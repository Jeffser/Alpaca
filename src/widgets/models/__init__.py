# __init__.py
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
from . import added, common, creator, basic, manager
from .common import set_available_models_data, get_available_models_data, remove_added_model, remove_stt_model, remove_tts_model, remove_background_remover_model
from ...sql_manager import Instance as SQL

import os, importlib.util
from ...constants import data_dir, cache_dir, STT_MODELS, TTS_VOICES, REMBG_MODELS, MODEL_CATEGORIES_METADATA

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
