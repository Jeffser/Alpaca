# common.py

from gi.repository import Gtk, Gio, Adw
import importlib.util, os, threading
from .. import dialog
from ...constants import data_dir, cache_dir, STT_MODELS, TTS_VOICES, REMBG_MODELS
from ...sql_manager import prettify_model_name, Instance as SQL

available_models_data = {}

class CategoryPill(Adw.Bin):
    __gtype_name__ = 'AlpacaCategoryPill'

    metadata = {
        'multilingual': {'name': _('Multilingual'), 'css': ['accent'], 'icon': 'language-symbolic'},
        'code': {'name': _('Code'), 'css': ['accent'], 'icon': 'code-symbolic'},
        'math': {'name': _('Math'), 'css': ['accent'], 'icon': 'accessories-calculator-symbolic'},
        'vision': {'name': _('Vision'), 'css': ['accent'], 'icon': 'eye-open-negative-filled-symbolic'},
        'embedding': {'name': _('Embedding'), 'css': ['error'], 'icon': 'brain-augemnted-symbolic'},
        'tools': {'name': _('Tools'), 'css': ['accent'], 'icon': 'wrench-wide-symbolic'},
        'reasoning': {'name': _('Reasoning'), 'css': ['accent'], 'icon': 'brain-augemnted-symbolic'},
        'cloud': {'name': _('Cloud'), 'css': ['accent'], 'icon': 'cloud-filled-symbolic'},
        'small': {'name': _('Small'), 'css': ['success'], 'icon': 'leaf-symbolic'},
        'medium': {'name': _('Medium'), 'css': ['brown'], 'icon': 'sprout-symbolic'},
        'big': {'name': _('Big'), 'css': ['warning'], 'icon': 'tree-circle-symbolic'},
        'huge': {'name': _('Huge'), 'css': ['error'], 'icon': 'weight-symbolic'},
        'language': {'css': [], 'icon': 'language-symbolic'}
    }

    def __init__(self, name_id:str, show_label:bool):
        if 'language:' in name_id:
            self.metadata['language']['name'] = name_id.split(':')[1]
            name_id = 'language'
        button_content = Gtk.Box(
            spacing=5,
            halign=3
        )
        button_content.append(Gtk.Image.new_from_icon_name(self.metadata.get(name_id, {}).get('icon', 'language-symbolic')))
        if show_label:
            button_content.append(Gtk.Label(
                label='<span weight="bold">{}</span>'.format(self.metadata.get(name_id, {}).get('name')),
                use_markup=True
            ))
        super().__init__(
            css_classes=['subtitle', 'category_pill'] + self.metadata.get(name_id, {}).get('css', []),
            tooltip_text=self.metadata.get(name_id, {}).get('name'),
            child=button_content,
            halign=0 if show_label else 1,
            focusable=False,
            hexpand=True
        )

def get_available_models_data() -> list:
    global available_models_data
    return available_models_data

def set_available_models_data(data:list):
    global available_models_data
    available_models_data = data

def prepend_added_model(root, model):
    window = root.get_application().get_main_window(present=False)
    window.local_model_flowbox.prepend(model)
    model.get_parent().set_focusable(False)

def append_added_model(root, model):
    window = root.get_application().get_main_window(present=False)
    window.local_model_flowbox.append(model)
    model.get_parent().set_focusable(False)

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

# Callbacks for removing models
def remove_added_model(model):
    window = model.get_root().get_application().get_main_window(present=False)

    if model.instance.delete_model(model.get_name()):
        if len(list(model.get_ancestor(Gtk.FlowBox))) == 1:
            window.local_model_stack.set_visible_child_name('no-models')

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
