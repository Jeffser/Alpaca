# latex.py
"""
Representation of Latex equations
"""

import gi
from gi.repository import Gtk, Gdk, Adw, GLib, Gio

from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.figure import Figure
from .. import dialog, activities

class LatexCanvas(FigureCanvas):
    __gtype_name__ = 'AlpacaLatexCanvas'

    def __init__(self, eq=""):
        self.fig = Figure(dpi=100)
        self.fig.patch.set_alpha(0)
        ax = self.fig.add_subplot()
        ax.axis('off')
        self.text = ax.text(0.5, 0.5, "", fontsize=24, ha='center', va='center')
        super().__init__(self.fig)
        self.set_css_classes(['latex_renderer'])

        if eq:
            GLib.idle_add(self.set_text, eq)

    def set_text(self, text:str):
        try:
            self.text.set_text(text)
            self.text.set_fontsize(24)
            self.fig.canvas.draw()
        except ValueError as e:
            self.text.set_text(str(e))
            self.text.set_fontsize(12)
            self.fig.canvas.draw()

        bbox = self.text.get_window_extent()
        self.set_content_width(bbox.width)
        self.set_content_height(bbox.height)
        self.set_halign(3)
        self.set_valign(3)

    def get_text(self) -> str:
        return self.text.get_text()

    def download_requested(self):
        def on_download(file_dialog, result, user_data):
            try:
                file = file_dialog.save_finish(result)
                path = file.get_path()
                text = self.get_text()
                self.fig.savefig(path, bbox_inches="tight", pad_inches=0)
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
                dialog.show_toast(_("Equation exported successfully"), self.get_root())
                GLib.idle_add(self.set_text, text)
            except GLib.Error as e:
                logger.error(e)

        file_dialog = Gtk.FileDialog(
            title=_("Save Equation"),
            initial_name="{}.png".format(_("equation"))
        )
        file_dialog.save(self.get_root(), None, on_download, None)

    def copy_equation(self) -> None:
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.get_text())
        dialog.show_toast(_("Equation copied to the clipboard"), self.get_root())

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/latex_renderer.ui')
class LatexRenderer(Gtk.Button):
    __gtype_name__ = 'AlpacaLatexRenderer'

    scrolled_window = Gtk.Template.Child()

    def __init__(self, content:str=None):
        self.canvas = LatexCanvas()
        self.activity = None
        super().__init__(
            child=self.canvas
        )
        if content:
            self.set_content(content)

    def get_content(self) -> str:
        return '${}$'.format(self.canvas.get_text().strip('$'))

    def get_content_for_dictation(self) -> str:
        return self.canvas.get_text()

    def set_content(self, content:str=None) -> None:
        content = content.strip().strip('$')
        self.canvas.set_text('${}$'.format(content))

    @Gtk.Template.Callback()
    def edit_equation(self, button=None) -> None:
        if self.activity:
            self.activity.on_reload()
        else:
            page = activities.LatexEditor(self.canvas)
            self.activity = activities.show_activity(
                page,
                self.get_root(),
                False
            )

    @Gtk.Template.Callback()
    def show_popup(self, *args):
        rect = Gdk.Rectangle()
        if len(args) == 4:
            rect.x, rect.y = args[2], args[3]
        else:
            rect.x, rect.y = args[1], args[2]

        actions = [[
        {
            'label': _('Copy Equation'),
            'callback': self.canvas.copy_equation,
            'icon': 'edit-copy-symbolic'
        },
        {
            'label': _('Download as Image'),
            'callback': self.canvas.download_requested,
            'icon': 'folder-download-symbolic'
        }]]

        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()
