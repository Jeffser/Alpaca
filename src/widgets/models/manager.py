# manager.py

from gi.repository import Gtk, Adw, GLib
from . import added, basic, common

import os, importlib.util, re
from ...constants import data_dir, STT_MODELS, TTS_VOICES, REMBG_MODELS, MODEL_CATEGORIES_METADATA

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
        common.set_available_models_data(instance.get_available_models())
        available_models_data = common.get_available_models_data()

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
                    icon.add_css_class('category-filter-{}'.format(category.get('color', 'slate')))
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
            # order categories
            model_info['categories'] = list(set(model_info.get('categories', [])))
            order_reference = list(MODEL_CATEGORIES_METADATA.keys())
            model_info['categories'].sort(key=lambda x: order_reference.index(x) if x in order_reference else len(order_reference))
            if 'huge' not in model_info.get('categories') or 'small' in model_info.get('categories') or 'medium' in model_info.get('categories') or 'big' in model_info.get('categories') or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
                if 'embedding' not in model_info.get('categories') or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
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
            self.create_added_model(
                model_name=model.get('name'),
                instance=instance,
                data=model
            )

        if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
            # Speech to Text
            if os.path.isdir(os.path.join(data_dir, 'whisper')):
                for model in os.listdir(os.path.join(data_dir, 'whisper')):
                    if model.endswith('.pt') and STT_MODELS.get(model.removesuffix('.pt')):
                        self.create_stt_model(model)

            # Text to Speech
            tts_model_path = common.get_tts_path()
            if tts_model_path:
                for model in os.listdir(tts_model_path):
                    self.create_tts_model(os.path.join(tts_model_path, model))


        # Background Removers
        if importlib.util.find_spec('rembg'):
            model_dir = os.path.join(data_dir, '.u2net')
            if os.path.isdir(model_dir):
                for model in os.listdir(model_dir):
                    if model.endswith('.onnx') and REMBG_MODELS.get(model.removesuffix('.onnx')):
                        self.create_background_remover_model(os.path.join(model_dir, model))

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
            category_filter = len(filtered_categories) == 0 or model.get_child().get_search_categories() & filtered_categories or not self.searchbar.get_search_mode()
            model.set_visible(string_search and category_filter)

        for model in list(self.available_model_flowbox):
            string_search = re.search(query, model.get_child().get_search_string(), re.IGNORECASE)
            category_filter = len(filtered_categories) == 0 or model.get_child().get_search_categories() & filtered_categories or not self.searchbar.get_search_mode()
            model.set_visible(string_search and category_filter)

        self.update_added_visibility()
        self.update_available_visibility()

    @Gtk.Template.Callback()
    def explore_available_models(self, button):
        self.view_stack.set_visible_child_name('available_models')

    @Gtk.Template.Callback()
    def open_instance_manager(self, button):
        self.get_root().main_navigation_view.push_by_tag('instance_manager')

    def create_added_model(self, model_name:str, instance, append_row:bool=True, data:dict={}):
        model_element = basic.BasicModelButton(
            model_name=model_name,
            instance=instance,
            dialog_callback=added.AddedModelDialog,
            remove_callback=common.remove_added_model,
            data=data
        )
        if append_row:
            added.append_to_model_selector(model_element.row)
        self.added_model_flowbox.prepend(model_element)
        model_element.get_parent().set_focusable(False)
        self.update_added_visibility()
        return model_element

    def create_stt_model(self, model_name:str):
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
            remove_callback=common.remove_stt_model
        )
        self.added_model_flowbox.append(model_element)
        model_element.get_parent().set_focusable(False)
        self.update_added_visibility()
        return model_element

    def create_tts_model(self, model_path:str):
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
            remove_callback=lambda model, path=model_path: common.remove_tts_model(model, path)
        )
        self.added_model_flowbox.append(model_element)
        model_element.get_parent().set_focusable(False)
        self.update_added_visibility()
        return model_element

    def create_background_remover_model(self, model_path:str):
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
            remove_callback=lambda model, path=model_path: common.remove_background_remover_model(model, path)
        )
        self.added_model_flowbox.append(model_element)
        model_element.get_parent().set_focusable(False)
        self.update_added_visibility()
        return model_element

