# instance_manager.py
"""
Manages AI instances (only Ollama for now)
"""

import gi
from gi.repository import Adw, Gtk, GLib

import openai, requests, json, logging, os, shutil, subprocess, threading, re
from pydantic import BaseModel
from .internal import source_dir, data_dir, cache_dir
from .custom_widgets import dialog_widget
from . import available_models_descriptions

logger = logging.getLogger(__name__)

window = None

override_urls = {
    'HSA_OVERRIDE_GFX_VERSION': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#overrides',
    'CUDA_VISIBLE_DEVICES': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#gpu-selection',
    'ROCR_VISIBLE_DEVICES': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#gpu-selection-1'
}

# Base instance, don't use directly
class base_instance:
    instance_id = None
    name = _('Instance')
    instance_url = None
    max_tokens = 4096
    api_key = None
    temperature = 0.7
    seed = 0
    overrides = {}
    model_directory = None
    default_model = None
    title_model = None
    pinned = False

    def generate_message(self, bot_message, model:str):
        chat = bot_message.get_chat()
        chat.busy = True
        if not chat.quick_chat:
            window.chat_list_box.get_tab_by_name(chat.get_name()).spinner.set_visible(True)
        chat.set_visible_child_name('content')
        window.switch_send_stop_button(False)
        if window.regenerate_button:
            GLib.idle_add(window.chat_list_box.get_current_chat().remove, window.regenerate_button)
        if chat.regenerate_button:
            chat.container.remove(chat.regenerate_button)

        messages = chat.convert_to_ollama()[:list(chat.messages.values()).index(bot_message)]
        if self.instance_type in ('gemini', 'venice'):
            for m in messages:
                if m.get('role') == 'system':
                    m['role'] = 'user'

        if not chat.quick_chat and [m['role'] for m in messages].count('assistant') == 0 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(target=self.generate_chat_title, args=(chat, '\n'.join([c.get('text') for c in messages[-1].get('content') if c.get('type') == 'text']))).start()

        params = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True
        }

        if self.seed != 0 and self.instance_type not in ('gemini', 'venice'):
            params["seed"] = self.seed

        try:
            response = self.client.chat.completions.create(**params)

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    bot_message.update_message({"content": chunk.choices[0].delta.content})
            bot_message.update_message({"done": True})
        except Exception as e:
            dialog_widget.simple_error(_('Instance Error'), _('Message generation failed'), e)
            logger.error(e)
            window.instance_listbox.unselect_all()

    def generate_chat_title(self, chat, prompt:str):
        class chat_title(BaseModel): #Pydantic
            title:str
            emoji:str = ""

        messages = [
            {"role": "system" if self.instance_type not in ('gemini', 'venice') else "user", "content": "You are an assistant that generates short chat titles based on the first message from a user. If you want to add an emoji, use the emoji character directly (e.g., 😀) instead of its description (e.g., ':happy_face:')."},
            {"role": "user", "content": "Generate a title for this prompt:\n{}".format(prompt)}
        ]

        model = self.title_model if self.title_model else self.get_default_model()

        params = {
            "temperature": 0.2,
            "model": model,
            "messages": messages,
            "max_tokens": 100
        }

        try:
            completion = self.client.beta.chat.completions.parse(**params, response_format=chat_title)
            response = completion.choices[0].message
            if response.parsed:
                emoji = response.parsed.emoji if len(response.parsed.emoji) == 1 else '💬'
                window.chat_list_box.rename_chat(chat.get_name(), '{} {}'.format(emoji, response.parsed.title).strip())
        except Exception as e:
            try:
                response = self.client.chat.completions.create(**params)
                window.chat_list_box.rename_chat(chat.get_name(), str(response.choices[0].message.content))
            except Exception as e:
                logger.error(e)

    def get_default_model(self):
        if not self.default_model:
            models = self.get_local_models()
            if len(models) > 0:
                self.default_model = models[0].get('name')
        return self.default_model

# Fallback for when there are no instances
class empty:
    instance_id = None
    name = 'Fallback Instance'
    instance_type = 'empty'
    instance_type_display = 'Empty'
    pinned = True

    def __init__(self):
        pass

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

class base_ollama(base_instance):
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
            dialog_widget.simple_error(_('Instance Error'), _('Could not retrieve added models'), str(e))
            logger.error(e)
            window.instance_listbox.unselect_all()
        return []

    def get_available_models(self) -> dict:
        try:
            with open(os.path.join(source_dir, 'available_models.json'), 'r', encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            dialog_widget.simple_error(_('Instance Error'), _('Could not retrieve available models'), e)
            logger.error(e)
            window.instance_listbox.unselect_all()
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
class ollama_managed(base_ollama):
    instance_type = 'ollama:managed'
    instance_type_display = _('Ollama (Managed)')
    instance_url = 'http://0.0.0.0:11434'
    overrides = {
        'HSA_OVERRIDE_GFX_VERSION': '',
        'CUDA_VISIBLE_DEVICES': '',
        'ROCR_VISIBLE_DEVICES': ''
    }
    model_directory = os.path.join(data_dir, '.ollama', 'models')

    def __init__(self, instance_id:str, name:str, instance_url:str, temperature:float, seed:int, overrides:dict, model_directory:str, default_model:str, title_model:str, pinned:bool):
        self.instance_id = instance_id
        self.name = name
        self.instance_url = instance_url
        self.temperature = temperature
        self.seed = seed
        self.overrides = overrides
        self.model_directory = model_directory
        self.default_model = default_model
        self.title_model = title_model
        self.pinned = pinned
        self.process = None
        self.log_raw = ''
        self.log_summary = ('', ['dim-label'])
        self.client = openai.OpenAI(
            base_url='{}/v1/'.format(self.instance_url),
            api_key=self.api_key
        )

    def log_output(self, pipe):
        AMD_support_label = "\n<a href='https://github.com/Jeffser/Alpaca/wiki/AMD-Support'>{}</a>".format(_('Alpaca Support'))
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
            if not os.path.isdir(os.path.join(cache_dir, 'tmp/ollama')):
                os.mkdir(os.path.join(cache_dir, 'tmp/ollama'))
            params = self.overrides.copy()
            params["OLLAMA_HOST"] = self.instance_url
            params["TMPDIR"] = os.path.join(cache_dir, 'tmp/ollama')
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
                dialog_widget.simple_error(_('Instance Error'), _('Managed Ollama instance failed to start'), e)
                logger.error(e)
                window.instance_listbox.unselect_all()
            self.log_summary = (_("Integrated Ollama instance is running"), ['dim-label', 'success'])

    def get_preferences_page(self) -> Adw.PreferencesPage:
        pp = Adw.PreferencesPage()
        pg = Adw.PreferencesGroup(title=self.instance_type_display, description=_('Local AI instance managed directly by Alpaca'))

        if self.instance_id:
            logger_button = Gtk.Button(icon_name='terminal-symbolic', valign=1, css_classes=['flat'], tooltip_text=_('Ollama Log'))
            logger_button.connect('clicked', lambda button: dialog_widget.simple_log(_('Ollama Log'), self.log_summary[0], self.log_summary[1], '\n'.join(self.log_raw.split('\n')[-50:])))
            pg.set_header_suffix(logger_button)

        pp.add(pg)

        name_el = Adw.EntryRow(title=_('Name'), name='name', text=self.name)
        pg.add(name_el)
        try:
            port = int(self.instance_url.split(':')[-1])
        except Exception as e:
            port = 11435
        port_el = Adw.SpinRow(title=_('Port'), subtitle=_('Which network port will Ollama use'), name='port', digits=0, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=port, lower=1024, upper=65535, step_increment=1))
        pg.add(port_el)

        pg = Adw.PreferencesGroup()
        pp.add(pg)
        temperature_el = Adw.SpinRow(title=_('Temperature'), subtitle=_('Increasing the temperature will make the models answer more creatively.'), name='temperature', digits=2, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=self.temperature, lower=0.01, upper=2, step_increment=0.01))
        pg.add(temperature_el)

        seed_el = Adw.SpinRow(title=_('Seed'), subtitle=_('Setting this to a specific number other than 0 will make the model generate the same text for the same prompt.'), name='seed', digits=0, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=self.seed, lower=0, upper=99999999, step_increment=1))
        pg.add(seed_el)

        pg = Adw.PreferencesGroup()
        pp.add(pg)
        directory_el = Adw.ActionRow(title=_('Model Directory'), subtitle=self.model_directory)
        open_dir_button = Gtk.Button(
            tooltip_text=_('Select Directory'),
            icon_name='inode-directory-symbolic',
            valign=3
        )
        open_dir_button.connect('clicked', lambda button, row=directory_el: dialog_widget.simple_directory(lambda res, row=directory_el: row.set_subtitle(res.get_path())))
        directory_el.add_suffix(open_dir_button)
        pg.add(directory_el)

        if self.instance_id:
            pg = Adw.PreferencesGroup()
            pp.add(pg)
            default_model_el = Adw.ComboRow(title=_('Default Model'), subtitle=_('Model to select when starting a new chat.'))
            default_model_index = 0
            title_model_el = Adw.ComboRow(title=_('Title Model'), subtitle=_('Model to use when generating a chat title.'))
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
            pg.add(default_model_el)
            pg.add(title_model_el)

        pg = Adw.PreferencesGroup(title=_('Overrides'), description=_('These entries are optional, they are used to troubleshoot GPU related problems with Ollama.'))
        pp.add(pg)
        override_elements = {}
        for name, value in self.overrides.items():
            override_elements[name] = Adw.EntryRow(title=name, name='override:{}'.format(name), text=value)
            if override_urls.get(name):
                link_button = Gtk.Button(
                    name=override_urls.get(name),
                    tooltip_text=override_urls.get(name),
                    icon_name='globe-symbolic',
                    valign=3
                )
                link_button.connect('clicked', window.link_button_handler)
                override_elements[name].add_suffix(link_button)
            pg.add(override_elements[name])

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

        def save():
            if name_el.get_text():
                self.name = name_el.get_text()
            self.instance_url = 'http://0.0.0.0:{}'.format(int(port_el.get_value()))
            self.temperature = temperature_el.get_value()
            self.seed = int(seed_el.get_value())
            self.model_directory = directory_el.get_subtitle()
            self.overrides = {}
            for name, element in override_elements.items():
                self.overrides[name] = element.get_text()
            if self.instance_id:
                if default_model_el.get_selected_item():
                    self.default_model = window.convert_model_name(default_model_el.get_selected_item().get_string(), 1)
                if title_model_el.get_selected_item():
                    self.title_model = window.convert_model_name(title_model_el.get_selected_item().get_string(), 1)
                self.start()
            else:
                self.instance_id = window.generate_uuid()

            window.sql_instance.insert_or_update_instance(self)
            update_instance_list()
            window.main_navigation_view.pop_to_tag('instance_manager')

        save_button.connect('clicked', lambda button: save())
        button_container.append(save_button)
        pg.add(button_container)
        return pp

# Remote Connection Equivalent
class ollama(base_ollama):
    instance_type = 'ollama'
    instance_type_display = 'Ollama'
    instance_url = 'http://0.0.0.0:11434'

    def __init__(self, instance_id:str, name:str, instance_url:str, api_key:str, temperature:float, seed:int, default_model:str, title_model:str, pinned:bool):
        self.instance_id = instance_id
        self.name = name
        self.instance_url = instance_url
        self.api_key = api_key
        self.temperature = temperature
        self.seed = seed
        self.default_model = default_model
        self.title_model = title_model
        self.pinned = pinned
        self.client = openai.OpenAI(
            base_url='{}/v1/'.format(self.instance_url),
            api_key=self.api_key
        )

    def get_preferences_page(self) -> Adw.PreferencesPage:
        pp = Adw.PreferencesPage()
        pg = Adw.PreferencesGroup(title=self.instance_type_display, description=_('Local or remote AI instance not managed by Alpaca'))
        pp.add(pg)

        name_el = Adw.EntryRow(title=_('Name'), name='name', text=self.name)
        pg.add(name_el)

        url_el = Adw.EntryRow(title=_('Instance URL'), name='url', text=self.instance_url)
        pg.add(url_el)

        api_el = Adw.EntryRow(title=_('API Key (Optional)'), name='api', text=self.api_key)
        link_button = Gtk.Button(
            name='https://github.com/Jeffser/Alpaca/wiki/Instances#bearer-token-compatibility',
            tooltip_text='https://github.com/Jeffser/Alpaca/wiki/Instances#bearer-token-compatibility',
            icon_name='globe-symbolic',
            valign=3
        )
        link_button.connect('clicked', window.link_button_handler)
        api_el.add_suffix(link_button)
        pg.add(api_el)

        pg = Adw.PreferencesGroup()
        pp.add(pg)

        temperature_el = Adw.SpinRow(title=_('Temperature'), subtitle=_('Increasing the temperature will make the models answer more creatively.'), name='temperature', digits=2, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=self.temperature, lower=0.01, upper=2, step_increment=0.01))
        pg.add(temperature_el)

        seed_el = Adw.SpinRow(title=_('Seed'), subtitle=_('Setting this to a specific number other than 0 will make the model generate the same text for the same prompt.'), name='seed', digits=0, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=self.seed, lower=0, upper=99999999, step_increment=1))
        pg.add(seed_el)

        if self.instance_id:
            pg = Adw.PreferencesGroup()
            pp.add(pg)
            default_model_el = Adw.ComboRow(title=_('Default Model'), subtitle=_('Model to select when starting a new chat.'))
            default_model_index = 0
            title_model_el = Adw.ComboRow(title=_('Title Model'), subtitle=_('Model to use when generating a chat title.'))
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
            pg.add(default_model_el)
            pg.add(title_model_el)

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

        def save():
            if self.instance_id:
                if default_model_el.get_selected_item():
                    self.default_model = window.convert_model_name(default_model_el.get_selected_item().get_string(), 1)
                if title_model_el.get_selected_item():
                    self.title_model = window.convert_model_name(title_model_el.get_selected_item().get_string(), 1)
            else:
                self.instance_id = window.generate_uuid()
            if name_el.get_text():
                self.name = name_el.get_text()
            self.instance_url = url_el.get_text().rstrip('/')
            if not re.match(r'^(http|https)://', self.instance_url):
                self.instance_url = 'http://{}'.format(self.instance_url)
            self.api_key = api_el.get_text()
            self.temperature = temperature_el.get_value()
            self.seed = int(seed_el.get_value())

            window.sql_instance.insert_or_update_instance(self)
            update_instance_list()
            window.main_navigation_view.pop_to_tag('instance_manager')

        save_button.connect('clicked', lambda button: save())
        button_container.append(save_button)
        pg.add(button_container)
        return pp

class base_openai(base_instance):
    max_tokens = 256
    api_key = ''

    def __init__(self, instance_id:str, name:str, max_tokens:int, api_key:str, temperature:float, seed:int, default_model:str, title_model:str, pinned:bool):
        self.instance_id = instance_id
        self.name = name
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.temperature = temperature
        self.seed = seed
        self.default_model = default_model
        self.title_model = title_model
        self.pinned = pinned
        self.client = openai.OpenAI(
            base_url=self.instance_url,
            api_key=self.api_key
        )

    def stop(self):
        pass

    def get_local_models(self) -> list:
        try:
            return [{'name': m.id} for m in self.client.models.list()]
        except Exception as e:
            dialog_widget.simple_error(_('Instance Error'), _('Could not retrieve added models'), str(e))
            logger.error(e)
            window.instance_listbox.unselect_all()
            return []

    def get_available_models(self) -> dict:
        return {}

    def get_model_info(self, model_name:str) -> dict:
        return {}

    def get_preferences_page(self) -> Adw.PreferencesPage:
        pp = Adw.PreferencesPage()
        pg = Adw.PreferencesGroup(title=self.instance_type_display, description=self.instance_url)
        pp.add(pg)

        name_el = Adw.EntryRow(title=_('Name'), name='name', text=self.name)
        pg.add(name_el)
        if self.instance_type in ('openai:generic',):
            url_el = Adw.EntryRow(title=_('Instance URL'), name='url', text=self.instance_url)
            pg.add(url_el)
        api_el = Adw.EntryRow(title=_('API Key (Unchanged)') if self.api_key else _('API Key'), name='api')
        if self.api_key:
            api_el.connect('changed', lambda el: api_el.set_title(_('API Key') if api_el.get_text() else _('API Key (Unchanged)')))
        pg.add(api_el)

        pg = Adw.PreferencesGroup()
        pp.add(pg)
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
                upper=4096,
                step_increment=1
            )
        )
        pg.add(max_tokens_el)

        pg = Adw.PreferencesGroup()
        pp.add(pg)

        temperature_el = Adw.SpinRow(title=_('Temperature'), subtitle=_('Increasing the temperature will make the models answer more creatively.'), name='temperature', digits=2, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=self.temperature, lower=0.01, upper=2, step_increment=0.01))
        pg.add(temperature_el)

        if self.instance_type not in ('gemini', 'venice'):
            seed_el = Adw.SpinRow(title=_('Seed'), subtitle=_('Setting this to a specific number other than 0 will make the model generate the same text for the same prompt.'), name='seed', digits=0, numeric=True, snap_to_ticks=True, adjustment=Gtk.Adjustment(value=self.seed, lower=0, upper=99999999, step_increment=1))
            pg.add(seed_el)

        if self.instance_id:
            pg = Adw.PreferencesGroup()
            pp.add(pg)
            default_model_el = Adw.ComboRow(title=_('Default Model'), subtitle=_('Model to select when starting a new chat.'))
            default_model_index = 0
            title_model_el = Adw.ComboRow(title=_('Title Model'), subtitle=_('Model to use when generating a chat title.'))
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
            pg.add(default_model_el)
            pg.add(title_model_el)

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

        def save():
            if self.instance_id:
                if default_model_el.get_selected_item():
                    self.default_model = window.convert_model_name(default_model_el.get_selected_item().get_string(), 1)
                if title_model_el.get_selected_item():
                    self.title_model = window.convert_model_name(title_model_el.get_selected_item().get_string(), 1)
            else:
                self.instance_id = window.generate_uuid()
            if self.instance_type in ('openai:generic', 'llamacpp'):
                self.instance_url = url_el.get_text().rstrip('/')
                if not re.match(r'^(http|https)://', self.instance_url):
                    self.instance_url = 'http://{}'.format(self.instance_url)
            if name_el.get_text():
                self.name = name_el.get_text()
            if api_el.get_text():
                self.api_key = api_el.get_text()
            self.max_tokens = int(max_tokens_el.get_value())
            self.temperature = temperature_el.get_value()
            if self.instance_type not in ('gemini', 'venice'):
                self.seed = int(seed_el.get_value())

            window.sql_instance.insert_or_update_instance(self)
            update_instance_list()
            window.main_navigation_view.pop_to_tag('instance_manager')

        save_button.connect('clicked', lambda button: save())
        button_container.append(save_button)
        pg.add(button_container)
        return pp

class chatgpt(base_openai):
    instance_type = 'chatgpt'
    instance_type_display = 'OpenAI ChatGPT'
    instance_url = 'https://api.openai.com/v1/'

class gemini(base_openai):
    instance_type = 'gemini'
    instance_type_display = 'Google Gemini'
    instance_url = 'https://generativelanguage.googleapis.com/v1beta/openai/'

    def get_local_models(self) -> list:
        try:
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models?key={}'.format(self.api_key))
            models = []
            for model in response.json().get('models', []):
                if "generateContent" in model.get("supportedGenerationMethods", []) and 'discontinued' not in model.get('description'):
                    model['name'] = model.get('name').removeprefix('models/')
                    models.append(model)
            return models
        except Exception as e:
            dialog_widget.simple_error(_('Instance Error'), _('Could not retrieve added models'), str(e))
            logger.error(e)
            window.instance_listbox.unselect_all()

    def get_model_info(self, model_name:str) -> dict:
        try:
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models/{}?key={}'.format(model_name, self.api_key))
            data = response.json()
            data['projector_info'] = True
            return data
        except Exception as e:
            logger.error(e)
        return {}

class together(base_openai):
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
            dialog_widget.simple_error(_('Instance Error'), _('Could not retrieve added models'), str(e))
            logger.error(e)
            window.instance_listbox.unselect_all()

class venice(base_openai):
    instance_type = 'venice'
    instance_type_display = 'Venice'
    instance_url = 'https://api.venice.ai/api/v1/'

class generic_openai(base_openai):
    instance_type = 'openai:generic'
    instance_type_display = _('OpenAI Compatible Instance')

    def __init__(self, instance_id:str, name:str, instance_url:str, max_tokens:int, api_key:str, temperature:float, seed:int, default_model:str, title_model:str, pinned:bool):
        self.instance_url = instance_url
        super().__init__(instance_id, name, max_tokens, api_key, temperature, seed, default_model, title_model, pinned)

class instance_row(Adw.ActionRow):
    __gtype_name__ = 'AlpacaInstanceRow'

    def __init__(self, instance):
        self.instance = instance
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
            remove_button.connect('clicked', lambda button: dialog_widget.simple(_('Remove Instance?'), _('Are you sure you want to remove this instance?'), self.remove, _('Remove'), 'destructive'))
            self.add_suffix(remove_button)
        if not isinstance(self.instance, empty):
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
        window.sql_instance.delete_instance(self.instance.instance_id)
        update_instance_list()

def update_instance_list():
    window.instance_listbox.remove_all()
    window.instance_listbox.set_sensitive(False)
    instances = window.sql_instance.get_instances()
    selected_instance = window.sql_instance.get_preference('selected_instance')
    openai_compatible_instances = {
        chatgpt.instance_type: chatgpt,
        gemini.instance_type: gemini,
        together.instance_type: together,
        venice.instance_type: venice,
    }
    if len(instances) > 0:
        window.instance_manager_stack.set_visible_child_name('content')
        window.instance_listbox.set_sensitive(True)
        for i, ins in enumerate(instances):
            row = None
            if ins.get('type') == 'ollama:managed' and shutil.which('ollama'):
                row = instance_row(ollama_managed(ins.get('id'), ins.get('name'), ins.get('url'), ins.get('temperature'), ins.get('seed'), ins.get('overrides'), ins.get('model_directory'), ins.get('default_model'), ins.get('title_model'), ins.get('pinned')))
            elif ins.get('type') == 'ollama':
                row = instance_row(ollama(ins.get('id'), ins.get('name'), ins.get('url'), ins.get('api'), ins.get('temperature'), ins.get('seed'), ins.get('default_model'), ins.get('title_model'), ins.get('pinned')))
            elif ins.get('type') == 'openai:generic':
                row = instance_row(generic_openai(ins.get('id'), ins.get('name'), ins.get('url'), ins.get('max_tokens'), ins.get('api'), ins.get('temperature'), ins.get('seed'), ins.get('default_model'), ins.get('title_model'), ins.get('pinned')))
            elif openai_compatible_instances.get(ins.get('type')):
                row = instance_row(openai_compatible_instances.get(ins.get('type'))(ins.get('id'), ins.get('name'), ins.get('max_tokens'), ins.get('api'), ins.get('temperature'), ins.get('seed'), ins.get('default_model'), ins.get('title_model'), ins.get('pinned')))
            if row:
                window.instance_listbox.append(row)
                if selected_instance == row.instance.instance_id:
                    window.instance_listbox.select_row(row)
        if not window.instance_listbox.get_selected_row():
            window.instance_listbox.select_row(window.instance_listbox.get_row_at_index(0))
    else:
        window.instance_manager_stack.set_visible_child_name('no-instances')
        row = instance_row(empty())
        window.instance_listbox.append(row)
        window.instance_listbox.set_sensitive(True)
        window.instance_listbox.select_row(row)

ready_instances = [ollama, chatgpt, gemini, together, venice, generic_openai]

if shutil.which('ollama'):
    ready_instances.insert(0, ollama_managed)
