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

