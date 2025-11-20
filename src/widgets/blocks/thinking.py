# thinking.py

from gi.repository import GLib, Gtk, Gdk, Adw

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/thinking.ui')
class Thinking(Gtk.Box):
    __gtype_name__ = 'AlpacaThinking'

    label = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

    def append_content(self, text:str):
        self.label.append_content(text)

    def get_content(self) -> str:
        return self.label.get_content()
