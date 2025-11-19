# code.py
"""
Code block handling
"""

from gi.repository import Gtk, Gdk, GtkSource
from .. import dialog, activities, message
from ...sql_manager import generate_uuid
from ...constants import CODE_LANGUAGE_FALLBACK, CODE_LANGUAGE_PROPERTIES
import re, unicodedata

def get_language_property(language:str) -> dict:
    for properties in CODE_LANGUAGE_PROPERTIES:
        if language.lower() in properties.get('aliases', []):
            return properties
    return {}

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/code.ui')
class Code(Gtk.Box):
    __gtype_name__ = 'AlpacaCode'

    language_label = Gtk.Template.Child()
    button_container = Gtk.Template.Child()
    edit_button = Gtk.Template.Child()
    run_button = Gtk.Template.Child()
    buffer = Gtk.Template.Child()

    def __init__(self, content:str=None, language:str=None):
        super().__init__()
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))

        self.raw_language = language
        self.code_language = None
        if content:
            self.set_content(content)
        if self.raw_language:
            self.set_language(self.raw_language)

        self.activity_runner = None
        self.activity_edit = None

    @Gtk.Template.Callback()
    def begin_edit(self, button=None) -> None:
        if self.activity_edit and self.activity_edit.get_root():
            self.activity_edit.on_reload()
        else:
            ce = activities.CodeEditor(
                language=get_language_property(self.get_language()).get('id'),
                code_getter=self.get_code,
                save_func=self.save_edit
            )
            self.activity_edit = activities.show_activity(ce, self.get_root())

    def save_edit(self, code:str) -> None:
        self.buffer.set_text(code, len(code.encode('utf-8')))
        self.get_ancestor(message.Message).save()

    @Gtk.Template.Callback()
    def copy_code(self, button=None) -> None:
        clipboard = Gdk.Display().get_default().get_clipboard()
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        clipboard.set(text)
        dialog.show_toast(_("Code copied to the clipboard"), self.get_root())

    @Gtk.Template.Callback()
    def prompt_download(self, button=None):
        def download(file_dialog, result):
            file = file_dialog.save_finish(result)
            if file:
                with open(file.get_path(), 'w+') as f:
                    f.write(self.get_code())
                dialog.show_toast(
                    message=_('Script saved successfully'),
                    root_widget=self.get_root()
                )

        language = self.get_language()
        filename = 'script'
        for d in language_properties:
            if d.get('id') == language.lower():
                filename = d.get('filename')

        file_dialog = Gtk.FileDialog(initial_name=filename)
        file_dialog.save(
            parent=self.get_root(),
            cancellable=None,
            callback=download
        )

    @Gtk.Template.Callback()
    def run_script(self, button=None) -> None:
        if self.activity_runner and self.activity_runner.get_root():
            self.activity_runner.on_reload()
        else:
            extra_files = []
            for blk in [blk for blk in list(self.get_parent().get_ancestor(message.Message).block_container) if isinstance(blk, Code) and blk.get_language().lower() in ('css', 'javascript', 'js') and blk != self]:
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
        self.code_language = GtkSource.LanguageManager.get_default().get_language(CODE_LANGUAGE_FALLBACK.get(value.lower(), value))
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
