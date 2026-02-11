#chat.py
"""
Handles the terminal widget
"""

import gi
import sys
from gi.repository import Gtk, Pango, GLib, Gdk, Gio, Adw, GtkSource, Vte
import os
from ...sql_manager import Instance as SQL
from ...constants import data_dir, IN_FLATPAK
from .. import dialog, attachments, message, activities

commands = {
    'python': [
        'echo -e "🦙 {}\n"'.format(_('Setting up Python environment...')),
        'python3 -m venv "{}"'.format(os.path.join(data_dir, 'code runner', 'python')),
        'source "{}"'.format(os.path.join(data_dir, 'code runner', 'python', 'bin', 'activate')),
        'export MPLBACKEND=GTK4Agg',
        'export PIP_DISABLE_PIP_VERSION_CHECK=1',
        'pip install matplotlib pygobject | grep -v "already satisfied"',
        'pip install -r "{}" | grep -v "already satisfied"'.format(os.path.join(data_dir, 'code runner', 'python', 'requirements.txt')),
        'clear',
        'echo -e "🦙 {sourcename}\n"',
        'python3 "{sourcepath}"'
    ],
    'html': [
        'echo -e "🦙 {}\n"'.format(_('Using Python HTTP server...')),
        'python -m http.server 8080 --directory "{sourcedir}"'
    ],
    'bash': [
        'flatpak-spawn --host env TERM=xterm-256color script -q -c {script} /dev/null'
    ] if IN_FLATPAK else ["{script}"]
}

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/code_runner.ui')
class CodeRunner(Gtk.Stack):
    __gtype_name__ = 'AlpacaCodeRunner'

    button_stack = Gtk.Template.Child()
    view_button = Gtk.Template.Child()

    def __init__(self, code_getter:callable, language:str, extra_files:list=[], save_func:callable=None, close_callback:callable=None, default_mode:str='terminal'):
        super().__init__()
        self.close_callback = close_callback
        self.code_editor = CodeEditor(language, code_getter, save_func)
        self.code_editor.set_margin_start(0)
        self.code_editor.set_margin_end(0)
        self.code_editor.remove_css_class('r10')
        self.terminal = Terminal(language, self.code_editor.get_code, extra_files)
        self.terminal.set_margin_start(0)
        self.terminal.set_margin_end(0)
        self.terminal.remove_css_class('r10')
        self.add_named(self.terminal, 'terminal')
        self.add_named(self.code_editor, 'editor')

        for btn in self.terminal.buttons.get('start', []) + self.terminal.buttons.get('end', []):
            self.button_stack.get_child_by_name("terminal").append(btn)

        for btn in self.code_editor.buttons.get('start', []) + self.code_editor.buttons.get('end', []):
            self.button_stack.get_child_by_name("editor").append(btn)

        # Activities
        self.buttons = {
            'start': [self.view_button, self.button_stack]
        }
        self.extend_to_edge = False
        self.title = _("Code Runner")
        self.activity_icon = 'code-symbolic'

    @Gtk.Template.Callback()
    def change_view(self, toggle):
        self.button_stack.set_visible_child_name('editor' if toggle.get_active() else 'terminal')
        self.set_visible_child_name('editor' if toggle.get_active() else 'terminal')

    def run(self):
        self.terminal.run()

    def on_close(self):
        self.terminal.on_close()
        if self.close_callback:
            self.close_callback()

    def on_reload(self):
        self.code_editor.on_reload()
        self.terminal.on_reload()

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/terminal.ui')
class Terminal(Vte.Terminal):
    __gtype_name__ = 'AlpacaTerminal'

    dir_button = Gtk.Template.Child()
    reload_button = Gtk.Template.Child()

    def __init__(self, language:str, code_getter:callable, extra_files:list=[], close_callback:callable=None):
        super().__init__()
        self.language = language
        self.code_getter = code_getter
        self.extra_files = extra_files
        self.close_callback = close_callback

        if self.close_callback:
            self.connect('child-exited', lambda *_: self.close_callback())

        # Activities
        self.buttons = {
            'start': [self.dir_button, self.reload_button]
        }
        self.extend_to_edge = False
        self.title = _("Terminal")
        self.activity_icon = 'terminal-symbolic'

    def get_text(self) -> str:
        return self.get_text_format(1)

    @Gtk.Template.Callback()
    def open_directory(self, button=None):
        Gio.AppInfo.launch_default_for_uri('file://{}'.format(self.sourcedir))

    @Gtk.Template.Callback()
    def on_reload(self, button=None):
        try:
            self.feed_child(b"\x03")
            self.reset(True, True)
        except:
            pass
        self.run()

    @Gtk.Template.Callback()
    def on_key_press(self, controller, keyval, keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        shift = state & Gdk.ModifierType.SHIFT_MASK
        if ctrl and keyval == Gdk.KEY_c:
            self.copy_clipboard_format(1)
            return True
        elif ctrl and keyval == Gdk.KEY_v:
            self.paste_clipboard()
            return True
        return False

    def on_close(self) -> bool: # Called by activities.py
        try:
            self.feed_child(b"\x03")
        except:
            pass
        if self.close_callback:
            self.close_callback()

    def prepare_script(self) -> list:
        runtime_code = self.code_getter()

        for ef in self.extra_files:
            if ef.get('language') in ('js', 'javascript'):
                runtime_code += '\n<script>{}</script>'.format(ef.get('code'))
            elif ef.get('language') == 'css':
                runtime_code += '\n<style>{}</style>'.format(ef.get('code'))

        self.sourcedir = os.path.join(data_dir, 'code runner', self.language)
        self.dir_button.set_sensitive(True)
        if not os.path.isdir(self.sourcedir):
            if not os.path.isdir(os.path.join(data_dir, 'code runner')):
                os.mkdir(os.path.join(data_dir, 'code runner'))
            os.mkdir(self.sourcedir)

        script = []
        if self.language == 'python':
            sourcepath = os.path.join(self.sourcedir, 'main.py')
            sourcename = 'main.py'
            with open(sourcepath, 'w') as f:
                f.write(runtime_code)
            if not os.path.isfile(os.path.join(self.sourcedir, 'requirements.txt')):
                with open(os.path.join(self.sourcedir, 'requirements.txt'), 'w') as f:
                    f.write('')
            for command in commands.get('python'):
                script.append(command.format(sourcepath=sourcepath, sourcename=sourcename))
        elif self.language == 'mermaid':
            sourcepath = os.path.join(self.sourcedir, 'index.html')
            with open(sourcepath, 'w') as f:
                f.write("""
<!DOCTYPE html>
<html>
<head>
<style>
body {{background:#fafafb;}}
.mermaid {{display: flex; justify-content: center;}}
</style>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({{ startOnLoad: true }});
</script>
</head>
<body><div class="mermaid">{mermaid_content}</div></body>
</html>
                """.format(mermaid_content=runtime_code))
            for command in commands.get('html'):
                script.append(command.format(sourcedir=self.sourcedir))
        elif self.language == 'html':
            sourcepath = os.path.join(self.sourcedir, 'index.html')
            with open(sourcepath, 'w') as f:
                f.write(runtime_code)
            for command in commands.get('html'):
                script.append(command.format(sourcedir=self.sourcedir))
        elif self.language in ('bash', 'auto'):
            settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
            if settings.get_value('activity-terminal-type').unpack() == 0:
                for command in commands.get('bash'):
                    script.append(command.format(script=runtime_code))
            else:
                runtime_code="ssh -t {}@{} -- '{}'".format(
                    settings.get_value('activity-terminal-username').unpack() or os.getenv('USER'),
                    settings.get_value('activity-terminal-ip').unpack() or '127.0.0.1',
                    runtime_code.replace("'", "\\'")
                )
                script.append(runtime_code)

        script.append('echo -e "\n🦙 {}"'.format(_('Script Exited')))
        script.append('exit')
        return script

    def run(self):
        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)
        self.set_pty(pty)
        pty.spawn_async(
            os.path.join(data_dir, 'code runner', self.language),
            ['bash', '-c', ';\n'.join(self.prepare_script())],
            [],
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            lambda p, t, u: self.watch_child(p.spawn_finish(t)[1]),
            None
        )
        self.reload_button.set_sensitive(True)

        if self.language in ('html', 'mermaid'): #Launch Browser
            def launch_browser():
                activities.show_activity(
                    page=activities.WebBrowser('http://127.0.0.1:8080'),
                    root=self.get_root()
                )
            GLib.idle_add(launch_browser)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/attachment_creator.ui')
class AttachmentCreator(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentCreator'

    buffer = Gtk.Template.Child()
    save_button = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

        # Activities
        self.buttons = {
            'start': [self.save_button]
        }
        self.extend_to_edge = False
        self.title = _("New Attachment")
        self.activity_icon = 'document-edit-symbolic'

        Adw.StyleManager.get_default().connect(
            'notify::dark',
            lambda sm, gp: self.update_scheme()
        )
        self.update_scheme()

    def update_scheme(self):
        scheme_name = 'Adwaita'
        if Adw.StyleManager.get_default().get_dark():
            scheme_name += '-dark'
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme(scheme_name))

    def save(self, name:str):
        is_code = '.' in name and len(name.split('.')) > 1 and name.split('.')[1] != 'txt'

        attachment = attachments.Attachment(
            file_id='-1',
            file_name=name,
            file_type=code if is_code else 'plain_text',
            file_content=self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        )
        self.get_root().get_application().get_main_window().global_footer.attachment_container.add_attachment(attachment)
        self.close()

    @Gtk.Template.Callback()
    def save_requested(self, button=None):
        dialog.simple_entry(
            self.get_root(),
            heading=_('Name the Attachment'),
            body='',
            callback=self.save,
            entries=[{
                'placeholder': _('New File'),
                'text': _('New File')
            }]
        )

    def close(self):
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.close_page(parent.get_page(self))
        else:
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()

    def on_close(self):
        pass

    def on_reload(self):
        pass

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/code_editor.ui')
class CodeEditor(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaCodeEditor'

    view = Gtk.Template.Child()
    buffer = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    reload_button = Gtk.Template.Child()

    def __init__(self, language:str, code_getter:callable, save_func:callable=None, close_callback:callable=None):
        super().__init__()
        self.get_original_code = code_getter
        self.save_func = save_func
        self.close_callback = close_callback

        if language:
            self.buffer.set_language(GtkSource.LanguageManager.get_default().get_language(language))

        self.view.set_editable(bool(save_func))

        self.on_reload()

        self.save_button.set_visible(bool(save_func))
        self.reload_button.set_visible(bool(save_func))

        # Activities
        self.buttons = {
            'start': [self.save_button, self.reload_button]
        }
        self.extend_to_edge = False
        self.title = _("Code Editor")
        self.activity_icon = 'document-edit-symbolic'

        Adw.StyleManager.get_default().connect(
            'notify::dark',
            lambda sm, gp: self.update_scheme()
        )
        self.update_scheme()

    def update_scheme(self):
        scheme_name = 'Adwaita'
        if Adw.StyleManager.get_default().get_dark():
            scheme_name += '-dark'
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme(scheme_name))

    @Gtk.Template.Callback()
    def save(self, button=None):
        code = self.get_code()
        self.save_func(code)
        dialog.show_toast(_("Changes saved successfully"), self.get_root())
        self.close()

    def close(self):
        # only when dialog
        parent = self.get_ancestor(Adw.Dialog)
        if parent:
            parent.close()

    def get_code(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def on_close(self):
        if self.close_callback:
            self.close_callback()

    @Gtk.Template.Callback()
    def on_reload(self, button=None):
        code = self.get_original_code()
        self.buffer.set_text(code, len(code.encode('utf-8')))

