#generic_actions.py
"""
Working on organizing the code
"""

import gi
from gi.repository import GLib
import os, requests, re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from html2text import html2text

from .constants import AlpacaFolders
from .custom_widgets import model_manager_widget
from .internal import cache_dir

window = None

def attach_file(file):
    file_types = {
        "plain_text": ["txt", "md"],
        "code": ["c", "h", "css", "html", "js", "ts", "py", "java", "json", "xml", "asm", "nasm",
                "cs", "csx", "cpp", "cxx", "cp", "hxx", "inc", "csv", "lsp", "lisp", "el", "emacs",
                "l", "cu", "dockerfile", "glsl", "g", "lua", "php", "rb", "ru", "rs", "sql", "sh", "p8",
                "yaml"],
        "image": ["png", "jpeg", "jpg", "webp", "gif"],
        "pdf": ["pdf"],
        "odt": ["odt"],
        "docx": ["docx"],
        "pptx": ["pptx"],
        "xlsx": ["xlsx"]
    }
    if file.query_info("standard::content-type", 0, None).get_content_type() == 'text/plain':
        extension = 'txt'
    else:
        extension = file.get_path().split(".")[-1]
    found_types = [key for key, value in file_types.items() if extension in value]
    if len(found_types) == 0:
        file_type = 'plain_text'
    else:
        file_type = found_types[0]
    if file_type == 'image' and not model_manager_widget.get_selected_model().get_vision():
        window.show_toast(_("Image recognition is only available on specific models"), window.main_overlay)
        return
    window.attach_file(file.get_path(), file_type)
