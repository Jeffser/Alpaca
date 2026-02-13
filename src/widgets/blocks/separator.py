# separator.py
"""
Separator
"""

from gi.repository import Gtk

class Separator(Gtk.Separator):
    __gtype_name__ = 'AlpacaSeparator'

    def __init__(self):
        super().__init__()

    def get_content(self) -> str:
        return '---'

    def get_content_for_dictation(self) -> str:
        return ''
