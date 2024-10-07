#chat_widget.py
"""
Handles the terminal widget
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Vte, GLib, Pango, GLib, Gdk

class terminal(Vte.Terminal):
    __gtype_name__ = 'AlpacaTerminal'

    def __init__(self, script:list):
        super().__init__(css_classes=["terminal"])
        self.set_font(Pango.FontDescription.from_string("Monospace 12"))
        self.set_clear_background(False)
        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)

        self.set_pty(pty)

        env = {
            "TERM": "xterm-256color"
        }

        pty.spawn_async(
            GLib.get_current_dir(),
            script,
            [f"{key}={value}" for key, value in env.items()],
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
