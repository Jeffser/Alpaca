# ollama_instances.py

from gi.repository import Adw, Gtk, GLib

import requests, json, logging, os, shutil, subprocess, threading, re, signal, pwd, getpass
from .. import dialog, tools
from ...ollama_models import OLLAMA_MODELS
from ...constants import data_dir, cache_dir, TITLE_GENERATION_PROMPT_OLLAMA, MAX_TOKENS_TITLE_GENERATION
from ...sql_manager import generate_uuid, dict_to_metadata_string, Instance as SQL

logger = logging.getLogger(__name__)

# Base instance, don't use directly
class BaseInstance:
    description = None
    process = None

    def prepare_chat(self, bot_message):
        bot_message.chat.busy = True
        if bot_message.chat.chat_id:
            bot_message.chat.row.spinner.set_visible(True)
            bot_message.get_root().global_footer.toggle_action_button(False)
        bot_message.chat.set_visible_child_name('content')

        messages = bot_message.chat.convert_to_ollama()[:list(bot_message.chat.container).index(bot_message)]
        return bot_message.chat, messages

    def generate_message(self, bot_message, model:str):
        chat, messages = self.prepare_chat(bot_message)

        if chat.chat_id and [m.get('role') for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    messages[-1].get('content'),
                    model
                )
            ).start()
        self.generate_response(bot_message, chat, messages, model)

    def use_tools(self, bot_message, model:str, available_tools:dict, generate_message:bool):
        chat, messages = self.prepare_chat(bot_message)
        if bot_message.options_button:
            bot_message.options_button.set_active(False)
        GLib.idle_add(bot_message.block_container.add_css_class, 'dim-label')
        bot_message.block_container.prepare_generating_block()

        if chat.chat_id and [m.get('role') for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(
                target=self.generate_chat_title,
                args=(
                    chat,
                    messages[-1].get('content'),
                    model
                )
            ).start()

        try:
            tools.log_to_message(_("Selecting tool to use..."), bot_message, True)
            params = {
                "model": model,
                "messages": messages,
                "stream": False,
                "tools": [v.get_tool() for v in available_tools.values()],
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
                tools.log_to_message(_("Using {}").format(function.get('name')), bot_message, True)
                if available_tools.get(function.get('name')):
                    gen_request, response = available_tools.get(function.get('name')).run(function.get('arguments'), messages, bot_message)
                    generate_message = generate_message and gen_request
                    response = str(response)
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
                        response
                    ]

                    attachment = bot_message.add_attachment(
                        file_id = generate_uuid(),
                        name = available_tools.get(function.get('name')).name,
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
                        'content': response
                    })
        except Exception as e:
            dialog.simple_error(
                parent = bot_message.get_root(),
                title = _('Tool Error'),
                body = _('An error occurred while running tool'),
                error_log = e
            )
            logger.error(e)

        if generate_message:
            GLib.idle_add(bot_message.block_container.remove_css_class, 'dim-label')
            GLib.idle_add(bot_message.block_container.clear)
            self.generate_response(bot_message, chat, messages, model)
        else:
            GLib.idle_add(bot_message.block_container.clear)
            bot_message.finish_generation('')

    def generate_response(self, bot_message, chat, messages:list, model:str):
        if bot_message.options_button:
            bot_message.options_button.set_active(False)
        bot_message.block_container.prepare_generating_block()

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
                GLib.idle_add(bot_message.block_container.clear)
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line.decode('utf-8'))
                            bot_message.update_message(data.get('message', {}).get('content'))
                        if not chat.busy or data.get('done'):
                            break
                else:
                    logger.error(response.content)
            except Exception as e:
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
                chat.row.rename('{} {}'.format(data.get('emoji').replace('\n', '').strip(), generated_title))
            else:
                chat.row.rename(generated_title)
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

    def pull_model(self, model_name:str, callback:callable):
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
                    'name': model_name,
                    'stream': True
                }),
                stream=True
            )
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        callback(json.loads(line.decode("utf-8")))
        except Exception as e:
            callback({'error': e})
            logger.error(e)

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

    def create_model(self, data:dict, callback:callable):
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
                        callback(json.loads(line.decode("utf-8")))
        except Exception as e:
            callback({'error': e})
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
            'HIP_VISIBLE_DEVICES': '1'
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
        self.log_summary = ('', ['dim-label'])
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
        AMD_support_label = "\n<a href='https://github.com/Jeffser/Alpaca/wiki/Installing-Ollama'>{}</a>".format(_('Alpaca Support'))
        with pipe:
            try:
                for line in iter(pipe.readline, ''):
                    self.log_raw += line
                    print(line, end='')
                    if 'msg="model request too large for system"' in line and self.row:
                        dialog.show_toast(_("Model request too large for system"), self.row.get_root())
                    elif 'msg="amdgpu detected, but no compatible rocm library found.' in line:
                        if bool(os.getenv("FLATPAK_ID")):
                            self.log_summary = (_("AMD GPU detected but the extension is missing, Ollama will use CPU.") + AMD_support_label, ['dim-label', 'error'])
                        else:
                            self.log_summary = (_("AMD GPU detected but ROCm is missing, Ollama will use CPU.") + AMD_support_label, ['dim-label', 'error'])
                    elif 'msg="amdgpu is supported"' in line:
                        self.log_summary = (_("Using AMD GPU type '{}'").format(line.split('=')[-1].replace('\n', '')), ['dim-label', 'success'])
            except Exception as e:
                pass

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
                self.log_summary = (_("Integrated Ollama instance is not running"), ['dim-label'])
                logger.info("Stopped Alpaca's Ollama instance")

    def start(self):
        if shutil.which('ollama') and not self.process:
            try:
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
                    ["ollama", "serve"],
                    env={**os.environ, **params},
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid
                )

                threading.Thread(target=self.log_output, args=(self.process.stdout,)).start()
                threading.Thread(target=self.log_output, args=(self.process.stderr,)).start()
                logger.info("Starting Alpaca's Ollama instance...")
                logger.info("Started Alpaca's Ollama instance")
                v_str = subprocess.check_output("ollama -v", shell=True).decode('utf-8')
                logger.info(v_str.split('\n')[1].strip('Warning: ').strip())
            except Exception as e:
                dialog.simple_error(
                    parent = self.row.get_root() if self.row else None,
                    title = _('Instance Error'),
                    body = _('Managed Ollama instance failed to start'),
                    error_log = e
                )
                logger.error(e)
                if self.row:
                    self.row.get_parent().unselect_all()
            self.log_summary = (_("Integrated Ollama instance is running"), ['dim-label', 'success'])

class Ollama(BaseInstance):
    instance_type = 'ollama'
    instance_type_display = 'Ollama'
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

