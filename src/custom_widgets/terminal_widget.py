#chat_widget.py
"""
Handles the terminal widget
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Vte, GLib, Pango, GLib, Gdk
import logging, os, shutil, subprocess, re
from ..internal import data_dir

logger = logging.getLogger(__name__)

window = None

class terminal(Vte.Terminal):
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
            None
        )

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        self.add_controller(key_controller)

    def on_key_press(self, controller, keyval, keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        shift = state & Gdk.ModifierType.SHIFT_MASK
        if ctrl and keyval == Gdk.KEY_c:
            self.copy_clipboard()
            return True
        return False

def show_terminal(script):
    window.terminal_scroller.set_child(terminal(script))
    window.terminal_dialog.present(window)

def run_terminal(script:str, language_name:str):
    logger.info('Running: \n{}'.format(language_name))
    if language_name == 'python3':
        if not os.path.isdir(os.path.join(data_dir, 'pyenv')):
            os.mkdir(os.path.join(data_dir, 'pyenv'))
        with open(os.path.join(data_dir, 'pyenv', 'main.py'), 'w') as f:
            f.write(script)
        script = [
            'echo "🐍 {}\n"'.format(_('Setting up Python environment...')),
            'python3 -m venv "{}"'.format(os.path.join(data_dir, 'pyenv')),
            '{} {}'.format(os.path.join(data_dir, 'pyenv', 'bin', 'python3').replace(' ', '\\ '), os.path.join(data_dir, 'pyenv', 'main.py').replace(' ', '\\ '))
        ]
        if os.path.isfile(os.path.join(data_dir, 'pyenv', 'requirements.txt')):
            script.insert(1, '{} install -r {} | grep -v "already satisfied"; clear'.format(os.path.join(data_dir, 'pyenv', 'bin', 'pip3'), os.path.join(data_dir, 'pyenv', 'requirements.txt')))
        else:
            with open(os.path.join(data_dir, 'pyenv', 'requirements.txt'), 'w') as f:
                f.write('')
        script = ';\n'.join(script)

    script += '; echo "\n🦙 {}"'.format(_('Script exited'))
    if language_name == 'bash':
        script = re.sub(r'(?m)^\s*sudo', 'pkexec', script)
    if shutil.which('flatpak-spawn') and language_name == 'bash':
        sandbox = True
        try:
            process = subprocess.run(['flatpak-spawn', '--host', 'bash', '-c', 'echo "test"'], check=True)
            sandbox = False
        except Exception as e:
            pass
        if sandbox:
            script = 'echo "🦙 {}\n";'.format(_('The script is contained inside Flatpak')) + script
            show_terminal(['bash', '-c', script])
        else:
            show_terminal(['flatpak-spawn', '--host', 'bash', '-c', script])
    else:
        show_terminal(['bash', '-c', script])
