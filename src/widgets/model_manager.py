# model_manager.py
"""
Handles models
"""

import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf, GObject
import logging, os, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ..constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ..sql_manager import prettify_model_name, Instance as SQL
from . import dialog, attachments, models as MODELSTEST

logger = logging.getLogger(__name__)

window = None

available_models = {}
tts_model_path = ""

class TextToSpeechModel(Gtk.Box):
    __gtype_name__ = 'AlpacaTextToSpeechModel'

    def __init__(self, name:str):
        self.model_title = name.title()
        super().__init__(
            spacing=10,
            css_classes=['card', 'model_box'],
            name=name
        )
        self.image_container = Adw.Bin(
            css_classes=['model_pfp'],
            valign=3,
            halign=3,
            overflow=1,
            child=Gtk.Image.new_from_icon_name("bullhorn-symbolic")
        )
        self.append(self.image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        self.append(text_container)
        title_label = Gtk.Label(
            label=self.model_title,
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        self.subtitle_label = Gtk.Label(
            label=_("Text to Speech"),
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(self.subtitle_label)
        self.page = None

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    def get_default_widget(self) -> Gtk.Widget:
        return None

    def remove_model(self):
        global tts_model_path
        name = '{}.pt'.format(TTS_VOICES.get(self.get_name(), ''))
        symlink_path = os.path.join(tts_model_path, name)

        if os.path.islink(symlink_path):
            target_path = os.readlink(symlink_path)
            os.unlink(symlink_path)
            if os.path.isfile(target_path):
                os.remove(target_path)
        window.local_model_flowbox.remove(self)

    def get_page(self):
        buttons = []
        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text="https://github.com/hexgrad/kokoro"
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri("https://github.com/hexgrad/kokoro"))
        buttons.append(web_button)

        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        ))
        buttons.append(remove_button)

        page = Adw.StatusPage(
            icon_name="bullhorn-symbolic",
            title=self.model_title,
            description=_("Local text to speech model provided by Kokoro.")
        )
        return buttons, page

class SpeechToTextModel(Gtk.Box):
    __gtype_name__ = 'AlpacaSpeechToTextModel'

    def __init__(self, name:str):
        self.model_title = name.title()
        super().__init__(
            spacing=10,
            css_classes=['card', 'model_box'],
            name=name
        )
        self.image_container = Adw.Bin(
            css_classes=['model_pfp'],
            valign=3,
            halign=3,
            overflow=1,
            child=Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        )
        self.append(self.image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        self.append(text_container)
        title_label = Gtk.Label(
            label=self.model_title,
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        self.subtitle_label = Gtk.Label(
            label=_("Speech to Text"),
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(self.subtitle_label)
        self.page = None

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    def get_default_widget(self) -> Gtk.Widget:
        return None

    def remove_model(self):
        model_path = os.path.join(data_dir, 'whisper', '{}.pt'.format(self.get_name()))
        if os.path.isfile(model_path):
            os.remove(model_path)
        window.local_model_flowbox.remove(self)

    def get_page(self):
        buttons = []
        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text="https://github.com/openai/whisper"
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri("https://github.com/openai/whisper"))
        buttons.append(web_button)

        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        ))
        buttons.append(remove_button)

        page = Adw.StatusPage(
            icon_name="audio-input-microphone-symbolic",
            title=self.model_title,
            description=_("Local speech to text model provided by OpenAI Whisper."),
            child=Gtk.Label(label=STT_MODELS.get(self.get_name(), '~151mb'), css_classes=["dim-label"])
        )
        return buttons, page

def add_text_to_speech_model(model_name:str):
    model_element = TextToSpeechModel(model_name)
    window.local_model_flowbox.prepend(model_element)
    return model_element

def add_speech_to_text_model(model_name:str):
    model_element = SpeechToTextModel(model_name)
    #window.local_model_flowbox.prepend(model_element)
    return model_element

def update_local_model_list():
    global tts_model_path
    window.local_model_flowbox.remove_all()
    GLib.idle_add(window.model_dropdown.get_model().remove_all)

    if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
        # Speech to Text
        if os.path.isdir(os.path.join(data_dir, 'whisper')):
            for model in os.listdir(os.path.join(data_dir, 'whisper')):
                if model.endswith('.pt') and STT_MODELS.get(model.removesuffix('.pt')):
                    add_speech_to_text_model(model.removesuffix('.pt'))

        # Text to Speech
        tts_model_path = os.path.join(cache_dir, 'huggingface', 'hub')
        if os.path.isdir(tts_model_path) and any([d for d in os.listdir(tts_model_path) if 'Kokoro' in d]):
            # Kokoro has a directory
            tts_model_path = os.path.join(tts_model_path, [d for d in os.listdir(tts_model_path) if 'Kokoro' in d][0], 'snapshots')
            if os.path.isdir(tts_model_path) and len(os.listdir(tts_model_path)) > 0:
                # Kokoro has snapshots
                tts_model_path = os.path.join(tts_model_path, os.listdir(tts_model_path)[0], 'voices')
                if os.path.isdir(tts_model_path):
                    # Kokoro has voices
                    for model in os.listdir(tts_model_path):
                        pretty_name = [k for k, v in TTS_VOICES.items() if v == model.removesuffix('.pt')]
                        if len(pretty_name) > 0:
                            pretty_name = pretty_name[0]
                            add_text_to_speech_model(pretty_name)

    available_models = window.get_current_instance().get_available_models()
    MODELSTEST.added.available_models = available_models
    # Normal Models
    threads=[]
    window.get_current_instance().local_models = None # To reset cache
    local_models = window.get_current_instance().get_local_models()
    for model in local_models:
        model_element = MODELSTEST.added.AddedModelButton(model.get('name'), window.get_current_instance())
        window.local_model_flowbox.prepend(model_element)
        GLib.idle_add(window.model_dropdown.get_model().append,model_element.row)
        model_element.get_parent().set_focusable(False)
    window.title_stack.set_visible_child_name('model-selector' if len(get_local_models()) > 0 else 'no-models')
    window.local_model_stack.set_visible_child_name('content' if len(list(window.local_model_flowbox)) > 0 else 'no-models')
    window.model_dropdown.set_enable_search(len(local_models) > 10)
    GLib.idle_add(window.auto_select_model)

def update_available_model_list():
    global available_models
    window.available_model_flowbox.remove_all()
    available_models = window.get_current_instance().get_available_models()
    MODELSTEST.added.available_models = available_models

    # Category Filter
    window.model_filter_button.set_visible(len(available_models) > 0)
    container = Gtk.Box(
        orientation=1,
        spacing=5
    )
    if len(available_models) > 0:
        for name, category in MODELSTEST.common.CategoryPill.metadata.items():
            if category.get('name') and (name != 'embedding' or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1'):
                pill_container = Gtk.Box(
                    spacing=5,
                    halign=3
                )
                icon = Gtk.Image.new_from_icon_name(category.get('icon', 'language-symbolic'))
                icon.set_css_classes(category.get('css', []))
                pill_container.append(icon)
                pill_container.append(Gtk.Label(label=category.get('name')))
                checkbtn = Gtk.CheckButton(
                    child=pill_container,
                    name=name
                )
                checkbtn.connect('toggled', lambda *_: window.model_search_changed(window.searchentry_models))
                container.append(checkbtn)
    window.model_filter_button.set_popover(
        Gtk.Popover(
            child=container,
            has_arrow=True
        )
    )

    for name, model_info in available_models.items():
        if 'small' in model_info['categories'] or 'medium' in model_info['categories'] or 'big' in model_info['categories'] or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
            if 'embedding' not in model_info['categories'] or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
                model_element = MODELSTEST.available.AvailableModelButton(name, model_info)
                window.available_model_flowbox.append(model_element)
                model_element.get_parent().set_focusable(False)
    window.get_application().lookup_action('download_model_from_name').set_enabled(len(available_models) > 0)
    window.available_models_stack_page.set_visible(len(available_models) > 0)
    window.model_creator_stack_page.set_visible(len(available_models) > 0)
    visible_model_manger_switch = len([p for p in window.model_manager_stack.get_pages() if p.get_visible()]) > 1
    window.model_manager_bottom_view_switcher.set_visible(visible_model_manger_switch)
    window.model_manager_top_view_switcher.set_visible(visible_model_manger_switch)

def get_local_models() -> dict:
    results = {}
    for model in [item.get_child() for item in list(window.local_model_flowbox) if isinstance(item.get_child(), MODELSTEST.added.AddedModelButton)]:
        results[model.get_name()] = model
    return results

def pull_model_confirm(model_name:str):
    if model_name:
        model_name = model_name.strip().replace('\n', '')
        if model_name not in list(get_local_models().keys()):
            model = PullingModel(model_name, add_local_model)
            window.local_model_flowbox.prepend(model)
            GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'added_models')
            GLib.idle_add(window.local_model_flowbox.select_child, model.get_parent())
            GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
            window.get_current_instance().pull_model(model_name, model.update_progressbar)

def pull_model(row, icon):
    model_name = row.get_name()
    row.remove(icon)
    row.add_suffix(Gtk.Image.new_from_icon_name('check-plain-symbolic'))
    row.set_sensitive(False)
    threading.Thread(target=pull_model_confirm, args=(model_name,)).start()

def create_model_confirm(data:dict, gguf_path:str):
    if data.get('model') and data.get('model') not in list(get_local_models().keys()):
        model = PullingModel(data.get('model'), add_local_model)
        window.local_model_flowbox.prepend(model)
        GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'added_models')
        GLib.idle_add(window.local_model_flowbox.select_child, model.get_parent())
        GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
        if gguf_path:
            try:
                with open(gguf_path, 'rb', buffering=0) as f:
                    model.update_progressbar({'status': 'Generating sha256'})
                    sha256 = hashlib.file_digest(f, 'sha256').hexdigest()

                if not window.get_current_instance().gguf_exists(sha256):
                    model.update_progressbar({'status': 'Uploading GGUF to Ollama instance'})
                    window.get_current_instance().upload_gguf(gguf_path, sha256)
                    data['files'] = {os.path.split(gguf_path)[1]: 'sha256:{}'.format(sha256)}
            except Exception as e:
                logger.error(e)
                GLib.idle_add(window.local_model_flowbox.remove, model.get_parent())
                return
        window.get_current_instance().create_model(data, model.update_progressbar)

def create_model(data:dict, gguf_path:str=None):
    threading.Thread(target=create_model_confirm, args=(data, gguf_path)).start()

class FallbackModel:
    def get_name():
        return None

    def get_vision() -> bool:
        return False

def get_selected_model():
    selected_item = window.model_dropdown.get_selected_item()
    if selected_item:
        return selected_item.model
    else:
        return FallbackModel

