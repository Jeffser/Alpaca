# code.py
"""
Code block handling
"""

from gi.repository import Gtk, Gdk, GtkSource
from .. import dialog, activities
from ...sql_manager import generate_uuid
import re, unicodedata

language_fallback = {
    'bash': 'sh',
    'cmd': 'powershell',
    'batch': 'powershell',
    'c#': 'csharp',
    'vb.net': 'vbnet',
    'python': 'python3',
    'javascript': 'js',
}

language_properties = (
    {
        'id': 'python',
        'aliases': ['python', 'python3', 'py', 'py3'],
        'filename': 'main.py'
    },
    {
        'id': 'mermaid',
        'aliases': ['mermaid'],
        'filename': 'index.html'
    },
    {
        'id': 'html',
        'aliases': ['html', 'htm'],
        'filename': 'index.html'
    },
    {
        'id': 'bash',
        'aliases': ['bash', 'sh'],
        'filename': 'script.sh'
    }
)

def get_language_property(language:str) -> dict:
    for properties in language_properties:
        if language.lower() in properties.get('aliases', []):
            return properties
    return {}

class Code(Gtk.Box):
    __gtype_name__ = 'AlpacaCode'

    def __init__(self, content:str=None, language:str=None):
        super().__init__(
            css_classes=["card", "code_block"],
            orientation=1,
            overflow=1,
            margin_start=5,
            margin_end=5
        )
        title_box = Gtk.Box(
            margin_start=12,
            margin_top=3,
            margin_bottom=3,
            margin_end=3,
            spacing=5
        )
        self.language_label = Gtk.Label(
            label=_("Code Block"),
            hexpand=True,
            xalign=0
        )
        title_box.append(self.language_label)

        # Buttons
        self.button_container = Gtk.Box(
            halign=2,
            css_classes=['linked']
        )
        title_box.append(self.button_container)

        self.edit_button = Gtk.Button(
            icon_name="edit-symbolic",
            tooltip_text=_("Edit Script"),
            css_classes=['flat']
        )
        self.edit_button.connect("clicked", lambda *_: self.begin_edit())
        self.button_container.append(self.edit_button)

        copy_button = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=_("Copy Script"),
            css_classes=['flat']
        )
        copy_button.connect("clicked", lambda *_: self.copy_code())
        self.button_container.append(copy_button)

        self.run_button = Gtk.Button(
            icon_name="execute-from-symbolic",
            tooltip_text=_("Run Script"),
            css_classes=['accent', 'flat'],
            visible=False
        )
        self.run_button.connect("clicked", lambda *_: self.run_script())
        self.button_container.append(self.run_button)

        self.append(title_box)
        self.append(Gtk.Separator())

        # Code view
        self.buffer = GtkSource.Buffer()
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))
        source_view = GtkSource.View(
            auto_indent=True,
            indent_width=4,
            buffer=self.buffer,
            show_line_numbers=True,
            editable=False,
            top_margin=6,
            bottom_margin=6,
            left_margin=12,
            right_margin=12,
            css_classes=["code_block"]
        )
        self.append(source_view)
        self.raw_language = language
        self.code_language = None
        if content:
            self.set_content(content)
        if self.raw_language:
            self.set_language(self.raw_language)

        self.activity_runner = None
        self.activity_edit = None

    def begin_edit(self) -> None:
        if self.activity_edit and self.activity_edit.get_root():
            self.activity_edit.reload()
        else:
            ce = activities.CodeEditor(
                language=get_language_property(self.get_language()).get('id'),
                code_getter=self.get_code,
                save_func=self.save_edit
            )
            self.activity_edit = activities.show_activity(ce, self.get_root())

    def save_edit(self, code:str) -> None:
        self.buffer.set_text(code, len(code.encode('utf-8')))
        self.get_parent().message.save()

    def copy_code(self) -> None:
        clipboard = Gdk.Display().get_default().get_clipboard()
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        clipboard.set(text)
        dialog.show_toast(_("Code copied to the clipboard"), self.get_root())

    def run_script(self) -> None:
        if self.activity_runner and self.activity_runner.get_root():
            self.activity_runner.reload()
        else:
            extra_files = []
            for blk in [blk for blk in list(self.get_parent().message.block_container) if isinstance(blk, Code) and blk.get_language().lower() in ('css', 'javascript', 'js') and blk != self]:
                blk_language = blk.get_language().lower()
                blk_code = blk.get_code()
                extra_files.append({
                    'language': blk_language,
                    'code': blk_code
                })

            cr = activities.CodeRunner(
                code_getter=self.get_code,
                language=get_language_property(self.get_language()).get('id'),
                extra_files=extra_files,
                save_func=self.save_edit
            )
            self.activity_runner = activities.show_activity(cr, self.get_root())
            cr.run()

    def get_code(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def get_language(self) -> str:
        if self.code_language:
            language_name = self.code_language.get_name()
            if language_name:
                return language_name
        return self.raw_language

    def set_language(self, value:str) -> None:
        self.code_language = GtkSource.LanguageManager.get_default().get_language(language_fallback.get(value.lower(), value))
        self.language_label.set_label(self.get_language().title())
        self.buffer.set_language(self.code_language)
        self.run_button.set_visible(get_language_property(self.get_language()))

    def get_content(self) -> str:
        return "```{}\n{}\n```".format(self.get_language().lower(), self.get_code())

    def get_content_for_dictation(self) -> str:
        allowed_characters = ('\n', ',', '.', ':', ';', '+', '/', '-', '(', ')', '[', ']', '=', '<', '>', '’', '\'', '"', '¿', '?', '¡', '!')
        cleaned_text = ''.join(c for c in self.get_code() if unicodedata.category(c).startswith(('L', 'N', 'Zs')) or c in allowed_characters)
        lines = ['{}.'.format(self.get_language())]
        for line in cleaned_text.split('\n'):
            if line and line.strip() not in allowed_characters:
                lines.append(line)
        return '\n'.join(lines)

    def set_content(self, value:str) -> None:
        self.buffer.set_text(value, len(value.encode('utf-8')))

