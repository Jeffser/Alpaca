#chat.py
"""
Handles the terminal widget
"""

import gi
import sys
if sys.platform != 'win32':
    gi.require_version('Vte', '3.91')
    from gi.repository import Vte
from gi.repository import Gtk, Pango, GLib, Gdk, Gio, Adw
import os
from ..constants import data_dir

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
        'xdg-open http://0.0.0.0:8080',
        'python -m http.server 8080 --directory "{sourcedir}"'
    ],
    'bash': [
        'echo "🦙 {}\n"'.format(_('Using Flatpak contained shell...')),
        '{script}'
    ],
    'ssh': [
        'echo "🦙 {}\n"'.format(_('Using SSH to run command')),
        '{script}'
    ]
}

if sys.platform != 'win32':
    class Terminal(Vte.Terminal):
        __gtype_name__ = 'AlpacaTerminal'

        def __init__(self, language_getter:callable, code_getter:callable, extra_files_getter:callable=lambda:[], close_callback:callable=None):
            self.language_getter = language_getter
            self.code_getter = code_getter
            self.extra_files_getter = extra_files_getter
            self.close_callback = close_callback

            super().__init__(css_classes=["p10"])
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
            self.reload_button.connect('clicked', lambda button: self.reload())

            # Activities
            self.buttons = [self.dir_button, self.reload_button]
            self.title = _("Terminal")
            self.activity_css = ['osd']
            self.activity_icon = 'terminal-symbolic'

        def reload(self):
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

        def close(self) -> bool: # Called by activities.py
            try:
                self.feed_child(b"\x03")
            except:
                pass
            if self.close_callback:
                self.close_callback()

        def prepare_script(self) -> list:
            language = self.language_getter()
            code = self.code_getter()
            extra_files = self.extra_files_getter()

            self.sourcedir = os.path.join(data_dir, 'code runner', language)
            self.dir_button.set_sensitive(True)
            if not os.path.isdir(self.sourcedir):
                if not os.path.isdir(os.path.join(data_dir, 'code runner')):
                    os.mkdir(os.path.join(data_dir, 'code runner'))
                os.mkdir(self.sourcedir)

            for file in extra_files:
                if language == 'html':
                    if file.get('language') == 'js':
                        with open(os.path.join(self.sourcedir, 'script.js'), 'w') as f:
                            f.write(file.get('content'))
                        code += '<script src="script.js">'
                    if file.get('language') == 'css':
                        with open(os.path.join(self.sourcedir, 'style.css'), 'w') as f:
                            f.write(file.get('content'))
                        code += '<link rel="stylesheet" href="style.css" type="text/css">'

            script = []
            if language == 'python':
                sourcepath = os.path.join(self.sourcedir, 'main.py')
                sourcename = 'main.py'
                with open(sourcepath, 'w') as f:
                    f.write(code)
                if not os.path.isfile(os.path.join(self.sourcedir, 'requirements.txt')):
                    with open(os.path.join(self.sourcedir, 'requirements.txt'), 'w') as f:
                        f.write('')
                for command in commands.get('python'):
                    script.append(command.format(sourcepath=sourcepath, sourcename=sourcename))
            elif language == 'mermaid':
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
                    """.format(mermaid_content=code))
                for command in commands.get('html'):
                    script.append(command.format(sourcedir=self.sourcedir))


            elif language == 'html':
                sourcepath = os.path.join(self.sourcedir, 'index.html')
                with open(sourcepath, 'w') as f:
                    f.write(code)
                for command in commands.get('html'):
                    script.append(command.format(sourcedir=self.sourcedir))
            elif language in ('bash', 'ssh'):
                for command in commands.get(language):
                    script.append(command.format(script=code))

            script.append('echo -e "\n🦙 {}"'.format(_('Script Exited')))
            return script

        def run(self):
            pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)
            self.set_pty(pty)
            pty.spawn_async(
                GLib.get_current_dir(),
                ['bash', '-c', ';\n'.join(self.prepare_script())],
                [],
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                -1,
                None,
                None,
                None
            )
            self.reload_button.set_sensitive(True)
else:
    class Terminal(Gtk.Label):
        __gtype_name__ = 'AlpacaWindowsTerminalFallback'

        def __init__(self):
            super().__init__(
                label=_("Alpaca Terminal is not compatible with Windows"),
                css_classes=['error', 'p10'],
                justify=2,
                wrap=True
            )

