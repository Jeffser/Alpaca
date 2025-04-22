# text.py
"""
Text blocks with PangoMarkup styling
"""

import gi
from gi.repository import GLib, Gtk

import re

def markdown_to_pango(self, text:str) -> str:
    """Converts Markdown text to a limited version of PangoMarkup"""
    text = GLib.markup_escape_text(text)
    text = text.replace("\n* ", "\n• ").replace("\n- ", "\n• ")
    text = text.replace("<|begin_of_solution|>", "")
    text = text.replace("<|end_of_solution|>", "")
    text = re.sub(r'`([^`\n]*?)`', r'<tt>\1</tt>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^####\s+(.*)', r'<span size="medium" weight="bold">\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.*)', r'<span size="large">\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.*)', r'<span size="x-large">\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s+(.*)', r'<span size="xx-large">\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'_(\((.*?)\)|\d+)', r'<sub>\2\1</sub>', text, flags=re.MULTILINE)
    text = re.sub(r'\^(\((.*?)\)|\d+)', r'<sup>\2\1</sup>', text, flags=re.MULTILINE)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text, flags=re.MULTILINE)
    return text.strip()

class Text(Gtk.Overlay):
    """Text block
    Use Text.Content = "" to set the text
    """

    __gtype_name__ = 'AlpacaText'

    def __init__(self, content:str=None, generating:bool=False):
        """Multipurpose text widget
        If `generating` then styling is added.
        """
        textview = Gtk.TextView(
            hexpand=True,
            halign=0,
            editable=False,
            wrap_mode=3,
            css_classes=['flat']
        )
        self.buffer = textview.get_buffer()
        super().__init__(
            child=textview
        )
        if generating:
            self.add_overlay(Gtk.Box(
                valign=2,
                halign=0,
                height_request=25,
                css_classes=['generating_text_shadow']
            ))
        if content:
            self.set_content(content)

    def append_content(self, value:str) -> None:
        text = markdown_to_pango(value)
        self.buffer.insert_markup(self.buffer.get_end_iter(), text, len(text.encode('utf-8')))

    def get_content(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def set_content(self, value:str) -> None:
        self.buffer.delete(self.buffer.get_start_iter(), self.buffer.get_end_iter())
        if value:
            self.append_content(value)
