# __init__.py
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
from . import added, available, pulling, common, speech, creator, image
from .common import set_available_models_data, get_available_models_data

import os, importlib.util
from ...constants import data_dir, cache_dir, STT_MODELS, TTS_VOICES, REMBG_MODELS

def update_available_model_list(root):
    window = root.get_application().get_main_window(present=False)
    window.available_model_flowbox.remove_all()
    instance = window.get_current_instance()
    set_available_models_data(instance.get_available_models())
    available_models_data = get_available_models_data()
    window.model_filter_button.set_visible(len(available_models_data) > 0)
    container = Gtk.Box(
        orientation=1,
        spacing=5
    )
    if len(available_models_data) > 0:
        for name, category in common.CategoryPill.metadata.items():
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

    for name, model_info in available_models_data.items():
        if 'huge' not in model_info.get('categories', []) or 'small' in model_info.get('categories', []) or 'medium' in model_info.get('categories', []) or 'big' in model_info.get('categories', []) or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
            if 'embedding' not in model_info.get('categories', []) or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
                model_element = available.AvailableModelButton(name, model_info)
                window.available_model_flowbox.append(model_element)
                model_element.get_parent().set_focusable(False)
    window.available_models_stack_page.set_visible(len(available_models_data) > 0)
    visible_model_manger_switch = len([p for p in window.model_manager_stack.get_pages() if p.get_visible()]) > 1
    window.model_manager_bottom_view_switcher.set_visible(visible_model_manger_switch)
    window.model_manager_top_view_switcher.set_visible(visible_model_manger_switch)
    window.model_filter_button.set_visible('ollama' in instance.instance_type)

def update_added_model_list(root):
    window = root.get_application().get_main_window(present=False)
    window.local_model_flowbox.remove_all()
    window.model_dropdown.get_model().remove_all()

    # Normal Models
    window.get_current_instance().local_models = None # To reset cache
    local_models = window.get_current_instance().get_local_models()
    for model in local_models:
        model_element = added.AddedModelButton(model.get('name'), window.get_current_instance())
        window.local_model_flowbox.append(model_element)
        window.model_dropdown.get_model().append(model_element.row)
        model_element.get_parent().set_focusable(False)

    if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
        # Speech to Text
        if os.path.isdir(os.path.join(data_dir, 'whisper')):
            for model in os.listdir(os.path.join(data_dir, 'whisper')):
                if model.endswith('.pt') and STT_MODELS.get(model.removesuffix('.pt')):
                    model_element = speech.SpeechToTextModelButton(model.removesuffix('.pt'))
                    window.local_model_flowbox.append(model_element)
                    model_element.get_parent().set_focusable(False)

        # Text to Speech
        tts_model_path = get_tts_path()
        if tts_model_path:
            for model in os.listdir(tts_model_path):
                model_element = speech.TextToSpeechModelButton(os.path.join(tts_model_path, model))
                window.local_model_flowbox.append(model_element)
                model_element.get_parent().set_focusable(False)

    # Background Removers
    if importlib.util.find_spec('rembg'):
        model_dir = os.path.join(data_dir, '.u2net')
        if os.path.isdir(model_dir):
            for model in os.listdir(model_dir):
                if model.endswith('.onnx') and REMBG_MODELS.get(model.removesuffix('.onnx')):
                    model_element = image.BackgroundRemoverModelButton(model.removesuffix('.onnx'))
                    window.local_model_flowbox.append(model_element)
                    model_element.get_parent().set_focusable(False)

    window.title_stack.set_visible_child_name('model-selector' if len(common.get_local_models(window)) > 0 else 'no-models')
    window.local_model_stack.set_visible_child_name('content' if len(list(window.local_model_flowbox)) > 0 else 'no-models')
    window.model_dropdown.set_enable_search(len(local_models) > 10)
    GLib.idle_add(window.chat_list_navigationview.get_visible_page().auto_select_model)

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
