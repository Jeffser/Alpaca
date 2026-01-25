# ollama_instances.py

from gi.repository import Adw, Gtk, GLib

import requests, json, logging, os, shutil, subprocess, threading, re, signal, pwd, getpass, datetime, time
from .ollama_manager import OllamaManager, get_latest_ollama_tag
from .. import dialog, tools, chat
from ...ollama_models import OLLAMA_MODELS
from ...constants import data_dir, cache_dir, TITLE_GENERATION_PROMPT_OLLAMA, MAX_TOKENS_TITLE_GENERATION, OLLAMA_BINARY_PATH, CAN_SELF_MANAGE_OLLAMA, is_ollama_installed
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
        bot_message.block_container.show_generating_block()
        if chat_element and chat_element.chat_id:
            chat_element.row.spinner.set_visible(True)
            try:
                bot_message.get_root().global_footer.toggle_action_button(False)
            except:
                pass
        
            chat_element.busy = True
            chat_element.set_visible_child_name('content')

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

    def use_tools(self, bot_message, model:str, available_tools:dict, generate_message:bool):
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

        message_response = ''
        try:
            params = {
                "model": model,
                "messages": messages,
                "stream": False,
                "tools": [v.get_metadata() for v in available_tools.values()],
                "think": False
            }
            response = requests.post(
                '{}/api/chat'.format(self.properties.get('url')),
                headers={
                    "Authorization": "Bearer {}".format(self.properties.get('api')),
                    "Content-Type": "application/json"
                },
                data=json.dumps(params)
            )
            tool_calls = response.json().get('message', {}).get('tool_calls', [])
            for tc in tool_calls:
                function = tc.get('function')
                if available_tools.get(function.get('name')):
                    message_response, tool_response = available_tools.get(function.get('name')).run(function.get('arguments'), messages, bot_message)
                    generate_message = generate_message and not bool(message_response)

                    attachment_content = []

                    if len(function.get('arguments', {})) > 0:
                        attachment_content += [
                            '## {}'.format(_('Arguments')),
                            '| {} | {} |'.format(_('Argument'), _('Value')),
                            '| --- | --- |'
                        ]
                        attachment_content += ['| {} | {} |'.format(k, v) for k, v in function.get('arguments', {}).items()]

                    attachment_content += [
                        '## {}'.format(_('Result')),
                        str(tool_response)
                    ]

                    attachment = bot_message.add_attachment(
                        file_id = generate_uuid(),
                        name = available_tools.get(function.get('name')).display_name,
                        attachment_type = 'tool',
                        content = '\n'.join(attachment_content)
                    )
                    SQL.insert_or_update_attachment(bot_message, attachment)
                    messages.append({
                        'role': 'assistant',
                        'content': '',
                    })
                    messages.append({
                        'role': 'tool',
                        'content': str(tool_response)
                    })
        except Exception as e:
            if self.instance_type != 'ollama:managed' or is_ollama_installed():
                dialog.simple_error(
                    parent = bot_message.get_root(),
                    title = _('Tool Error'),
                    body = _('An error occurred while running tool'),
                    error_log = e
                )
                logger.error(e)

        if generate_message:
            self.generate_response(bot_message, chat, messages, model)
        else:
            bot_message.block_container.set_content(str(message_response))
            bot_message.finish_generation('')

    def generate_response(self, bot_message, chat, messages:list, model:str):
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

        time_now = datetime.datetime.now().replace(microsecond=0).astimezone().isoformat()

        messages.insert(0, {
            'role': 'system',
            'content': 'Current time is {}'.format(time_now),
        })

        params = {
            "model": model,
            "messages": messages,
            "stream": True,
            "think": self.properties.get('think', False) and 'thinking' in model_info.get('capabilities', []),
            "keep_alive": self.properties.get('keep_alive', 300)
        }

        if self.properties.get("override_parameters"):
            params["options"] = {}
            params["options"]["temperature"] = self.properties.get('temperature', 0.7)
            params["options"]["num_ctx"] = self.properties.get('num_ctx', 16384)
            if self.properties.get('seed', 0) != 0:
                params["options"]["seed"] = self.properties.get('seed')

        data = {'done': True}
        if chat.busy:
            try:
                response = requests.post(
                    '{}/api/chat'.format(self.properties.get('url')),
                    headers={
                        "Authorization": "Bearer {}".format(self.properties.get('api')),
                        "Content-Type": "application/json"
                    },
                    data=json.dumps(params),
                    stream=True
                )
                bot_message.block_container.clear()
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line.decode('utf-8'))
                            content = data.get('message', {}).get('content')
                            think_content = data.get('message', {}).get('thinking')
                            if content:
                                bot_message.update_message(content)
                            if think_content:
                                bot_message.update_thinking(think_content)
                        if not chat.busy or data.get('done'):
                            break
                else:
                    response_json = response.json()
                    if response_json.get('error') == 'unauthorized' and response_json.get('signin_url'):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = 'Ollama Login',
                            attachment_type = 'link',
                            content = response_json.get('signin_url')
                        )
                        SQL.insert_or_update_attachment(bot_message, attachment)
                        bot_message.update_message("🦙 Just a quick heads-up! To access the Ollama cloud models, you'll need to log into your Ollama account first.")
                    logger.error(response.content)
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
        metadata_string = None
        if self.properties.get('show_response_metadata'):
            metadata_string = dict_to_metadata_string(data)
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
            "max_tokens": MAX_TOKENS_TITLE_GENERATION,
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
                    },
                    "emoji": {
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
            response = requests.post(
                '{}/api/chat'.format(self.properties.get('url')),
                headers={
                    "Authorization": "Bearer {}".format(self.properties.get('api')),
                    "Content-Type": "application/json"
                },
                data=json.dumps(params)
            )
            data = json.loads(response.json().get('message', {}).get('content', '{"title": "New Chat"}'))
            generated_title = data.get('title').replace('\n', '').strip()

            if len(generated_title) > 30:
                generated_title = generated_title[:30].strip() + '...'

            if data.get('emoji'):
                chat.row.edit(
                    new_name='{} {}'.format(data.get('emoji').replace('\n', '').strip(), generated_title),
                    is_template=chat.is_template
                )
            else:
                chat.row.edit(
                    new_name=generated_title,
                    is_template=chat.is_template
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
        pass

    def start(self):
        pass

    def get_local_models(self) -> list:
        if not self.process:
            self.start()
        try:
            response = requests.get(
                '{}/api/tags'.format(self.properties.get('url')),
                headers={
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                }
            )
            if response.status_code == 200:
                return json.loads(response.text).get('models')
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
        if not self.process:
            self.start()
        try:
            response = requests.post(
                '{}/api/show'.format(self.properties.get('url')),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                },
                data=json.dumps({
                    "name": model_name
                }),
                stream=False
            )
            if response.status_code == 200:
                return json.loads(response.text)
        except Exception as e:
            logger.error(e)
        return {}

    def pull_model(self, model):
        if not self.process:
            self.start()
        try:
            response = requests.post(
                '{}/api/pull'.format(self.properties.get('url')),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                },
                data=json.dumps({
                    'model': model.get_name(),
                    'stream': True
                }),
                stream=True
            )
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode("utf-8"))
                        if data.get('error'):
                            raise Exception(data.get('error'))
                        if data.get('status'):
                            model.append_progress_line(data.get('status'))
                        if data.get('total') and data.get('completed'):
                            model.update_progressbar(data.get('completed') / data.get('total'))
                        if data.get('status') == 'success':
                            model.update_progressbar(-1)
                            return
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

    def gguf_exists(self, sha256:str) -> bool:
        if not self.process:
            self.start()
        try:
            return requests.head(
                '{}/api/blobs/sha256:{}'.format(self.properties.get('url'), sha256),
                headers={
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                }
            ).status_code == 200
        except Exception as e:
            return False

    def upload_gguf(self, gguf_path:str, sha256:str):
        if not self.process:
            self.start()
        with open(gguf_path, 'rb') as f:
            requests.post(
                '{}/api/blobs/sha256:{}'.format(self.properties.get('url'), sha256),
                data=f,
                headers={
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                }
            )

    def create_model(self, data:dict, model):
        if not self.process:
            self.start()
        try:
            response = requests.post(
                '{}/api/create'.format(self.properties.get('url')),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                },
                data=json.dumps(data),
                stream=True
            )
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode("utf-8"))
                        if data.get('status'):
                            model.append_progress_line(data.get('status'))
                        if data.get('total') and data.get('completed'):
                            model.update_progressbar(data.get('completed') / data.get('total'))
                        if data.get('status') == 'success':
                            model.update_progressbar(-1)
                            return
        except Exception as e:
            model.get_parent().get_parent().remove(model.get_parent())
            logger.error(e)

    def delete_model(self, model_name:str):
        if not self.process:
            self.start()
        try:
            response = requests.delete(
                '{}/api/delete'.format(self.properties.get('url')),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                },
                data=json.dumps({
                    "name": model_name
                })
            )
            return response.status_code == 200
        except Exception as e:
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
            'CUDA_VISIBLE_DEVICES': '0',
            'ROCR_VISIBLE_DEVICES': '1',
            'HIP_VISIBLE_DEVICES': '1',
            'OLLAMA_VULKAN': '0'
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
        available_tag = get_latest_ollama_tag()

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
                logger.info("Stopped Alpaca's Ollama instance")

    def start(self):
        if not self.process:
            try:
                logger.info("Starting Alpaca's Ollama instance...")
                params = self.properties.get('overrides', {}).copy()
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
                self.version_number = self.version_number.strip('ollama version is ').strip()
                if self.version_number:
                    logger.info('Ollama version is {}'.format(self.version_number))
                if CAN_SELF_MANAGE_OLLAMA and self.row.get_root().settings.get_value('ollama-managed-auto-check-update').unpack() and time.time() - self.last_auto_version_check_time > 300:
                    self.last_auto_version_check_time = time.time()
                    GLib.idle_add(self.auto_check_version)
            except Exception as e:
                logger.error(e)
                if not is_ollama_installed():
                    if self.row:
                        OllamaManager(self).present(self.row.get_root())
                else:
                    dialog.simple_error(
                        parent = self.row.get_root() if self.row else None,
                        title = _('Instance Error'),
                        body = _('Managed Ollama instance failed to start'),
                        error_log = e
                    )
                if self.row:
                    self.row.get_parent().unselect_all()
                self.stop()

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
        'show_response_metadata': False
    }

    def __init__(self, instance_id:str, properties:dict):
        self.instance_id = instance_id
        self.properties = {}
        self.row = None
        for key in self.default_properties:
            self.properties[key] = properties.get(key, self.default_properties.get(key))

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
        if not self.process:
            self.start()
        try:
            response = requests.get(
                '{}/api/tags'.format(self.properties.get('url')),
                headers={
                    'Authorization': 'Bearer {}'.format(self.properties.get('api'))
                }
            )
            if response.status_code == 200:
                available_models = {}

                for model in [m.get('model') for m in response.json().get('models', [])]:
                    if ':' in model:
                        model_name, model_tag = model.split(':')
                    else:
                        model_name, model_tag = model, ''

                    if not available_models.get(model_name):
                        model_metadata = OLLAMA_MODELS.get(model_name)
                        if model_metadata:
                            available_models[model_name] = {
                                'url': model_metadata.get('url'),
                                'tags': [],
                                'author': model_metadata.get('author'),
                                'categories': model_metadata.get('categories'),
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
