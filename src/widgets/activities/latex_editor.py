# latex_editor.py
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject, Gst
from ..blocks import latex
from ..message import Message
import logging

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/latex_editor.ui')
class LatexEditor(Gtk.Box):
    __gtype_name__ = 'AlpacaLatexEditor'

    latex_container = Gtk.Template.Child()
    buffer = Gtk.Template.Child()

    save_button = Gtk.Template.Child()
    reload_button = Gtk.Template.Child()
    download_button = Gtk.Template.Child()

    def __init__(self, block_canvas=None):
        super().__init__()
        self.block_canvas = block_canvas #in case the user edits existing latex
        self.canvas = latex.LatexCanvas()
        self.latex_container.set_child(self.canvas)
        self.reload_button.set_visible(bool(block_canvas))
        self.save_button.set_visible(bool(block_canvas))

        # Activity
        self.title=_('Latex Editor')
        self.activity_icon='document-edit-symbolic'
        self.buttons={
            'start': [
                self.save_button,
                self.reload_button
            ],
            'end': [self.download_button]
        }
        self.extend_to_edge = False

        self.on_reload()

    @Gtk.Template.Callback()
    def buffer_changed(self, buffer):
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip('$')
        GLib.idle_add(self.canvas.set_text, '${}$'.format(text) if text else '')

    @Gtk.Template.Callback()
    def save_requested(self, button):
        if self.block_canvas:
            GLib.idle_add(self.block_canvas.set_text, self.canvas.get_text())
            GLib.idle_add(self.block_canvas.get_ancestor(Message).save)

    @Gtk.Template.Callback()
    def download_requested(self, button):
        self.canvas.download_requested()

    @Gtk.Template.Callback()
    def on_reload(self, button=None):
        if self.block_canvas:
            eq = self.block_canvas.get_text().strip('$')
            self.buffer.set_text(eq, len(eq.encode('utf8')))

    def on_close(self):
        pass

