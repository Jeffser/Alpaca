# text.py
"""
Text blocks with PangoMarkup styling
"""

import gi
from gi.repository import GLib, Gtk, Gdk

import re, unicodedata
from ..message import Message

def markdown_to_pango(text:str) -> str:
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
    return text

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/generating_text.ui')
class GeneratingText(Gtk.Overlay):
    __gtype_name__ = 'AlpacaGeneratingText'

    textview = Gtk.Template.Child()
    buffer = Gtk.Template.Child()

    def __init__(self, content:str=None):
        super().__init__()
        self.textview.remove_css_class('view')
        if content:
            self.set_content(content)

    def process_content(self, value:str) -> None:
        current_text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        if value.endswith('\n'):
            think_block_complete = not current_text.strip().startswith('<think>') or current_text.strip().endswith('</think>')
            think_block_complete_v2 = not current_text.strip().startswith('<|begin_of_thought|>') or current_text.strip().endswith('<|end_of_thought|>')
            code_block_complete = not current_text.strip().startswith('```') or (current_text.strip().endswith('```') and len(current_text.strip()) > 3)
            table_block_complete = not current_text.strip().startswith('|') or '|\n\n' in current_text

            if think_block_complete and think_block_complete_v2 and code_block_complete and table_block_complete:
                self.set_content()
                self.get_parent().add_content(current_text)
        elif not self.get_parent().message.popup.tts_button.get_active() and '.' in current_text and (self.get_parent().message.get_root().settings.get_value('tts-auto-dictate').unpack() or self.get_parent().message.get_root().get_name() == 'AlpacaLiveChat'):
            self.get_parent().message.popup.tts_button.set_active(True)

    def append_content(self, value:str) -> None:
        text = GLib.markup_escape_text(value)
        self.buffer.insert_markup(self.buffer.get_end_iter(), text, len(text.encode('utf-8')))
        self.process_content(value)

    def get_content(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def set_content(self, value:str=None) -> None:
        self.buffer.delete(self.buffer.get_start_iter(), self.buffer.get_end_iter())
        if value:
            self.append_content(value)

    def get_content_for_dictation(self) -> str:
        raw_text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        if raw_text:
            allowed_characters = ('\n', ',', '.', ':', ';', '+', '/', '-', '(', ')', '[', ']', '=', '<', '>', '’', '\'', '"', '¿', '?', '¡', '!')
            cleaned_text = ''.join(c for c in raw_text if unicodedata.category(c).startswith(('L', 'N', 'Zs')) or c in allowed_characters)
            lines = []
            for line in cleaned_text.split('\n'):
                if line and line.strip() not in allowed_characters:
                    lines.append(line)
            return '\n'.join(lines)
        return ''

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/editing_text.ui')
class EditingText(Gtk.Box):
    __gtype_name__ = 'AlpacaEditingText'

    textview = Gtk.Template.Child()

    def set_content(self, content:str):
        self.textview.get_buffer().set_text(content, len(content.encode('utf8')))

    @Gtk.Template.Callback()
    def enter_key_handler(self, controller, keyval, keycode, state):
        if keyval==Gdk.KEY_Return and state & Gdk.ModifierType.CONTROL_MASK:
            self.save_edit()

    @Gtk.Template.Callback()
    def cancel_edit(self, button=None):
        message = self.get_ancestor(Message)
        message.set_halign(2 if message.mode == 0 else 0)
        self.set_visible(False)
        message.popup.change_status(True)
        message.main_stack.set_visible_child_name('content')

    @Gtk.Template.Callback()
    def save_edit(self, button=None):
        message = self.get_ancestor(Message)
        buffer = self.textview.get_buffer()
        GLib.idle_add(message.block_container.set_content, buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False))
        message.set_halign(2 if message.mode == 0 else 0)
        self.set_visible(False)
        message.popup.change_status(True)
        message.main_stack.set_visible_child_name('content')
        GLib.idle_add(message.save)
        response_index = list(message.get_parent()).index(message) + 1
        if len(list(message.get_parent())) > response_index:
            next_message = list(message.get_parent())[response_index]
            if next_message.mode == 1 and next_message.get_root().settings.get_value('regenerate-after-edit').unpack():
                next_message.popup.regenerate_message()

class Text(Gtk.Label):
    __gtype_name__ = 'AlpacaText'

    def __init__(self, content:str=None):
        super().__init__(
            hexpand=True,
            halign=0,
            wrap=True,
            wrap_mode=2,
            focusable=True,
            selectable=True,
            xalign=0,
            css_classes=['lh']
        )
        self.raw_text=""
        if content:
            self.set_content(content)

    def append_content(self, value:str) -> None:
        self.raw_text += value
        self.set_content(self.raw_text)

    def get_content(self) -> str:
        return self.raw_text

    def get_content_for_dictation(self) -> str:
        if self.raw_text:
            allowed_characters = ('\n', ',', '.', ':', ';', '+', '/', '-', '(', ')', '[', ']', '=', '<', '>', '’', '\'', '"', '¿', '?', '¡', '!')
            cleaned_text = ''.join(c for c in self.raw_text if unicodedata.category(c).startswith(('L', 'N', 'Zs')) or c in allowed_characters)
            lines = []
            for line in cleaned_text.split('\n'):
                if line and line.strip() not in allowed_characters:
                    lines.append(line)
            return '\n'.join(lines)
        return ''

    def set_content(self, value:str) -> None:
        self.raw_text = value
        self.set_markup(markdown_to_pango(self.raw_text))

