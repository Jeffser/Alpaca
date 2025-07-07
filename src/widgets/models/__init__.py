# __init__.py
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
from . import added, available, pulling, common, speech, creator
from .common import set_available_models_data, get_available_models_data

import os, importlib.util
from ...constants import data_dir, cache_dir, STT_MODELS, TTS_VOICES

def update_available_model_list(root):
    window = root.get_application().main_alpaca_window
    window.available_model_flowbox.remove_all()
    set_available_models_data(window.get_current_instance().get_available_models())
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
        if len(model_info.get('categories', [])) == 0 or 'small' in model_info.get('categories', []) or 'medium' in model_info.get('categories', []) or 'big' in model_info.get('categories', []) or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
            if 'embedding' not in model_info.get('categories', []) or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
                model_element = available.AvailableModelButton(name, model_info)
                window.available_model_flowbox.append(model_element)
                model_element.get_parent().set_focusable(False)

    window.get_application().lookup_action('download_model_from_name').set_enabled(len(available_models_data) > 0)
    window.available_models_stack_page.set_visible(len(available_models_data) > 0)
    window.model_creator_stack_page.set_visible(len(available_models_data) > 0)
    visible_model_manger_switch = len([p for p in window.model_manager_stack.get_pages() if p.get_visible()]) > 1
    window.model_manager_bottom_view_switcher.set_visible(visible_model_manger_switch)
    window.model_manager_top_view_switcher.set_visible(visible_model_manger_switch)

def update_added_model_list(root):
    window = root.get_application().main_alpaca_window
    window.local_model_flowbox.remove_all()
    GLib.idle_add(window.model_dropdown.get_model().remove_all)

    if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
        # Speech to Text
        if os.path.isdir(os.path.join(data_dir, 'whisper')):
            for model in os.listdir(os.path.join(data_dir, 'whisper')):
                if model.endswith('.pt') and STT_MODELS.get(model.removesuffix('.pt')):
                    model_element = speech.SpeechToTextModelButton(model.removesuffix('.pt'))
                    window.local_model_flowbox.prepend(model_element)

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
                            model_element = speech.TextToSpeechModelButton(pretty_name[0])
                            window.local_model_flowbox.prepend(model_element)

    # Normal Models
    threads=[]
    window.get_current_instance().local_models = None # To reset cache
    local_models = window.get_current_instance().get_local_models()
    for model in local_models:
        model_element = added.AddedModelButton(model.get('name'), window.get_current_instance())
        window.local_model_flowbox.prepend(model_element)
        GLib.idle_add(window.model_dropdown.get_model().append,model_element.row)
        model_element.get_parent().set_focusable(False)
    window.title_stack.set_visible_child_name('model-selector' if len(common.get_local_models(window)) > 0 else 'no-models')
    window.local_model_stack.set_visible_child_name('content' if len(list(window.local_model_flowbox)) > 0 else 'no-models')
    window.model_dropdown.set_enable_search(len(local_models) > 10)
    GLib.idle_add(window.auto_select_model)
