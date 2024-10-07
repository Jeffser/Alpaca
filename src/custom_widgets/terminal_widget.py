#chat_widget.py
"""
Handles the terminal widget
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Vte, GLib, Pango

class terminal(Vte.Terminal):
    __gtype_name__ = 'AlpacaTerminal'

    def __init__(self, script:list):
        super().__init__(css_classes=["terminal"])
        self.set_font(Pango.FontDescription.from_string("Monospace 12"))

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

        self.connect('child-exited', lambda *_: print('exited'))
