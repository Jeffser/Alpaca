# instance_manager.py
"""
Manages AI instances
"""

import gi
from gi.repository import Adw, Gtk, GLib

import openai, requests, json, logging, os, shutil, subprocess, threading, re
from pydantic import BaseModel

from ..ollama_models import OLLAMA_MODELS
from . import dialog, tools
from ..constants import data_dir, cache_dir
from ..sql_manager import generate_uuid, Instance as SQL

logger = logging.getLogger(__name__)

window = None

override_urls = {
    'HSA_OVERRIDE_GFX_VERSION': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#overrides',
    'CUDA_VISIBLE_DEVICES': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#gpu-selection',
    'ROCR_VISIBLE_DEVICES': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#gpu-selection-1'
}

# Base instance, don't use directly
class BaseInstance:
    instance_id = None
    name = _('Instance')
    instance_url = None
    max_tokens = None
    api_key = None
    temperature = 0.7
    seed = 0
    overrides = {}
    model_directory = None
    default_model = None
    title_model = None
    pinned = False
    description = None
    limitations = ()
    row = None

    def prepare_chat(self, bot_message):
        bot_message.chat.busy = True
        if bot_message.chat.chat_id:
            bot_message.chat.row.spinner.set_visible(True)
            bot_message.get_root().switch_send_stop_button(False)
        bot_message.chat.set_visible_child_name('content')

        messages = bot_message.chat.convert_to_json()[:list(bot_message.chat.container).index(bot_message)]
        return bot_message.chat, messages

    def generate_message(self, bot_message, model:str):
        chat, messages = self.prepare_chat(bot_message)

        if chat.chat_id and [m['role'] for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(target=self.generate_chat_title, args=(chat, '\n'.join([c.get('text') for c in messages[-1].get('content') if c.get('type') == 'text']))).start()

        self.generate_response(bot_message, chat, messages, model, None)

    def use_tools(self, bot_message, model:str):
        chat, messages = self.prepare_chat(bot_message)
        if bot_message.options_button:
            bot_message.options_button.set_active(False)
        bot_message.update_message({'add_css': 'dim-label'})

        if chat.chat_id and [m['role'] for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(target=self.generate_chat_title, args=(chat, '\n'.join([c.get('text') for c in messages[-1].get('content') if c.get('type') == 'text']))).start()

        available_tools = tools.get_enabled_tools(window.tool_listbox)
        tools_used = []

        try:
            tools.log_to_message(_("Selecting tool to use..."), bot_message, True)
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=available_tools
            )
            if completion.choices[0] and completion.choices[0].message:
                if completion.choices[0].message.tool_calls:
                    for call in completion.choices[0].message.tool_calls:
                        tools.log_to_message(_("Using {}").format(call.function.name), bot_message, True)
                        response = tools.run_tool(call.function.name, json.loads(call.function.arguments), messages, bot_message, window.listbox)
                        arguments = json.loads(call.function.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": str(response)
                        })
                        tools_used.append({
                            "name": call.function.name,
                            "arguments": arguments,
                            "response": str(response)
                        })
                        tool = tools.get_tool(call.function.name, window.tool_listbox)
                        if tool:
                            attachment = bot_message.add_attachment(
                                file_id = generate_uuid(),
                                name = tool.name,
                                attachment_type = 'tool',
                                content = '# {}\n\n## Arguments:\n\n{}\n\n## Result:\n\n{}'.format(
                                    tool.name,
                                    '\n'.join(['- {}: {}'.format(k.replace('_', ' ').title(), v) for k, v in arguments.items()]),
                                    str(response)
                                )
                            )
                            SQL.add_attachment(bot_message, attachment)
        except Exception as e:
            dialog.simple_error(
                parent = bot_message.get_root(),
                title = _('Tool Error'),
                body = _('An error occurred while running tool'),
                error_log = e
            )
            logger.error(e)

        tools.log_to_message(_("Generating message..."), bot_message, True)
        bot_message.update_message({'remove_css': 'dim-label'})
        self.generate_response(bot_message, chat, messages, model, tools_used if len(tools_used) > 0 else None)

    def generate_response(self, bot_message, chat, messages:list, model:str, tools_used:list):
        if bot_message.options_button:
            bot_message.options_button.set_active(False)

        GLib.idle_add(bot_message.block_container.get_generating_block) # Generate generating text block
        if 'no-system-messages' in self.limitations:
            for i in range(len(messages)):
                if messages[i].get('role') == 'system':
                    messages[i]['role'] = 'user'

        if 'text-only' in self.limitations:
            for i in range(len(messages)):
                for c in range(len(messages[i].get('content', []))):
                    if messages[i].get('content')[c].get('type') != 'text':
                        del messages[i]['content'][c]
                    else:
                        messages[i]['content'] = messages[i].get('content')[c].get('text')

        params = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": True
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if tools_used:
            params["tools"] = tools_used
            params["tool_choice"] = "none"

        if self.seed != 0 and 'no-seed' in self.limitations:
            params["seed"] = self.seed

        try:
            bot_message.update_message({"clear": True})
            response = self.client.chat.completions.create(**params)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        bot_message.update_message({"content": delta.content})
                if not chat.busy:
                    break
        except Exception as e:
            dialog.simple_error(
                parent = bot_message.get_root(),
                title = _('Instance Error'),
                body = _('Message generation failed'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
        bot_message.update_message({"done": True})

    def generate_chat_title(self, chat, prompt:str):
        class ChatTitle(BaseModel): #Pydantic
            title:str
            emoji:str = ""

        messages = [
            {"role": "user" if 'no-system-messages' in self.limitations else "system", "content": "You are an assistant that generates short chat titles based on the first message from a user. If you want to add an emoji, use the emoji character directly (e.g., 😀) instead of its description (e.g., ':happy_face:')."},
            {"role": "user", "content": "Generate a title for this prompt:\n{}".format(prompt)}
        ]

        model = self.title_model if self.title_model else self.get_default_model()

        params = {
            "temperature": 0.2,
            "model": model,
            "messages": messages,
            "max_tokens": 50
        }
        new_chat_title = chat.get_name()
        try:
            completion = self.client.beta.chat.completions.parse(**params, response_format=ChatTitle)
            response = completion.choices[0].message
            if response.parsed:
                emoji = response.parsed.emoji if len(response.parsed.emoji) == 1 else '💬'
                new_chat_title = '{} {}'.format(emoji, response.parsed.title)
        except Exception as e:
            try:
                response = self.client.chat.completions.create(**params)
                new_chat_title = str(response.choices[0].message.content)
            except Exception as e:
                logger.error(e)
        new_chat_title = re.sub(r'<think>.*?</think>', '', new_chat_title).strip()
        chat.rename(new_chat_title)

    def get_default_model(self):
        if not self.default_model:
            models = self.get_local_models()
            if len(models) > 0:
                self.default_model = models[0].get('name')
        return self.default_model

    def generate_preferences_page(self, elements:tuple, suffix_element=None) -> Adw.PreferencesPage:
        pp = Adw.PreferencesPage()
        pp.set_title(self.instance_type_display)
        groups = []
        groups.append(Adw.PreferencesGroup(title=self.instance_type_display, description=self.description if self.description else self.instance_url))
        if suffix_element:
            groups[-1].set_header_suffix(suffix_element)
        pp.add(groups[-1])

        if 'name' in elements:
            name_el = Adw.EntryRow(title=_('Name'), name='name', text=self.name)
            groups[-1].add(name_el)
        if 'port' in elements:
            try:
                port = int(self.instance_url.split(':')[-1])
            except Exception as e:
                port = 11435
            port_el = Adw.SpinRow(
                title=_('Port'),
                subtitle=_("Which network port will '{}' use").format(self.instance_type_display),
                name='port',
                digits=0,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=port,
                    lower=1024,
                    upper=65535,
                    step_increment=1
                )
            )
            groups[-1].add(port_el)
        if 'url' in elements:
            url_el = Adw.EntryRow(title=_('Instance URL'), name='url', text=self.instance_url)
            groups[-1].add(url_el)
        if 'api' in elements and self.instance_type == 'ollama':
            api_el = Adw.PasswordEntryRow(title=_('API Key (Unchanged)') if self.api_key else _('API Key (Optional)'), name='api')
            link_button = Gtk.Button(
                name='https://github.com/Jeffser/Alpaca/wiki/Instances#bearer-token-compatibility',
                tooltip_text='https://github.com/Jeffser/Alpaca/wiki/Instances#bearer-token-compatibility',
                icon_name='globe-symbolic',
                valign=3
            )
            link_button.connect('clicked', window.link_button_handler)
            api_el.add_suffix(link_button)
            if self.api_key:
                api_el.connect('changed', lambda el: api_el.set_title(_('API Key (Optional)') if api_el.get_text() else _('API Key (Unchanged)')))
            groups[-1].add(api_el)
        elif 'api' in elements:
            api_el = Adw.PasswordEntryRow(title=_('API Key (Unchanged)') if self.api_key else _('API Key'), name='api')
            if self.api_key:
                api_el.connect('changed', lambda el: api_el.set_title(_('API Key') if api_el.get_text() else _('API Key (Unchanged)')))
            groups[-1].add(api_el)

        groups.append(Adw.PreferencesGroup())
        pp.add(groups[-1])

        if 'max_tokens' in elements:
            max_tokens_el = Adw.SpinRow(
                title=_('Max Tokens'),
                subtitle=_('Defines the maximum number of tokens (words + spaces) the AI can generate in a response. More tokens allow longer replies but may take more time and cost more.'),
                name='max_tokens',
                digits=0,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.max_tokens,
                    lower=50,
                    upper=16384,
                    step_increment=1
                )
            )
            groups[-1].add(max_tokens_el)
        if 'temperature' in elements:
            temperature_el = Adw.SpinRow(
                title=_('Temperature'),
                subtitle=_('Increasing the temperature will make the models answer more creatively.'),
                name='temperature',
                digits=2,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.temperature,
                    lower=0.01,
                    upper=2,
                    step_increment=0.01
                )
            )
            groups[-1].add(temperature_el)
        if 'seed' in elements:
            seed_el = Adw.SpinRow(
                title=_('Seed'),
                subtitle=_('Setting this to a specific number other than 0 will make the model generate the same text for the same prompt.'),
                name='seed',
                digits=0,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.seed,
                    lower=0,
                    upper=99999999,
                    step_increment=1
                )
            )
            groups[-1].add(seed_el)

        if 'overrides' in elements and self.overrides:
            groups.append(Adw.PreferencesGroup(title=_('Overrides'), description=_('These entries are optional, they are used to troubleshoot GPU related problems with Ollama.')))
            pp.add(groups[-1])
            for name, value in self.overrides.items():
                override_el = Adw.EntryRow(title=name, name='override:{}'.format(name), text=value)
                if override_urls.get(name):
                    link_button = Gtk.Button(
                        name=override_urls.get(name),
                        tooltip_text=override_urls.get(name),
                        icon_name='globe-symbolic',
                        valign=3
                    )
                    link_button.connect('clicked', window.link_button_handler)
                    override_el.add_suffix(link_button)
                groups[-1].add(override_el)

        if 'model_directory' in elements:
            groups.append(Adw.PreferencesGroup())
            pp.add(groups[-1])
            model_directory_el = Adw.ActionRow(title=_('Model Directory'), subtitle=self.model_directory, name="model_directory")
            open_dir_button = Gtk.Button(
                tooltip_text=_('Select Directory'),
                icon_name='inode-directory-symbolic',
                valign=3
            )
            open_dir_button.connect('clicked', lambda button, row=model_directory_el: dialog.simple_directory(
                    parent = open_dir.get_root(),#TODO TEST
                    callback = lambda res, row=model_directory_el: row.set_subtitle(res.get_path())
                )
            )
            model_directory_el.add_suffix(open_dir_button)
            groups[-1].add(model_directory_el)

        if self.instance_id:
            groups.append(Adw.PreferencesGroup())
            pp.add(groups[-1])
            default_model_el = Adw.ComboRow(title=_('Default Model'), subtitle=_('Model to select when starting a new chat.'), name='default_model')
            default_model_index = 0
            title_model_el = Adw.ComboRow(title=_('Title Model'), subtitle=_('Model to use when generating a chat title.'), name='title_model')
            title_model_index = 0
            string_list = Gtk.StringList()
            for i, model in enumerate(self.get_local_models()):
                string_list.append(window.convert_model_name(model.get('name'), 0))
                if model.get('name') == self.default_model:
                    default_model_index = i
                if model.get('name') == self.title_model:
                    title_model_index = i
            default_model_el.set_model(string_list)
            default_model_el.set_selected(default_model_index)
            title_model_el.set_model(string_list)
            title_model_el.set_selected(title_model_index)
            groups[-1].add(default_model_el)
            groups[-1].add(title_model_el)

        def save():
            save_functions = {
                'name': lambda val: setattr(self, 'name', val if val else _('Instance')),
                'port': lambda val: setattr(self, 'instance_url', 'http://0.0.0.0:{}'.format(int(val))),
                'url': lambda val: setattr(self, 'instance_url', '{}{}'.format('http://' if not re.match(r'^(http|https)://', val) else '', val.rstrip('/'))),
                'api': lambda val: setattr(self, 'api_key', self.api_key if self.api_key and not val else (val if val else 'empty')),
                'max_tokens': lambda val: setattr(self, 'max_tokens', val if val else -1),
                'temperature': lambda val: setattr(self, 'temperature', val),
                'seed': lambda val: setattr(self, 'seed', val),
                'override': lambda name, val: self.overrides.__setitem__(name, val),
                'model_directory': lambda val: setattr(self, 'model_directory', val),
                'default_model': lambda val: setattr(self, 'default_model', window.convert_model_name(val, 1)),
                'title_model': lambda val: setattr(self, 'title_model', window.convert_model_name(val, 1))
            }

            for group in groups:
                for el in list(list(list(list(group)[0])[1])[0]):
                    value = None
                    if isinstance(el, Adw.EntryRow) or isinstance(el, Adw.PasswordEntryRow):
                        value = el.get_text().replace('\n', '')
                    elif isinstance(el, Adw.SpinRow):
                        value = el.get_value()
                    elif isinstance(el, Adw.ComboRow):
                        value = el.get_selected_item().get_string()
                    elif isinstance(el, Adw.ActionRow):
                        value = el.get_subtitle()
                    if el.get_name().startswith('override:'):
                        save_functions.get('override')(el.get_name().split(':')[1], value)
                    elif save_functions.get(el.get_name()):
                        save_functions.get(el.get_name())(value)

            if not self.instance_id:
                self.instance_id = generate_uuid()
            SQL.insert_or_update_instance(self)
            self.row.set_title(self.name)
            window.main_navigation_view.pop_to_tag('instance_manager')

        pg = Adw.PreferencesGroup()
        pp.add(pg)
        button_container = Gtk.Box(spacing=10, halign=3)
        cancel_button = Gtk.Button(
            label=_('Cancel'),
            tooltip_text=_('Cancel'),
            css_classes=['pill']
        )
        cancel_button.connect('clicked', lambda button: window.main_navigation_view.pop_to_tag('instance_manager'))
        button_container.append(cancel_button)
        save_button = Gtk.Button(
            label=_('Save'),
            tooltip_text=_('Save'),
            css_classes=['pill', 'suggested-action']
        )
        save_button.connect('clicked', lambda button: save())
        button_container.append(save_button)
        pg.add(button_container)
        return pp

# Fallback for when there are no instances
class Empty:
    instance_id = None
    name = 'Fallback Instance'
    instance_type = 'empty'
    instance_type_display = 'Empty'
    pinned = True

    def stop(self):
        pass

    def get_local_models(self) -> list:
        return []

    def get_available_models(self) -> dict:
        return {}

    def get_model_info(self, model_name:str) -> dict:
        return {}

    def get_default_model(self) -> str:
        return ''

class BaseOllama(BaseInstance):
    api_key = 'ollama'
    process = None

    def stop(self):
        pass

    def start(self):
        pass

    def get_local_models(self) -> list:
        if not self.process:
            self.start()
        try:
            response = requests.get('{}/api/tags'.format(self.instance_url), headers={'Authorization': 'Bearer {}'.format(self.api_key)})
            if response.status_code == 200:
                return json.loads(response.text).get('models')
        except Exception as e:
            dialog.simple_error(
                parent = window, # TODO replace window with root, also in get_available_models
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
        return []

    def get_available_models(self) -> dict:
        try:
            return OLLAMA_MODELS
        except Exception as e:
            dialog.simple_error(
                parent = window,
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
            response = requests.post('{}/api/show'.format(self.instance_url), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer {}'.format(self.api_key)}, data=json.dumps({"name": model_name}), stream=False)
            if response.status_code == 200:
                return json.loads(response.text)
        except Exception as e:
            logger.error(e)
        return {}

    def pull_model(self, model_name:str, callback:callable):
        if not self.process:
            self.start()
        try:
            response = requests.post('{}/api/pull'.format(self.instance_url), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer {}'.format(self.api_key)}, data=json.dumps({'name': model_name, 'stream': True}), stream=True)
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
            return requests.get('{}/api/blobs/sha256:{}'.format(self.instance_url, sha256), headers={'Authorization': 'Bearer {}'.format(self.api_key)}).status_code != 404
        except Exception as e:
            return False

    def upload_gguf(self, gguf_path:str, sha256:str):
        if not self.process:
            self.start()
        with open(gguf_path, 'rb') as f:
            requests.post('{}/api/blobs/sha256:{}'.format(self.instance_url, sha256), data=f, headers={'Authorization': 'Bearer {}'.format(self.api_key)})

    def create_model(self, data:dict, callback:callable):
        if not self.process:
            self.start()
        try:
            response = requests.post('{}/api/create'.format(self.instance_url), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer {}'.format(self.api_key)}, data=json.dumps(data), stream=True)
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
            response = requests.delete('{}/api/delete'.format(self.instance_url), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer {}'.format(self.api_key)}, data=json.dumps({"name": model_name}))
            return response.status_code == 200
        except Exception as e:
            return False

# Local ollama instance equivalent
class OllamaManaged(BaseOllama):
    instance_type = 'ollama:managed'
    instance_type_display = _('Ollama (Managed)')
    instance_url = 'http://0.0.0.0:11434'
    overrides = {
        'HSA_OVERRIDE_GFX_VERSION': '',
        'CUDA_VISIBLE_DEVICES': '',
        'ROCR_VISIBLE_DEVICES': '1',
        'HIP_VISIBLE_DEVICES': '1'
    }
    model_directory = os.path.join(data_dir, '.ollama', 'models')
    description = _('Local AI instance managed directly by Alpaca')

    def __init__(self, data:dict={}):
        self.instance_id = data.get('id', self.instance_id)
        self.name = data.get('name', self.name)
        self.instance_url = data.get('url', self.instance_url).removesuffix('.0')
        self.temperature = data.get('temperature', self.temperature)
        self.seed = data.get('seed', self.seed)
        for key in self.overrides:
            self.overrides[key] = data.get('overrides', self.overrides).get(key, self.overrides.get(key))
        self.model_directory = data.get('model_directory', self.model_directory)
        self.default_model = data.get('default_model', self.default_model)
        self.title_model = data.get('title_model', self.title_model)
        self.pinned = data.get('pinned', self.pinned)
        self.process = None
        self.log_raw = ''
        self.log_summary = ('', ['dim-label'])
        if self.instance_id:
            self.client = openai.OpenAI(
                base_url='{}/v1/'.format(self.instance_url).replace('\n', ''),
                api_key=self.api_key if self.api_key else 'NO_KEY'
            )

    def log_output(self, pipe):
        AMD_support_label = "\n<a href='https://github.com/Jeffser/Alpaca/wiki/Installing-Ollama'>{}</a>".format(_('Alpaca Support'))
        with pipe:
            try:
                for line in iter(pipe.readline, ''):
                    self.log_raw += line
                    print(line, end='')
                    if 'msg="model request too large for system"' in line:
                        window.show_toast(_("Model request too large for system"), window.main_overlay)
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
            self.process.terminate()
            self.process.wait()
            self.process = None
            self.log_summary = (_("Integrated Ollama instance is not running"), ['dim-label'])
            logger.info("Stopped Alpaca's Ollama instance")

    def start(self):
        self.stop()
        if shutil.which('ollama'):
            if not os.path.isdir(os.path.join(cache_dir, 'tmp', 'ollama')):
                os.mkdir(os.path.join(cache_dir, 'tmp', 'ollama'))
            params = self.overrides.copy()
            params["OLLAMA_HOST"] = self.instance_url
            params["TMPDIR"] = os.path.join(cache_dir, 'tmp', 'ollama')
            params["OLLAMA_MODELS"] = self.model_directory
            self.process = subprocess.Popen(["ollama", "serve"], env={**os.environ, **params}, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            threading.Thread(target=self.log_output, args=(self.process.stdout,)).start()
            threading.Thread(target=self.log_output, args=(self.process.stderr,)).start()
            logger.info("Starting Alpaca's Ollama instance...")
            logger.debug(params)
            logger.info("Started Alpaca's Ollama instance")
            try:
                v_str = subprocess.check_output("ollama -v", shell=True).decode('utf-8')
                logger.info(v_str.split('\n')[1].strip('Warning: ').strip())
            except Exception as e:
                dialog.simple_error(
                    parent = window,
                    title = _('Instance Error'),
                    body = _('Managed Ollama instance failed to start'),
                    error_log = e
                )
                logger.error(e)
                window.instance_listbox.unselect_all()
            self.log_summary = (_("Integrated Ollama instance is running"), ['dim-label', 'success'])

    def get_preferences_page(self) -> Adw.PreferencesPage:
        suffix_button = None
        if self.instance_id:
            suffix_button = Gtk.Button(icon_name='terminal-symbolic', valign=1, css_classes=['flat'], tooltip_text=_('Ollama Log'))
            suffix_button.connect('clicked', lambda button: dialog.simple_log(
                    parent = window,
                    title = _('Ollama Log'),
                    summary_text = self.log_summary[0],
                    summary_classes = self.log_summary[1],
                    log_text = '\n'.join(self.log_raw.split('\n')[-50:])
                )
            )
        arguments = {
            'elements': ('name', 'port', 'temperature', 'seed', 'overrides', 'model_directory'),
            'suffix_element': suffix_button
        }
        return self.generate_preferences_page(**arguments)

# Remote Connection Equivalent
class Ollama(BaseOllama):
    instance_type = 'ollama'
    instance_type_display = 'Ollama'
    instance_url = 'http://0.0.0.0:11434'
    description = _('Local or remote AI instance not managed by Alpaca')

    def __init__(self, data:dict={}):
        self.instance_id = data.get('id', self.instance_id)
        self.name = data.get('name', self.name)
        self.instance_url = data.get('url', self.instance_url)
        self.api_key = data.get('api', self.api_key)
        self.temperature = data.get('temperature', self.temperature)
        self.seed = data.get('seed', self.seed)
        self.default_model = data.get('default_model', self.default_model)
        self.title_model = data.get('title_model', self.title_model)
        self.pinned = data.get('pinned', self.pinned)
        if self.instance_id:
            self.client = openai.OpenAI(
                base_url='{}/v1/'.format(self.instance_url).replace('\n', ''),
                api_key=self.api_key if self.api_key else 'NO_KEY'
            )

    def get_preferences_page(self) -> Adw.PreferencesPage:
        arguments = {
            'elements': ('name', 'url', 'api', 'temperature', 'seed')
        }
        return self.generate_preferences_page(**arguments)

class BaseOpenAI(BaseInstance):
    max_tokens = 2048
    api_key = ''

    def __init__(self, data:dict={}):
        self.instance_id = data.get('id', self.instance_id)
        self.name = data.get('name', self.name)
        self.max_tokens = data.get('max_tokens', self.max_tokens)
        self.api_key = data.get('api', self.api_key)
        self.temperature = data.get('temperature', self.temperature)
        self.seed = data.get('seed', self.seed)
        self.default_model = data.get('default_model', self.default_model)
        self.title_model = data.get('title_model', self.title_model)
        self.pinned = data.get('pinned', self.pinned)
        if self.instance_id:
            self.client = openai.OpenAI(
                base_url=self.instance_url.replace('\n', ''),
                api_key=self.api_key if self.api_key else 'NO_KEY'
            )

    def stop(self):
        pass

    def get_local_models(self) -> list:
        try:
            return [{'name': m.id} for m in self.client.models.list() if 'whisper' not in m.id.lower()]
        except Exception as e:
            dialog.simple_error(
                parent = window,
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
            return []

    def get_available_models(self) -> dict:
        return {}

    def get_model_info(self, model_name:str) -> dict:
        return {}

    def get_preferences_page(self) -> Adw.PreferencesPage:
        arguments = {
            'elements': ('name', 'api', 'temperature', 'max_tokens')
        }
        if 'no-seed' in self.limitations:
            arguments['elements'] = arguments['elements'] + ('seed',)
        if self.instance_type == 'openai:generic':
            arguments['elements'] = arguments['elements'] + ('url',)
        return self.generate_preferences_page(**arguments)

class ChatGPT(BaseOpenAI):
    instance_type = 'chatgpt'
    instance_type_display = 'OpenAI ChatGPT'
    instance_url = 'https://api.openai.com/v1/'

class Gemini(BaseOpenAI):
    instance_type = 'gemini'
    instance_type_display = 'Google Gemini'
    instance_url = 'https://generativelanguage.googleapis.com/v1beta/openai/'
    limitations = ('no-system-messages', 'no-seed')

    def get_local_models(self) -> list:
        try:
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models?key={}'.format(self.api_key))
            models = []
            for model in response.json().get('models', []):
                if "generateContent" in model.get("supportedGenerationMethods", []) and 'deprecated' not in model.get('description', ''):
                    model['name'] = model.get('name').removeprefix('models/')
                    models.append(model)
            return models
        except Exception as e:
            dialog.simple_error(
                parent = window,
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
        return []

    def get_model_info(self, model_name:str) -> dict:
        try:
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models/{}?key={}'.format(model_name, self.api_key))
            data = response.json()
            data['capabilities'] = ['completion', 'vision']
            return data
        except Exception as e:
            logger.error(e)
        return {}

class Together(BaseOpenAI):
    instance_type = 'together'
    instance_type_display = 'Together AI'
    instance_url = 'https://api.together.xyz/v1/'

    def get_local_models(self) -> list:
        try:
            response = requests.get('https://api.together.xyz/v1/models', headers={'accept': 'application/json', 'authorization': 'Bearer {}'.format(self.api_key)})
            models = []
            for model in response.json():
                if model.get('id') and model.get('type') == 'chat':
                    models.append({'name': model.get('id'), 'display_name': model.get('display_name')})
            return models
        except Exception as e:
            dialog.simple_error(
                parent = window,
                title = _('Instance Error'),
                body = _('Could not retrieve added models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()

class Venice(BaseOpenAI):
    instance_type = 'venice'
    instance_type_display = 'Venice'
    instance_url = 'https://api.venice.ai/api/v1/'
    limitations = ('no-system-messages', 'no-seed')

class Deepseek(BaseOpenAI):
    instance_type = 'deepseek'
    instance_type_display = 'Deepseek'
    instance_url = 'https://api.deepseek.com/v1/'
    limitations = ('text-only', 'no-seed')

class Groq(BaseOpenAI):
    instance_type = 'groq'
    instance_type_display = 'Groq Cloud'
    instance_url = 'https://api.groq.com/openai/v1'
    limitations = ('text-only')

class Anthropic(BaseOpenAI):
    instance_type = 'anthropic'
    instance_type_display = 'Anthropic'
    instance_url = 'https://api.anthropic.com/v1/'
    limitations = ('no-system-messages')

class OpenRouter(BaseOpenAI):
    instance_type = 'openrouter'
    instance_type_display = 'OpenRouter AI'
    instance_url = 'https://openrouter.ai/api/v1/'

    def get_local_models(self) -> list:
        try:
            response = requests.get('https://openrouter.ai/api/v1/models')
            models = []
            for model in response.json().get('data', []):
                if model.get('id'):
                    models.append({'name': model.get('id'), 'display_name': model.get('name')})
            return models
        except Exception as e:
            dialog.simple_error(
                parent = window,
                title = _('Instance Error'),
                body = _('Could not retrieve models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
            return []

class Fireworks(BaseOpenAI):
    instance_type = 'fireworks'
    instance_type_display = 'Fireworks AI'
    instance_url = 'https://api.fireworks.ai/inference/v1/'
    description = _('Fireworks AI inference platform')

    def get_local_models(self) -> list:
        try:
            response = requests.get('https://api.fireworks.ai/inference/v1/models', headers={'Authorization': f'Bearer {self.api_key}'})
            models = []
            for model in response.json().get('data', []):
                if model.get('id') and 'chat' in model.get('capabilities', []):
                    models.append({'name': model.get('id'), 'display_name': model.get('name')})
            return models
        except Exception as e:
            dialog.simple_error(
                parent = window,
                title = _('Instance Error'),
                body = _('Could not retrieve models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
            return []

class LambdaLabs(BaseOpenAI):
    instance_type = 'lambda_labs'
    instance_type_display = 'Lambda Labs'
    instance_url = 'https://api.lambdalabs.com/v1/'
    description = _('Lambda Labs cloud inference API')

    def get_local_models(self) -> list:
        try:
            response = requests.get('https://api.lambdalabs.com/v1/models',
                                  headers={'Authorization': f'Bearer {self.api_key}'})
            models = []
            for model in response.json().get('data', []):
                if model.get('id'):
                    models.append({'name': model.get('id'), 'display_name': model.get('name')})
            return models
        except Exception as e:
            dialog.simple_error(
                parent = window,
                title = _('Instance Error'),
                body = _('Could not retrieve models'),
                error_log = e
            )
            logger.error(e)
            window.instance_listbox.unselect_all()
            return []

class Cerebras(BaseOpenAI):
    instance_type = 'cerebras'
    instance_type_display = 'Cerebras AI'
    instance_url = 'https://api.cerebras.ai/v1/'
    description = _('Cerebras AI cloud inference API')

class Klusterai(BaseOpenAI):
    instance_type = 'klusterai'
    instance_type_display = 'Kluster AI'
    instance_url = 'https://api.kluster.ai/v1/'
    description = _('Kluster AI cloud inference API')

class GenericOpenAI(BaseOpenAI):
    instance_type = 'openai:generic'
    instance_type_display = _('OpenAI Compatible Instance')
    description = _('AI instance compatible with OpenAI library')

    def __init__(self, data:dict={}):
        self.instance_url = data.get('url', self.instance_url)
        super().__init__(data)

class LlamaAPI(BaseOpenAI):
    instance_type = 'llama-api'
    instance_type_display = 'Llama API'
    instance_url = 'https://api.llama.com/compat/v1/'
    description = _('Meta AI Llama API')

class InstanceRow(Adw.ActionRow):
    __gtype_name__ = 'AlpacaInstanceRow'

    def __init__(self, instance):
        self.instance = instance
        self.instance.row = self
        super().__init__(
            title = self.instance.name,
            subtitle = self.instance.instance_type_display,
            name = self.instance.name
        )
        if not instance.pinned:
            remove_button = Gtk.Button(
                icon_name='user-trash-symbolic',
                valign=3,
                css_classes=['destructive-action', 'flat']
            )
            remove_button.connect('clicked', lambda button: dialog.simple(
                    parent = self.get_root(),
                    heading = _('Remove Instance?'),
                    body = _('Are you sure you want to remove this instance?'),
                    callback = self.remove,
                    button_name = _('Remove'),
                    button_appearance = 'destructive'
                )
            )
            self.add_suffix(remove_button)
        if not isinstance(self.instance, Empty):
            edit_button = Gtk.Button(
                icon_name='edit-symbolic',
                valign=3,
                css_classes=['accent', 'flat']
            )
            edit_button.connect('clicked', lambda button: self.show_edit())
            self.add_suffix(edit_button)

    def show_edit(self):
        tbv=Adw.ToolbarView()
        tbv.add_top_bar(Adw.HeaderBar())
        tbv.set_content(self.instance.get_preferences_page())
        window.main_navigation_view.push(Adw.NavigationPage(title=_('Edit Instance'), tag='instance', child=tbv))

    def remove(self):
        SQL.delete_instance(self.instance.instance_id)
        self.get_parent().remove(self)

def update_instance_list():
    window.instance_listbox.remove_all()
    window.instance_listbox.set_selection_mode(0)
    instances = SQL.get_instances()
    selected_instance = SQL.get_preference('selected_instance')
    instance_dictionary = {i.instance_type: i for i in ready_instances}
    if len(instances) > 0:
        window.instance_manager_stack.set_visible_child_name('content')
        window.instance_listbox.set_selection_mode(1)
        row_to_select = None
        for i, ins in enumerate(instances):
            if ins.get('max_tokens') == -1:
                ins['max_tokens'] = None
            if ins.get('type') in list(instance_dictionary.keys()) and (ins.get('type') != 'ollama:managed' or shutil.which('ollama')):
                row = InstanceRow(instance_dictionary.get(ins.get('type'))(ins))
                window.instance_listbox.append(row)
                if selected_instance == row.instance.instance_id:
                    row_to_select = row
        if row_to_select:
            window.instance_listbox.select_row(row_to_select)
        if not window.instance_listbox.get_selected_row():
            window.instance_listbox.select_row(window.instance_listbox.get_row_at_index(0))
    if len(list(window.instance_listbox)) == 0:
        window.instance_manager_stack.set_visible_child_name('no-instances')
        row = InstanceRow(Empty())
        window.instance_listbox.append(row)
        window.instance_listbox.set_selection_mode(1)
        window.instance_listbox.select_row(row)

if os.getenv('ALPACA_OLLAMA_ONLY', '0') == '1':
    ready_instances = [OllamaManaged, Ollama]
else:
    ready_instances = [OllamaManaged, Ollama, ChatGPT, Gemini, Together, Venice, Deepseek, OpenRouter, Anthropic, Groq, Fireworks, LambdaLabs, Cerebras, Klusterai, GenericOpenAI, LlamaAPI]


