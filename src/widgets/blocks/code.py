# code.py
"""
TODO DESCRIPTION
"""

import gi
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, Gdk, GtkSource

language_fallback = {
    'bash': 'sh',
    'cmd': 'powershell',
    'batch': 'powershell',
    'c#': 'csharp',
    'vb.net': 'vbnet'
}

language_properties: (
    {
        'id': 'python',
        'aliases': ['python', 'python3', 'py', 'py3'],
        'executable': True,
        'filename': 'main.py'
    },
    {
        'id': 'cpp',
        'aliases': ['cpp', 'c++'],
        'executable': True,
        'filename': 'script.cpp'
    },
    {
        'id': 'html',
        'aliases': ['html', 'htm'],
        'executable': True,
        'filename': 'index.html'
    },
    {
        'id': 'bash',
        'aliases': ['bash', 'sh'],
        'executable': True,
        'filename': 'script.sh'
    },
    {
        'id': 'css',
        'aliases': ['css'],
        'executable': False,
        'filename': 'style.css'
    },
    {
        'id': 'js',
        'aliases': ['js', 'javascript'],
        'executable': False,
        'filename': 'script.js'
    }
)

def get_language_property(language:str) -> dict:
    for properties in language_properties:
        if language in properties.get('aliases', []):
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
            margin_end=12,
            spacing=5
        )
        self.language_label = Gtk.Label(
            label=_("Code Block"),
            hexpand=True,
            xalign=0
        )
        title_box.append(self.language_label)

        # Buttons
        copy_button = Gtk.Button(
            icon_name="edit-copy-symbolic",
            css_classes=["flat", "circular"],
            tooltip_text=_("Copy Message")
        )
        copy_button.connect("clicked", lambda *_: self.copy_code())
        title_box.append(copy_button)

        self.run_button = Gtk.Button(
            icon_name="execute-from-symbolic",
            css_classes=["flat", "circular"],
            tooltip_text=_("Run Script"),
            visible=False
        )
        self.run_button.connect("clicked", lambda *_: self.run_script())
        title_box.append(self.run_button)

        self.append(title_box)
        self.append(Gtk.Seperator())

        # Code view
        self.buffer = GtkSource.Buffer()
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))
        self.source_view = GtkSource.View(
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
        self.append(self.source_view)

        if content:
            self.set_content(content)
        if language:
            self.set_language(content)

    def copy_code(self) -> None:
        clipboard = Gdk.Display().get_default().get_clipboard()
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        clipboard.set(text)
        ##TODO you know what with toasts
        #window.show_toast(_("Code copied to the clipboard"), window.main_overlay)

    def run_script(self) -> None:
        print('requested run')

    def get_code(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def get_language(self) -> str:
        return self.code_language.get_name()

    def set_language(self, value:str) -> None:
        self.code_language = GtkSource.LanguageManager.get_default().get_language(language_fallback.get(value.lower(), value))
        self.language_label.set_label(self.get_language())
        self.buffer.set_language(self.code_language)
        self.run_button.set_visible(get_language_property(self.language).get('executable'))

    def get_content(self) -> str:
        return "```{}\n{}\n```".format(self.language, self.get_code())

    def set_content(self, value:str) -> None:
        self.buffer.set_text(value, len(value.encode('utf-8')))

# TODO: Connect to Code Runner, Edit Block
