#chat_widget.py
"""
Handles the terminal widget
"""

import gi
gi.require_version('Gtk', '4.0')
import sys
if sys.platform != 'win32':
    gi.require_version('Vte', '3.91')
    from gi.repository import Vte
from gi.repository import Gtk, GLib, Pango, GLib, Gdk, Gio
import logging, os, shutil, subprocess, re, signal
from ..internal import data_dir

logger = logging.getLogger(__name__)

window = None

if sys.platform != 'win32':
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
            elif ctrl and keyval == Gdk.KEY_v:
                self.paste_clipboard()
                return True
            return False

def show_terminal(script):
    if sys.platform != 'win32':
        window.terminal_scroller.set_child(terminal(script))
        window.terminal_dialog.present(window)

def run_terminal(files:dict):
    logger.info('Running Terminal')
    script = []
    if not os.path.isdir(os.path.join(data_dir, 'code runner')):
        os.mkdir(os.path.join(data_dir, 'code runner'))

    for file_name, file_metadata in files.items():
        window.terminal_dir_button.set_name('file://{}'.format(os.path.join(data_dir, 'code runner')))
        if file_metadata['language'].lower() in ('python3', 'py', 'py3', 'python'):
            window.terminal_dir_button.set_name('file://{}'.format(os.path.join(data_dir, 'code runner', 'python')))
            if not os.path.isdir(os.path.join(data_dir, 'code runner', 'python')):
                os.mkdir(os.path.join(data_dir, 'code runner', 'python'))
            with open(os.path.join(data_dir, 'code runner', 'python', file_name), 'w') as f:
                f.write(file_metadata['content'])
            if not os.path.isfile(os.path.join(data_dir, 'code runner', 'python', 'requirements.txt')):
                with open(os.path.join(data_dir, 'code runner', 'python', 'requirements.txt'), 'w') as f:
                    f.write('matplotlib\npygobject')
            script += [
                'echo -e "🦙 {}\n"'.format(_('Setting up Python environment...')),
                'python3 -m venv "{}"'.format(os.path.join(data_dir, 'code runner', 'python')),
                'source "{}"'.format(os.path.join(data_dir, 'code runner', 'python', 'bin', 'activate')),
                'pip install -r "{}" | grep -v "already satisfied"'.format(os.path.join(data_dir, 'code runner', 'python', 'requirements.txt')),
                'export MPLBACKEND=GTK4Agg',
                'clear',
                'echo -e "🦙 {}\n"'.format(file_name),
                'python3 "{}"'.format(os.path.join(data_dir, 'code runner', 'python', file_name))
            ]
        elif file_metadata['language'].lower() in ('cpp', 'c', 'c++'):
            window.terminal_dir_button.set_name('file://{}'.format(os.path.join(data_dir, 'code runner', 'cpp')))
            if not os.path.isdir(os.path.join(data_dir, 'code runner', 'cpp')):
                os.mkdir(os.path.join(data_dir, 'code runner', 'cpp'))
            with open(os.path.join(data_dir, 'code runner', 'cpp', file_name), 'w') as f:
                f.write(file_metadata['content'])
            script += [
                'echo -e "🦙 {}\n"'.format(_('Compiling C++ script...')),
                'g++ "{}" -o "{}"'.format(os.path.join(data_dir, 'code runner', 'cpp', file_name), os.path.join(data_dir, 'code runner', 'cpp', '.'.join(file_name.split('.')[:-1]) + '.bin')),
                'chmod u+x "{}"'.format(os.path.join(data_dir, 'code runner', 'cpp', '.'.join(file_name.split('.')[:-1]) + '.bin')),
                'echo -e "🦙 {}\n"'.format('.'.join(file_name.split('.')[:-1])+'.bin'),
                '"{}"'.format(os.path.join(data_dir, 'code runner', 'cpp', '.'.join(file_name.split('.')[:-1]) + '.bin'))
            ]
        elif file_metadata['language'].lower() in ('css', 'js', 'javascript'):
            if not os.path.isdir(os.path.join(data_dir, 'code runner', 'html')):
                os.mkdir(os.path.join(data_dir, 'code runner', 'html'))
            with open(os.path.join(data_dir, 'code runner', 'html', file_name), 'w') as f:
                f.write(file_metadata['content'])
        elif file_metadata['language'].lower() in ('html'):
            window.terminal_dir_button.set_name('file://{}'.format(os.path.join(data_dir, 'code runner', 'html')))
            script.append('echo -e "🦙 {}"'.format(_('Running local web server')))
            if not os.path.isdir(os.path.join(data_dir, 'code runner', 'html')):
                os.mkdir(os.path.join(data_dir, 'code runner', 'html'))
            with open(os.path.join(data_dir, 'code runner', 'html', file_name), 'w') as f:
                content = file_metadata['content']
                for file_name, file_metadata in files.items():
                    if file_metadata['language'].lower() == 'css':
                        content += '\n<link rel="stylesheet" href="{}">'.format(file_name)
                        script.append('echo -e "    - {}"'.format(file_name))
                    elif file_metadata['language'].lower() in ('javascript', 'js'):
                        content += '\n<script src="{}"></script>'.format(file_name)
                        script.append('echo -e "    - {}"'.format(file_name))
                script.append('echo')
                f.write(content)
            script.append('python -m http.server 8080 --directory "{}"'.format(os.path.join(data_dir, 'code runner', 'html')))
            Gio.AppInfo.launch_default_for_uri('http://0.0.0.0:8080')
        elif file_metadata['language'].lower() in ('bash', 'sh'):
            if shutil.which('flatpak-spawn'):
                sandbox = True
                try:
                    process = subprocess.run(['flatpak-spawn', '--host', 'bash', '-c', 'echo "test"'], check=True)
                    sandbox = False
                except Exception as e:
                    pass
                if sandbox:
                    script.append('echo "🦙 {}\n"'.format(_('Using Flatpak contained shell')))
                    script.append(file_metadata['content'])
                else:
                    script.append(file_metadata['content'])
                    show_terminal(['flatpak-spawn', '--host', 'bash', '-c', ';\n'.join(script)])
                    return
    script.append('echo -e "\n🦙 {}"'.format(_('Script Exited') ))
    show_terminal(['bash', '-c', ';\n'.join(script)])

