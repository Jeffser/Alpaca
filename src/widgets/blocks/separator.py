# separator.py
"""
Separator
"""

from gi.repository import Gtk

class Separator(Gtk.Separator):
    __gtype_name__ = 'AlpacaSeparator'

    def __init__(self, content:str):
        self.content = content
        super().__init__(
            margin_top=10,
            margin_bottom=10
        )

    def get_content(self) -> str:
        return self.content
