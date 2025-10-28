#chat.py
"""
Handles the terminal widget
"""

import gi
import sys
if sys.platform != 'win32':
    gi.require_version('Vte', '3.91')
    from gi.repository import Vte
from gi.repository import Gtk, Pango, GLib, Gdk, Gio, Adw, GtkSource
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
        'flatpak-spawn --host \'bash -c "{script}"\''
    ] if IN_FLATPAK else ["script'"]
}

if sys.platform != 'win32':
    class Terminal(Vte.Terminal):
        __gtype_name__ = 'AlpacaTerminal'

        def __init__(self, language:str, code_getter:callable, extra_files:list=[], close_callback:callable=None):
            self.language = language
            self.code_getter = code_getter
            self.extra_files = extra_files
            self.close_callback = close_callback

            super().__init__(css_classes=["p10", "black_background"])
            self.set_font(Pango.FontDescription.from_string("Monospace 12"))
            self.set_clear_background(False)
            key_controller = Gtk.EventControllerKey()
            key_controller.connect("key-pressed", self.on_key_press)
            self.add_controller(key_controller)

            self.dir_button = Gtk.Button(
                tooltip_text=_("Open Environment Directory"),
                icon_name="document-open-symbolic",
                sensitive=False
            )
            self.dir_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri('file://{}'.format(self.sourcedir)))

            self.reload_button = Gtk.Button(
                tooltip_text=_("Reload Script"),
                icon_name='update-symbolic',
                sensitive=False
            )
            self.reload_button.connect('clicked', lambda button: self.on_reload())
            if self.close_callback:
                self.connect('child-exited', lambda *_: self.close_callback())

            # Activities
            self.buttons = {
                'start': [self.dir_button, self.reload_button]
            }
            self.extend_to_edge = False
            self.title = _("Terminal")
            self.activity_icon = 'terminal-symbolic'

        def on_reload(self):
            try:
                self.feed_child(b"\x03")
                self.reset(True, True)
            except:
                pass
            self.run()

        def get_text(self) -> str:
            return self.get_text_format(1)

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

    class CodeRunner(Gtk.Stack):
        __gtype_name__ = 'AlpacaCodeRunner'

        def __init__(self, code_getter:callable, language:str, extra_files:list=[], save_func:callable=None, close_callback:callable=None, default_mode:str='terminal'):
            super().__init__(
                transition_type=6
            )
            self.close_callback = close_callback
            self.code_editor = CodeEditor(language, code_getter, save_func)
            self.terminal = Terminal(language, self.code_editor.get_code, extra_files)
            self.add_named(self.terminal, 'terminal')
            self.add_named(self.code_editor, 'editor')

            self.button_stack = Gtk.Stack(
                transition_type=1,
                overflow=1
            )
            terminal_buttons_container = Gtk.Box(
                css_classes=['linked']
            )
            for btn in self.terminal.buttons.get('start', []) + self.terminal.buttons.get('end', []):
                terminal_buttons_container.append(btn)

            code_editor_buttons_container = Gtk.Box(
                css_classes=['linked']
            )
            for btn in self.code_editor.buttons.get('start', []) + self.code_editor.buttons.get('end', []):
                code_editor_buttons_container.append(btn)

            self.button_stack.add_named(terminal_buttons_container, 'terminal')
            self.button_stack.add_named(code_editor_buttons_container, 'editor')

            view_button = Gtk.ToggleButton(
                tooltip_text=_('Edit Code'),
                icon_name='document-edit-symbolic'
            )
            view_button.connect('toggled', self.change_view)
            view_button.set_active(default_mode == 'editor')

            # Activities
            self.buttons = {
                'start': [view_button, self.button_stack]
            }
            self.extend_to_edge = False
            self.title = _("Code Runner")
            self.activity_icon = 'code-symbolic'

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

else:
    class Terminal(Gtk.Label):
        __gtype_name__ = 'AlpacaWindowsTerminalFallback'

        def __init__(self, *_):
            super().__init__(
                label=_("Alpaca Terminal is not compatible with Windows"),
                css_classes=['error', 'p10'],
                justify=2,
                wrap=True
            )

    class CodeRunner(Terminal):
        __gtype_name__ = 'AlpacaWindowsCodeRunnerFallback'

class AttachmentCreator(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentCreator'
    def __init__(self):
        self.buffer = GtkSource.Buffer()
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))
        self.view = GtkSource.View(
            auto_indent=True,
            indent_width=4,
            buffer=self.buffer,
            show_line_numbers=True,
            css_classes=["monospace", "p10-vertical"]
        )

        super().__init__(
            child=self.view,
            propagate_natural_width=True,
            propagate_natural_height=True
        )

        save_button = Gtk.Button(
            tooltip_text=_("Save Script"),
            icon_name='check-plain-symbolic'
        )
        save_button.connect('clicked', lambda button: self.save_requested())

        # Activities
        self.buttons = {
            'start': [save_button]
        }
        self.extend_to_edge = False
        self.title = _("New Attachment")
        self.activity_icon = 'document-edit-symbolic'

    def save(self, name:str):
        attachment = attachments.Attachment(
            file_id='-1',
            file_name=name,
            file_type='plain_text',
            file_content=self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        )
        self.get_root().get_application().get_main_window().global_footer.attachment_container.add_attachment(attachment)
        self.close()

    def save_requested(self):
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
            parent.close_page(self.get_parent().tab)
        else:
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()

    def on_close(self):
        pass

    def on_reload(self):
        pass

class CodeEditor(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaCodeEditor'

    def __init__(self, language:str, code_getter:callable, save_func:callable=None, close_callback:callable=None):
        self.get_original_code = code_getter
        self.save_func = save_func
        self.close_callback = close_callback

        self.buffer = GtkSource.Buffer()
        if language:
            self.buffer.set_language(GtkSource.LanguageManager.get_default().get_language(language))
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))

        self.view = GtkSource.View(
            auto_indent=True,
            indent_width=4,
            buffer=self.buffer,
            show_line_numbers=True,
            editable=bool(save_func),
            css_classes=["monospace", "p10-vertical"]
        )
        super().__init__(
            child=self.view,
            propagate_natural_width=True,
            propagate_natural_height=True
        )

        self.on_reload()

        # Activities
        self.buttons = {}
        self.extend_to_edge = False
        self.title = _("Code Editor")
        self.activity_icon = 'document-edit-symbolic'

        if save_func:
            save_button = Gtk.Button(
                tooltip_text=_("Save Script"),
                icon_name='check-plain-symbolic'
            )
            save_button.connect('clicked', lambda button: self.save())

            reload_button = Gtk.Button(
                tooltip_text=_("Undo Changes"),
                icon_name='update-symbolic'
            )
            reload_button.connect('clicked', lambda button: self.on_reload())
            self.buttons = {
                'start': [save_button, reload_button]
            }

    def save(self):
        code = self.get_code()
        self.save_func(code)
        dialog.show_toast(_("Changes saved successfully"), self.get_root())
        if isinstance(self.get_parent(), Adw.ToolbarView):
            self.get_ancestor(Adw.Dialog).force_close()

    def get_code(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def on_close(self):
        if self.close_callback:
            self.close_callback()

    def on_reload(self):
        code = self.get_original_code()
        self.buffer.set_text(code, len(code.encode('utf-8')))

