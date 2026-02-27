# ollama_instances.py

from gi.repository import Adw, Gtk, GLib

import json, logging, os, shutil, subprocess, threading, re, signal, pwd, getpass, datetime, time, ollama
from .ollama_manager import OllamaManager, get_latest_ollama_tag
from .. import dialog, tools, chat
from ...ollama_models import OLLAMA_MODELS
from ...constants import data_dir, cache_dir, TITLE_GENERATION_PROMPT_OLLAMA, OLLAMA_BINARY_PATH, CAN_SELF_MANAGE_OLLAMA, is_ollama_installed
from ...sql_manager import generate_uuid, dict_to_metadata_string, Instance as SQL

logger = logging.getLogger(__name__)

# Base instance, don't use directly
class BaseInstance:
    description = None
    process = None

    def get_active_lore(self, messages:list, lorebook:dict) -> str:
        if len(lorebook.get('entries', [])) == 0:
            return
        messages_to_scan = messages[-lorebook.get('scan_depth', 100):]
        messages_str = '\n'.join([m.get('content') for m in messages_to_scan if m.get('role') != 'system'])
        active_lore_content = []

        for entry in lorebook.get('entries'):
            for key in entry.get('keys', []):
                clean_key = key.strip()
                if clean_key:
                    pattern = rf"\b{re.escape(clean_key)}\b"
                    if re.search(pattern, messages_str, flags=re.IGNORECASE):
                        content = '# {}\n\n{}'.format(clean_key.title(), entry.get('content', ''))
                        if content not in active_lore_content:
                            active_lore_content.append(content)
                        break

        return '\n\n---\n\n'.join(active_lore_content)

    def prepare_chat(self, bot_message, model:str):
        chat_element = bot_message.get_ancestor(chat.Chat)
        GLib.idle_add(bot_message.block_container.show_generating_block)
        if chat_element and chat_element.chat_id:
            GLib.idle_add(chat_element.row.spinner.set_visible, True)
            try:
                GLib.idle_add(bot_message.get_root().global_footer.toggle_action_button, False)
            except:
                pass
        
            chat_element.busy = True
            GLib.idle_add(chat_element.set_visible_child_name, 'content')

        messages = chat_element.convert_to_ollama()[:list(chat_element.container).index(bot_message)]

        character_dict = SQL.get_model_preferences(model).get('character', {})
        if character_dict.get('data', {}).get('extensions', {}).get('com.jeffser.Alpaca', {}).get('enabled', False):
            character_book = character_dict.get('data', {}).get('character_book', {})
            if len(character_book.get('entries', [])) > 0:
                lore_message = {
                    'role': 'system',
                    'content': self.get_active_lore(messages, character_book)
                }
                if lore_message.get('content'):
                    index = 0
                    for msg in messages:
                        if msg.get('role') == 'system':
                            index += 1
                        else:
                            break
                    messages.insert(index, lore_message)

        return chat_element, messages

    def generate_message(self, bot_message, model:str):
        chat, messages = self.prepare_chat(bot_message, model)

        if chat.chat_id and chat.get_name().startswith(_("New Chat")):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    messages[-1].get('content'),
                    model
                ),
                daemon=True
            ).start()
        self.generate_response(bot_message, chat, messages, model)

    def use_tools(self, bot_message, model:str, available_tools:dict):
        chat, messages = self.prepare_chat(bot_message, model)

        if chat.chat_id and chat.get_name().startswith(_("New Chat")):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    messages[-1].get('content'),
                    model
                ),
                daemon=True
            ).start()

        self.generate_response(bot_message, chat, messages, model, available_tools=available_tools)

    def generate_response(self, bot_message, chat, messages:list, model:str, available_tools:dict={}):
        if self.properties.get('share_name', 0) > 0:
            user_display_name = None
            if self.properties.get('share_name') == 1:
                user_display_name = getpass.getuser().title()
            elif self.properties.get('share_name') == 2:
                gecos_temp = pwd.getpwnam(getpass.getuser()).pw_gecos.split(',')
                if len(gecos_temp) > 0:
                    user_display_name = pwd.getpwnam(getpass.getuser()).pw_gecos.split(',')[0].title()

            if user_display_name:
                messages.insert(0, {
                    'role': 'system',
                    'content': 'The user is called {}'.format(user_display_name)
                })

        model_info = self.get_model_info(model)
        if model_info:
            if model_info.get('system'):
                messages.insert(0, {
                    'role': 'system',
                    'content': model_info.get('system')
                })

        params = {
            "model": model,
            "stream": True,
            "think": self.properties.get('think', False) and 'thinking' in model_info.get('capabilities', []),
            "keep_alive": self.properties.get('keep_alive', 300),
            "tools": [v.get_metadata() for v in available_tools.values()]
        }

        if self.properties.get("override_parameters"):
            params["options"] = {}
            params["options"]["temperature"] = self.properties.get('temperature', 0.7)
            params["options"]["num_ctx"] = self.properties.get('num_ctx', 16384)
            if self.properties.get('seed', 0) != 0:
                params["options"]["seed"] = self.properties.get('seed')

        metadata_string = ""
        tool_calls = []
        thought = ""
        content = ""
        try:
            while chat.busy:
                params['messages'] = messages
                response = self.client.chat(**params)
                bot_message.block_container.clear()
                for chunk in response:
                    if chunk.message.thinking:
                        bot_message.update_thinking(chunk.message.thinking)
                        thought += chunk.message.thinking
                    if chunk.message.content:
                        bot_message.update_message(chunk.message.content)
                        content += chunk.message.content
                    if chunk.message.tool_calls:
                        tool_calls.extend(chunk.message.tool_calls)

                    if chunk.done or not chat.busy:
                        data = {
                            'total_duration': chunk.total_duration,
                            'load_duration': chunk.load_duration,
                            'prompt_eval_count': chunk.prompt_eval_count,
                            'prompt_eval_duration': chunk.prompt_eval_duration,
                            'eval_count': chunk.eval_count,
                            'eval_duration': chunk.eval_duration
                        }
                        metadata_string = dict_to_metadata_string(data)
                        break

                GLib.idle_add(bot_message.remove_and_attach_thought)

                if not tool_calls or not chat.busy:
                    break

                messages.append({'role': 'assistant', 'thinking': thought, 'content': content, 'tool_calls': tool_calls})

                for call in tool_calls:
                    selected_tool = available_tools.get(call.function.name)
                    tool_response = selected_tool.run(
                        call.function.arguments,
                        messages,
                        bot_message
                    )
                    messages.append({"role": "tool", "tool_name": call.function.name, "content": str(tool_response)})
                    attachment_content = []

                    if len(call.function.arguments) > 0:
                        attachment_content += [
                            '## {}'.format(_('Arguments')),
                            '| {} | {} |'.format(_('Argument'), _('Value')),
                            '| --- | --- |'
                        ]
                        attachment_content += ['| {} | {} |'.format(k, v) for k, v in call.function.arguments.items()]

                    attachment_content += [
                        '## {}'.format(_('Result')),
                        str(tool_response)
                    ]

                    def add_attachment():
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = selected_tool.display_name,
                            attachment_type = 'tool',
                            content = '\n'.join(attachment_content)
                        )
                        SQL.insert_or_update_attachment(bot_message, attachment)
                    GLib.idle_add(add_attachment)

        except ollama.ResponseError as e:
            logger.error(e)
            if e.status_code == 401:
                if self.instance_type == 'ollama:managed':
                    with open(os.path.join(data_dir, '.ollama', 'id_ed25519'), 'rb') as f:
                        signin_url = self.signin_request()
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = 'Ollama Login',
                            attachment_type = 'link',
                            content = signin_url
                        )
                        SQL.insert_or_update_attachment(bot_message, attachment)
                        bot_message.update_message("🦙 Just a quick heads-up! To access the Ollama cloud models, you'll need to log into your Ollama account first.")
                elif self.instance_type == 'ollama:cloud':
                    bot_message.update_message("🦙 Please verify that the API key provided in the instance preferences is valid.")
                else:
                    attachment = bot_message.add_attachment(
                        file_id = generate_uuid(),
                        name = 'Ollama Login Tutorial',
                        attachment_type = 'link',
                        content = 'https://docs.ollama.com/api/authentication'
                    )
                    bot_message.update_message("🦙 Just a quick heads-up! To access the Ollama cloud models, you'll need to log into your Ollama account first from the server.")
        except Exception as e:
            if self.instance_type != 'ollama:managed' or is_ollama_installed():
                dialog.simple_error(
                    parent = bot_message.get_root(),
                    title = _('Instance Error'),
                    body = _('Message generation failed'),
                    error_log = e
                )
                logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()

        if not self.properties.get('show_response_metadata'):
            metadata_string = None
        bot_message.finish_generation(metadata_string)

    def generate_chat_title(self, chat, prompt:str, fallback_model:str):
        if not chat.row or not chat.row.get_parent():
            return
        model = self.get_title_model()
        params = {
            "options": {
                "temperature": 0.2
            },
            "model": model or fallback_model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": '{}\n\n{}'.format(TITLE_GENERATION_PROMPT_OLLAMA, prompt)
                }
            ],
            "format": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string"
                    }
                },
                "required": [
                    "title"
                ]
            },
            'think': False,
            "keep_alive": 0
        }
        if self.properties.get("override_parameters"):
            params["options"]["num_ctx"] = self.properties.get('num_ctx', 16384)
        try:
            response = self.client.chat(**params)
            data = json.loads(response.message.content or '{"title": "New Chat"}')
            generated_title = data.get('title').replace('\n', '').strip()

            if len(generated_title) > 30:
                generated_title = generated_title[:30].strip() + '...'

            GLib.idle_add(
                chat.row.edit,
                generated_title,
                chat.is_template
            )
        except Exception as e:
            logger.error(e)

    def get_default_model(self):
        local_models = self.get_local_models()
        if len(local_models) > 0:
            if not self.properties.get('default_model') or not self.properties.get('default_model') in [m.get('name') for m in local_models]:
                self.properties['default_model'] = local_models[0].get('name')
            return self.properties.get('default_model')

    def get_title_model(self):
        local_models = self.get_local_models()
        if len(local_models) > 0:
            if self.properties.get('title_model') and not self.properties.get('title_model') in [m.get('name') for m in local_models]:
                self.properties['title_model'] = local_models[0].get('name')
            return self.properties.get('title_model')

    def stop(self):
        self.client = None

    def start(self):
        if not self.client:
            self.client = ollama.Client(
                host=self.properties.get('url'),
                headers={
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                },
                verify=not self.properties.get('allow_self_signed_ssl', False)
            )

    def get_local_models(self) -> list:
        try:
            model_list = []

            for m in self.client.list().models:
                model_list.append({
                    'name': m.model,
                    'modified_at': m.modified_at,
                    'digest': m.digest,
                    'size': m.size,
                    'details': m.details
                })

            return model_list

            return [{'name': m.model} for m in models if m.model]
        except Exception as e:
            if self.instance_type != 'ollama:managed' or is_ollama_installed():
                dialog.simple_error(
                    parent = self.row.get_root() if self.row else None,
                    title = _('Instance Error'),
                    body = _('Could not retrieve added models'),
                    error_log = e
                )
                logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
        return []

    def get_available_models(self) -> dict:
        try:
            return OLLAMA_MODELS
        except Exception as e:
            if self.instance_type != 'ollama:managed' or is_ollama_installed():
                dialog.simple_error(
                    parent = self.row.get_root() if self.row else None,
                    title = _('Instance Error'),
                    body = _('Could not retrieve available models'),
                    error_log = e
                )
                logger.error(e)
        return {}

    def get_model_info(self, model_name:str) -> dict:
        try:
            response = self.client.show(model_name)
            return response
        except Exception as e:
            logger.error(e)
        return {}

    def pull_model(self, model):
        try:
            response = self.client.pull(
                model=model.get_name(),
                stream=True
            )
            for chunk in response:
                if not model.get_root():
                    break
                if chunk.status:
                    model.append_progress_line(chunk.status)
                if chunk.total and chunk.completed:
                    model.update_progressbar(chunk.completed / chunk.total)
                if chunk.status == 'success':
                    model.update_progressbar(-1)
                    break
        except Exception as e:
            if self.instance_type != 'ollama:managed' or is_ollama_installed():
                dialog.simple_error(
                    parent = self.row.get_root() if self.row else None,
                    title = _('Error Pulling Model'),
                    body = model.get_name(),
                    error_log = e
                )
                logger.error(e)
            model.get_parent().get_parent().remove(model.get_parent())

    def upload_gguf(self, gguf_path:str):
        digest = self.client.create_blob(gguf_path)
        return digest

    def create_model(self, data:dict, model):
        try:
            response = self.client.create(
                model=data.get('model'),
                from_=data.get('from'),
                template=data.get('template'),
                files=data.get('files'),
                parameters=data.get('parameters'),
                stream=True
            )
            for chunk in response:
                if chunk.status:
                    model.append_progress_line(chunk.status)
                if chunk.total and chunk.completed:
                    model.update_progressbar(chunk.completed / chunk.total)
                if chunk.status == 'success':
                    model.update_progressbar(-1)
                    break
        except Exception as e:
            model.get_parent().get_parent().remove(model.get_parent())
            logger.error(e)

    def delete_model(self, model_name:str):
        try:
            response = self.client.delete(model_name)
            return response.status == 'success'
        except Exception as e:
            logger.error(e)
        return False

class OllamaManaged(BaseInstance):
    instance_type = 'ollama:managed'
    instance_type_display = _('Ollama (Managed)')
    description = _('Local AI instance managed directly by Alpaca')

    default_properties = {
        'name': _('Instance'),
        'url': 'http://0.0.0.0:11434',
        'override_parameters': True,
        'temperature': 0.7,
        'seed': 0,
        'num_ctx': 16384,
        'keep_alive': 300,
        'model_directory': os.path.join(data_dir, '.ollama', 'models'),
        'default_model': None,
        'title_model': None,
        'overrides': {
            'HSA_OVERRIDE_GFX_VERSION': '',
            'CUDA_VISIBLE_DEVICES': '',
            'ROCR_VISIBLE_DEVICES': '',
            'HIP_VISIBLE_DEVICES': '',
            'OLLAMA_VULKAN': ''
        },
        'think': False,
        'expose': False,
        'share_name': 0,
        'show_response_metadata': False
    }

    def __init__(self, instance_id:str, properties:dict):
        self.instance_id = instance_id
        self.process = None
        self.log_raw = ''
        self.rocm_status = 0 # 0: no need, 1: using Vulkan 2: wants rocm, 3: rocm ok
        self.version_number = ''
        self.last_auto_version_check_time = 0

        self.properties = {}
        self.row = None
        for key in self.default_properties:
            if key == 'overrides':
                self.properties[key] = {}
                for override in self.default_properties.get(key):
                    self.properties[key][override] = properties.get(key, {}).get(override, self.default_properties.get(key).get(override))
            else:
                self.properties[key] = properties.get(key, self.default_properties.get(key))

        self.client = None

    def signin_request(self) -> str:
        # For use with cloud models, returns the url even though it also opens it
        try:
            params = {
                "OLLAMA_HOST": self.properties.get('url')
            }
            result = subprocess.run(
                [OLLAMA_BINARY_PATH, 'signin'],
                capture_output=True,
                text=True,
                env={**os.environ, **params},
            )
            output = result.stdout + result.stderr
            url_match = re.search(r'https://ollama\.com/connect\?\S+', output)
            if url_match:
                return url_match.group(0)
        except Exception as e:
            logger.error(e)
        return ''

    def log_output(self, pipe):
        AMD_support_label = "\n<a href='https://jeffser.com/alpaca/installation-guide.html'>{}</a>".format(_('Alpaca Support'))
        with pipe:
            try:
                for line in iter(pipe.readline, ''):
                    self.log_raw += line
                    print(line, end='')
                    if 'msg="model request too large for system"' in line and self.row:
                        dialog.show_toast(_("Model request too large for system"), self.row.get_root())
                    elif 'library=cpu' in line:
                        self.rocm_status = 0
                    elif 'library=Vulkan' in line:
                        self.rocm_status = 1
                    elif 'msg="amdgpu is supported"' in line:
                        self.rocm_status = 2
                    elif 'library=ROCm' in line:
                        self.rocm_status = 3
            except Exception as e:
                pass

    def auto_check_version(self):
        installed_tag = self.version_number.strip('v').strip()
        available_tag = get_latest_ollama_tag().strip('v').strip()

        if available_tag and installed_tag:
            available_tag = available_tag.strip('v').strip()
            if installed_tag != available_tag:
                manager_dialog = OllamaManager(self)
                manager_dialog.update_check_requested(None)
                manager_dialog.navigation_view.replace_with_tags(["update_available"])
                manager_dialog.present(self.row.get_root())

    def stop(self):
        if self.process:
            logger.info("Stopping Alpaca's Ollama instance")
            try:
                # Check if process is still alive before trying to stop it
                if self.process.poll() is None:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    # Wait with timeout to avoid hanging indefinitely
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning("Ollama process didn't stop gracefully, forcing kill")
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        self.process.wait(timeout=2)
            except (ProcessLookupError, OSError) as e:
                logger.info(f"Process already stopped or not accessible: {e}")
            except Exception as e:
                logger.error(f"Error stopping Ollama process: {e}")
            finally:
                self.process = None
                self.log_raw += '\nOllama stopped by Alpaca\n'
                logger.info("Stopped Alpaca's Ollama instance")
        self.client = None

    def start(self):
        if not self.process:
            try:
                logger.info("Starting Alpaca's Ollama instance...")
                params = self.properties.get('overrides', {}).copy()
                params["HOME"] = data_dir
                params["OLLAMA_HOST"] = self.properties.get('url')
                params["OLLAMA_MODELS"] = self.properties.get('model_directory')
                if self.properties.get("expose"):
                    params["OLLAMA_ORIGINS"] = "chrome-extension://*,moz-extension://*,safari-web-extension://*,http://0.0.0.0,http://127.0.0.1"
                else:
                    params["OLLAMA_ORIGINS"] = params.get("OLLAMA_HOST")
                for key in list(params):
                    if not params.get(key):
                        del params[key]
                self.process = subprocess.Popen(
                    [OLLAMA_BINARY_PATH, "serve"],
                    env={**os.environ, **params},
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid
                )

                threading.Thread(target=self.log_output, args=(self.process.stdout,), daemon=True).start()
                threading.Thread(target=self.log_output, args=(self.process.stderr,), daemon=True).start()
                logger.info("Started Alpaca's Ollama instance")
                self.version_number = subprocess.check_output("{} -v".format(OLLAMA_BINARY_PATH), shell=True).decode('utf-8')
                self.version_number = self.version_number.split(' ')[-1].strip('v').strip()
                if self.version_number:
                    logger.info('Ollama version is {}'.format(self.version_number))
                if CAN_SELF_MANAGE_OLLAMA and self.row and self.row.get_root().settings.get_value('ollama-managed-auto-check-update').unpack() and time.time() - self.last_auto_version_check_time > 300:
                    self.last_auto_version_check_time = time.time()
                    GLib.idle_add(self.auto_check_version)
            except Exception as e:
                logger.error(e)
                if not is_ollama_installed():
                    if self.row:
                        GLib.idle_add(lambda: OllamaManager(self).present(self.row.get_root()))
                else:
                    dialog.simple_error(
                        parent = self.row.get_root() if self.row else None,
                        title = _('Instance Error'),
                        body = _('Managed Ollama instance failed to start'),
                        error_log = e
                    )
                if self.row:
                    GLib.idle_add(self.row.get_parent().unselect_all)
                self.stop()
        if not self.client:
            self.client = ollama.Client(
                host=self.properties.get('url'),
                headers={
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                },
                verify=not self.properties.get('allow_self_signed_ssl', False)
            )

class Ollama(BaseInstance):
    instance_type = 'ollama'
    instance_type_display = _('Ollama (External)')
    description = _('Local or remote AI instance not managed by Alpaca')

    default_properties = {
        'name': _('Instance'),
        'url': 'http://0.0.0.0:11434',
        'api': '',
        'override_parameters': True,
        'temperature': 0.7,
        'seed': 0,
        'num_ctx': 16384,
        'keep_alive': 300,
        'default_model': None,
        'title_model': None,
        'think': False,
        'share_name': 0,
        'show_response_metadata': False,
        'allow_self_signed_ssl': False
    }

    def __init__(self, instance_id:str, properties:dict):
        self.instance_id = instance_id
        self.properties = {}
        self.row = None
        for key in self.default_properties:
            self.properties[key] = properties.get(key, self.default_properties.get(key))

        self.client = None

class OllamaCloud(BaseInstance):
    instance_type = 'ollama:cloud'
    instance_type_display = _('Ollama (Cloud)')
    description = _('Online instance directly managed by Ollama (Experimental)')

    default_properties = {
        'name': _('Instance'),
        'url': 'https://ollama.com',
        'api': '',
        'override_parameters': True,
        'temperature': 0.7,
        'seed': 0,
        'num_ctx': 16384,
        'default_model': None,
        'title_model': None,
        'think': False,
        'share_name': 0,
        'show_response_metadata': False
    }

    def __init__(self, instance_id:str, properties:dict):
        self.instance_id = instance_id
        self.properties = {}
        self.row = None
        for key in self.default_properties:
            self.properties[key] = properties.get(key, self.default_properties.get(key))

        self.client = None

    def pull_model(self, model):
        SQL.append_online_instance_model_list(self.instance_id, model.get_name())
        GLib.timeout_add(5000, lambda: model.update_progressbar(-1) and False)

    def delete_model(self, model_name:str) -> bool:
        SQL.remove_online_instance_model_list(self.instance_id, model_name)
        return True

    def get_local_models(self) -> list:
        local_models = []
        for model in SQL.get_online_instance_model_list(self.instance_id):
            local_models.append({'name': model})
        return local_models

    def get_available_models(self) -> dict:
        try:
            response = self.client.list()
            available_models = {}
            for model in response.models:
                if ':' in model.model:
                    model_name, model_tag = model.model.split(':')
                else:
                    model_name, model_tag = model.model, ''

                model_metadata = OLLAMA_MODELS.get(model_name)
                if model_metadata:
                    available_models[model_name] = {
                        'url': model_metadata.get('url'),
                        'tags': [],
                        'author': model_metadata.get('author'),
                        'categories': [c for c in model_metadata.get('categories') if c not in ['small', 'medium', 'big', 'huge']],
                        'languages': model_metadata.get('languages'),
                        'description': model_metadata.get('description')
                    }
                else:
                    available_models[model_name] = {
                        'tags': [],
                        'categories': ['cloud']
                    }
                available_models[model_name]['tags'].append([model_tag, 'cloud'])
            return available_models
        except Exception as e:
            if self.instance_type != 'ollama:managed' or is_ollama_installed():
                dialog.simple_error(
                    parent = self.row.get_root() if self.row else None,
                    title = _('Instance Error'),
                    body = _('Could not retrieve added models'),
                    error_log = e
                )
                logger.error(e)
            if self.row:
                self.row.get_parent().unselect_all()
        return {}


