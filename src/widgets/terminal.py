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

        def __init__(self, script:list):
            super().__init__(css_classes=["terminal"])
            self.set_font(Pango.FontDescription.from_string("Monospace 12"))
            self.set_clear_background(False)
            pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)
            self.set_pty(pty)
            pty.spawn_async(
                GLib.get_current_dir(),
                script,
                [],
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                -1,
                None,
                None,
                None
            )
            key_controller = Gtk.EventControllerKey()
            key_controller.connect("key-pressed", self.on_key_press)
            self.add_controller(key_controller)

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

class TerminalDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaTerminalDialog'

    def __init__(self):
        super().__init__(
            title = _('Terminal'),
            can_close = False,
            content_width = 700,
            content_height = 600,
            child = Adw.ToolbarView(
                css_classes=["osd"]
            )
        )
        self.sourcedir = ''
        header = Adw.HeaderBar()
        self.dir_button = Gtk.Button(
            css_classes=["flat"],
            tooltip_text=_("Open Environment Directory"),
            icon_name="document-open-symbolic",
            sensitive=False
        )
        self.dir_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri('file://{}'.format(self.sourcedir)))
        header.pack_start(self.dir_button)
        self.get_child().add_top_bar(header)
        self.get_child().set_content(Gtk.ScrolledWindow(
            propagate_natural_height=True,
            propagate_natural_width=True
        ))
        self.connect('close-attempt', lambda *_: self.on_close())

    def on_close(self) -> bool:
        try:
            if self.get_child().get_content().get_child():
                self.get_child().get_content().get_child().feed_child(b"\x03")
        except:
            pass
        self.force_close()

    def run(self, code_language:str, file_content:str, extra_files:list=[]) -> None:
        self.sourcedir = os.path.join(data_dir, 'code runner', code_language)
        self.dir_button.set_sensitive(True)
        if not os.path.isdir(self.sourcedir):
            if not os.path.isdir(os.path.join(data_dir, 'code runner')):
                os.mkdir(os.path.join(data_dir, 'code runner'))
            os.mkdir(self.sourcedir)

        for file in extra_files:
            if code_language == 'html':
                if file.get('language') == 'js':
                    with os.path.join(self.sourcedir, 'script.js', 'w') as f:
                        f.write(file.get('content'))
                    file_content += '<script src="script.js">'
                if file.get('language') == 'css':
                    with os.path.join(self.sourcedir, 'style.css', 'w') as f:
                        f.write(file.get('content'))
                    file_content += '<link rel="stylesheet" href="style.css" type="text/css">'

        script = []
        if code_language == 'python':
            sourcepath = os.path.join(self.sourcedir, 'main.py')
            sourcename = 'main.py'
            with open(sourcepath, 'w') as f:
                f.write(file_content)
            if not os.path.isfile(os.path.join(self.sourcedir, 'requirements.txt')):
                with open(os.path.join(self.sourcedir, 'requirements.txt'), 'w') as f:
                    f.write('')
            for command in commands.get('python'):
                script.append(command.format(sourcepath=sourcepath, sourcename=sourcename))
        elif code_language == 'mermaid':
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
                """.format(mermaid_content=file_content))
            for command in commands.get('html'):
                script.append(command.format(sourcedir=self.sourcedir))


        elif code_language == 'html':
            sourcepath = os.path.join(self.sourcedir, 'index.html')
            with open(sourcepath, 'w') as f:
                f.write(file_content)
            for command in commands.get('html'):
                script.append(command.format(sourcedir=self.sourcedir))
        elif code_language in ('bash', 'ssh'):
            for command in commands.get(code_language):
                script.append(command.format(script=file_content))

        script.append('echo -e "\n🦙 {}"'.format(_('Script Exited')))

        if sys.platform != 'win32':
            self.get_child().get_content().set_child(
                Terminal(
                    script=['bash', '-c', ';\n'.join(script)]
                )
            )
        else:
            self.get_child().get_content().set_child(
                Gtk.Label(
                    label=_("Alpaca Terminal is not compatible with Windows"),
                    css_classes=['error', 'p10'],
                    justify=2,
                    wrap=True
                )
            )
