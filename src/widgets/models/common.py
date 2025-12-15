# common.py

from gi.repository import Gtk, Gio, Adw
import importlib.util, os, threading
from .. import dialog
from ...constants import data_dir, cache_dir, STT_MODELS, TTS_VOICES, REMBG_MODELS, MODEL_CATEGORIES_METADATA
from ...sql_manager import prettify_model_name, Instance as SQL

available_models_data = {}

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/info_box.ui')
class InfoBox(Gtk.Box):
    __gtype_name__ = 'AlpacaInformationBox'

    title_label = Gtk.Template.Child()
    description_label = Gtk.Template.Child()

    def __init__(self, title:str, description:str, single_line_description:bool):
        super().__init__(
            name=title
        )
        self.title_label.set_label(title)
        self.title_label.set_tooltip_text(title)
        self.description_label.set_label(description)
        self.description_label.set_tooltip_text(description)
        self.description_label.set_wrap(not single_line_description)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/category_pill.ui')
class CategoryPill(Gtk.Box):
    __gtype_name__ = 'AlpacaCategoryPill'

    image = Gtk.Template.Child()
    label = Gtk.Template.Child()

    def __init__(self, category_id:str, show_label:bool):
        category_name = MODEL_CATEGORIES_METADATA.get(category_id, {}).get('name')
        category_icon = MODEL_CATEGORIES_METADATA.get(category_id, {}).get('icon', 'language-symbolic')
        super().__init__(
            tooltip_text=category_name
        )
        if category_id.startswith('language:'):
            category_name = category_id.split(':')[1]

        self.image.set_from_icon_name(category_icon)
        self.label.set_label('<span weight="bold">{}</span>'.format(category_name))
        self.label.set_visible(show_label)

        for css in MODEL_CATEGORIES_METADATA.get(category_id, {}).get('css', []):
            self.add_css_class(css)

def get_available_models_data() -> list:
    global available_models_data
    return available_models_data

def set_available_models_data(data:list):
    global available_models_data
    available_models_data = data

def prepend_added_model(root, model):
    window = root.get_application().get_main_window(present=False)
    window.model_manager.added_model_flowbox.prepend(model)
    model.get_parent().set_focusable(False)
    window.model_manager.update_added_visibility()

def append_added_model(root, model):
    window = root.get_application().get_main_window(present=False)
    window.model_manager.added_model_flowbox.append(model)
    model.get_parent().set_focusable(False)
    window.model_manager.update_added_visibility()

def prompt_gguf(root, instance=None):
    creator = importlib.import_module('alpaca.widgets.models.creator')
    if not instance:
        instance = root.get_application().get_main_window(present=False).get_current_instance()

    def result(file):
        try:
            file_path = file.get_path()
        except Exception as e:
            return
        creator.ModelCreatorDialog(instance, None, file_path).present(root)

    file_filter = Gtk.FileFilter()
    file_filter.add_suffix('gguf')
    dialog.simple_file(
        parent = root,
        file_filters = [file_filter],
        callback = result
    )

def prompt_existing(root, instance=None, row=None):
    creator = importlib.import_module('alpaca.widgets.models.creator')
    if not instance:
        instance = root.get_application().get_main_window(present=False).get_current_instance()
    creator.ModelCreatorDialog(instance, row, None).present(root)

def tts_model_exists(model_name:str) -> bool:
    tts_model_path = get_tts_path()
    if tts_model_path:
        for model in os.listdir(tts_model_path):
            if model_name == model.removesuffix('.pt'):
                return True
    return False

def get_tts_path() -> str or None:
    tts_model_path = os.path.join(cache_dir, 'huggingface', 'hub')
    if os.path.isdir(tts_model_path) and any([d for d in os.listdir(tts_model_path) if 'Kokoro' in d]):
        tts_model_path = os.path.join(tts_model_path, [d for d in os.listdir(tts_model_path) if 'Kokoro' in d][0], 'snapshots')
        if os.path.isdir(tts_model_path) and len(os.listdir(tts_model_path)) > 0:
            tts_model_path = os.path.join(tts_model_path, os.listdir(tts_model_path)[0], 'voices')
            if os.path.isdir(tts_model_path):
                return tts_model_path

# Creating models
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

# Callbacks for removing models
def remove_added_model(model):
    window = model.get_root().get_application().get_main_window(present=False)

    if model.instance.delete_model(model.get_name()):

        SQL.remove_model_preferences(model.get_name())
        threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures, daemon=True).start()

def remove_stt_model(model):
    model_path = os.path.join(data_dir, 'whisper', '{}.pt'.format(model.get_name()))
    if os.path.isfile(model_path):
        os.remove(model_path)

def remove_tts_model(model, file_path:str):
    print(file_path)
    if os.path.islink(file_path):
        target_path = os.readlink(file_path)
        os.unlink(file_path)
        if os.path.isfile(target_path):
            os.remove(target_path)
    elif os.path.isfile(file_path):
        os.remove(file_path)

def remove_background_remover_model(model, file_path:str):
    if os.path.isfile(file_path):
        os.remove(file_path)
