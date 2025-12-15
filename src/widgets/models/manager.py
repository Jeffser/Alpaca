# manager.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
from . import added, common, creator, basic, manager
from .common import set_available_models_data, get_available_models_data, remove_added_model, remove_stt_model, remove_tts_model, remove_background_remover_model

import os, importlib.util, re
from ...constants import data_dir, cache_dir, STT_MODELS, TTS_VOICES, REMBG_MODELS, MODEL_CATEGORIES_METADATA

def create_added_model(model_name:str, instance, append_row=True):
    model_element = basic.BasicModelButton(
        model_name=model_name,
        instance=instance,
        dialog_callback=added.AddedModelDialog,
        remove_callback=remove_added_model
    )
    if append_row:
        added.append_to_model_selector(model_element.row)
    return model_element

def create_stt_model(model_name:str):
    model_element = basic.BasicModelButton(
        model_name=model_name.removesuffix('.pt'),
        subtitle=_("Speech to Text"),
        icon_name="audio-input-microphone-symbolic",
        dialog_callback=lambda model: basic.BasicModelDialog(
            model=model,
            description=_("Local speech to text model provided by OpenAI Whisper"),
            size=STT_MODELS.get(model.get_name(), '~151mb'),
            url="https://github.com/openai/whisper"
        ),
        remove_callback=remove_stt_model
    )
    return model_element

def create_tts_model(model_path:str):
    model_name = os.path.basename(model_path).removesuffix('.pt')
    pretty_name = [k for k, v in TTS_VOICES.items() if v == model_name]
    if len(pretty_name) > 0:
        pretty_name = pretty_name[0]
    else:
        pretty_name = model_name.title()

    model_element = basic.BasicModelButton(
        model_name=pretty_name,
        subtitle=_("Text to Speech"),
        icon_name="bullhorn-symbolic",
        dialog_callback=lambda model: basic.BasicModelDialog(
            model=model,
            description=_("Local text to speech model provided by Kokoro"),
            url="https://github.com/hexgrad/kokoro"
        ),
        remove_callback=lambda model, path=model_path: remove_tts_model(model, path)
    )
    return model_element

def create_background_remover_model(model_path:str):
    model_name = os.path.basename(model_path).removesuffix('.onnx')
    author = REMBG_MODELS.get(model_name, {}).get('author')
    size = REMBG_MODELS.get(model_name, {}).get('size', '~151mb')
    url = REMBG_MODELS.get(model_name, {}).get('link')

    model_element = basic.BasicModelButton(
        model_name=REMBG_MODELS.get(model_name, {}).get('display_name', model_name.title()),
        subtitle=_("Background Remover"),
        icon_name="image-missing-symbolic",
        dialog_callback=lambda model, author=author, size=size, url=url: basic.BasicModelDialog(
            model=model,
            description=_("Local background removal model provided by {}.").format(author) if author else "",
            size=size,
            url=url
        ),
        remove_callback=lambda model, path=model_path: remove_background_remover_model(model, path)
    )
    return model_element

def get_tts_path() -> str or None:
    tts_model_path = os.path.join(cache_dir, 'huggingface', 'hub')
    if os.path.isdir(tts_model_path) and any([d for d in os.listdir(tts_model_path) if 'Kokoro' in d]):
        tts_model_path = os.path.join(tts_model_path, [d for d in os.listdir(tts_model_path) if 'Kokoro' in d][0], 'snapshots')
        if os.path.isdir(tts_model_path) and len(os.listdir(tts_model_path)) > 0:
            tts_model_path = os.path.join(tts_model_path, os.listdir(tts_model_path)[0], 'voices')
            if os.path.isdir(tts_model_path):
                return tts_model_path

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/model_manager.ui')
class ModelManager(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaModelManager'

    header_bar = Gtk.Template.Child()
    searchbar = Gtk.Template.Child()
    searchentry = Gtk.Template.Child()
    bottom_view_switcher = Gtk.Template.Child()
    added_model_flowbox = Gtk.Template.Child()
    available_model_flowbox = Gtk.Template.Child()
    view_stack = Gtk.Template.Child()
    added_model_stack = Gtk.Template.Child()
    available_model_stack = Gtk.Template.Child()
    filter_button = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.searchbar.connect_entry(self.searchentry)
        GLib.idle_add(self.set_breakpoint)

    def set_breakpoint(self):
        win_bp = self.get_root().small_breakpoint

        win_bp.add_setter(
            self.header_bar,
            'title-widget',
            Gtk.Label(
                label=_("Model Manager"),
                css_classes=["title"]
            )
        )
        win_bp.add_setter(
            self.bottom_view_switcher,
            'reveal',
            True
        )
        win_bp.add_setter(
            self.added_model_flowbox,
            'max-children-per-line',
            2
        )
        win_bp.add_setter(
            self.available_model_flowbox,
            'min-children-per-line',
            1
        )

    def update_available_visibility(self):
        for btn in list(self.available_model_flowbox):
            if btn.get_visible():
                self.available_model_stack.set_visible_child_name('content')
                return
        if self.get_root().get_current_instance().instance_type == 'empty':
            self.available_model_stack.set_visible_child_name('no-results' if len(list(self.available_model_flowbox)) > 0 else 'no-instances')
        else:
            self.available_model_stack.set_visible_child_name('no-results' if len(list(self.available_model_flowbox)) > 0 else 'no-models')

    def update_added_visibility(self):
        for btn in list(self.added_model_flowbox):
            if btn.get_visible():
                self.added_model_stack.set_visible_child_name('content')
                return
        self.added_model_stack.set_visible_child_name('no-results' if len(list(self.added_model_flowbox)) > 0 else 'no-models')

    def update_available_model_list(self):
        self.available_model_flowbox.remove_all()
        instance = self.get_root().get_current_instance()
        set_available_models_data(instance.get_available_models())
        available_models_data = get_available_models_data()

        # Filter
        self.filter_button.set_visible(len(available_models_data) > 0)
        container = Gtk.Box(
            orientation=1,
            spacing=5
        )
        if len(available_models_data) > 0:
            for name, category in MODEL_CATEGORIES_METADATA.items():
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
                    checkbtn.connect('toggled', lambda *_: self.search_changed(self.searchentry))
                    container.append(checkbtn)
        self.filter_button.set_popover(
            Gtk.Popover(
                child=container,
                has_arrow=True
            )
        )

        # Available Model List
        for name, model_info in available_models_data.items():
            if 'huge' not in model_info.get('categories', []) or 'small' in model_info.get('categories', []) or 'medium' in model_info.get('categories', []) or 'big' in model_info.get('categories', []) or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
                if 'embedding' not in model_info.get('categories', []) or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
                    model_element = basic.BasicModelButton(
                        model_name=name,
                        subtitle=model_info.get('description'),
                        data=model_info,
                        dialog_callback=basic.AvailableModelDialog
                    )
                    self.available_model_flowbox.append(model_element)
                    model_element.get_parent().set_focusable(False)
        self.update_available_visibility()
        self.filter_button.set_visible('ollama' in instance.instance_type)

    def update_added_model_list(self):
        self.added_model_flowbox.remove_all()
        added.empty_model_selector()
        instance = self.get_root().get_current_instance()

        # Normal Models
        instance.local_models = None # Reset cache
        local_models = instance.get_local_models()
        for model in local_models:
            model_element = create_added_model(model.get('name'), instance)
            self.added_model_flowbox.append(model_element)
            model_element.get_parent().set_focusable(False)

        if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
            # Speech to Text
            if os.path.isdir(os.path.join(data_dir, 'whisper')):
                for model in os.listdir(os.path.join(data_dir, 'whisper')):
                    if model.endswith('.pt') and STT_MODELS.get(model.removesuffix('.pt')):
                        model_element = create_stt_model(model)
                        self.added_model_flowbox.append(model_element)
                        model_element.get_parent().set_focusable(False)

            # Text to Speech
            tts_model_path = get_tts_path()
            if tts_model_path:
                for model in os.listdir(tts_model_path):
                    model_element = create_tts_model(os.path.join(tts_model_path, model))
                    self.added_model_flowbox.append(model_element)
                    model_element.get_parent().set_focusable(False)

        # Background Removers
        if importlib.util.find_spec('rembg'):
            model_dir = os.path.join(data_dir, '.u2net')
            if os.path.isdir(model_dir):
                for model in os.listdir(model_dir):
                    if model.endswith('.onnx') and REMBG_MODELS.get(model.removesuffix('.onnx')):
                        model_path = os.path.join(model_dir, model)
                        model_element = create_background_remover_model(model_path)
                        self.added_model_flowbox.append(model_element)
                        model_element.get_parent().set_focusable(False)

        self.update_added_visibility()

    @Gtk.Template.Callback()
    def search_changed(self, entry):
        query = GLib.markup_escape_text(entry.get_text())
        results_added = False

        filtered_categories = set()
        if self.filter_button.get_popover():
            filtered_categories = set([c.get_name() for c in list(self.filter_button.get_popover().get_child()) if c.get_active()])

        for model in list(self.added_model_flowbox):
            string_search = re.search(query, model.get_child().get_search_string(), re.IGNORECASE)
            category_filter = len(filtered_categories) == 0 or model.get_child().get_search_categories() & filtered_categories or not self.model_searchbar.get_search_mode()
            model.set_visible(string_search and category_filter)

        for model in list(self.available_model_flowbox):
            string_search = re.search(query, model.get_child().get_search_string(), re.IGNORECASE)
            category_filter = len(filtered_categories) == 0 or model.get_child().get_search_categories() & filtered_categories or not self.model_searchbar.get_search_mode()
            model.set_visible(string_search and category_filter)

        self.update_added_visibility()
        self.update_available_visibility()

    @Gtk.Template.Callback()
    def explore_available_models(self, button):
        self.view_stack.set_visible_child_name('available_models')

    @Gtk.Template.Callback()
    def open_instance_manager(self, button):
        self.get_root().main_navigation_view.push_by_tag('instance_manager')
