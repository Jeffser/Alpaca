# added.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util, io, json
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, format_datetime, Instance as SQL
from .. import dialog, attachments, characters
from .common import CategoryPill, get_available_models_data, InfoBox
from .text import TextModelRow



