# latex.py
"""
Representation of Latex equations
"""

import gi
from gi.repository import Gtk, Gdk, Adw

from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.figure import Figure
from .. import dialog

class LatexCanvas(FigureCanvas):
    __gtype_name__ = 'AlpacaLatexCanvas'

    def __init__(self, eq):
        fig = Figure(dpi=100)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot()
        ax.axis('off')
        text = ax.text(0.5, 0.5, eq, fontsize=24, ha='center', va='center')

        fig.tight_layout()
        fig.canvas.draw()
        bbox = text.get_window_extent()
        super().__init__(fig)
        self.set_content_width(bbox.width)
        self.set_css_classes(['latex_renderer'])
        self.set_sensitive(False)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/latex_renderer.ui')
class LatexRenderer(Gtk.Button):
    __gtype_name__ = 'AlpacaLatexRenderer'

    scrolled_window = Gtk.Template.Child()

    def __init__(self, content:str=None):
        super().__init__()
        self.equation = ""
        if content:
            self.set_content(content)

    def get_content(self) -> str:
        return '${}$'.format(self.equation)

    def get_content_for_dictation(self) -> str:
        return self.equation

    def set_content(self, content:str=None) -> None:
        content = content.strip()
        for p in ('\\[', '$$', '$'):
            content.removeprefix(p)
        for s in ('\\]', '$$', '$'):
            content.removesuffix(s)
        self.equation = content
        try:
            child = LatexCanvas(self.get_content())
            self.set_tooltip_text(_("Copy Equation"))
        except Exception as e:
            error = str(e).strip()
            child = Gtk.Label(
                label=error,
                css_classes=['error'],
                wrap=True
            )
            self.set_tooltip_text(error)
        self.scrolled_window.set_child(child)

    @Gtk.Template.Callback()
    def copy_equation(self, button=None) -> None:
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.get_content())
        dialog.show_toast(_("Equation copied to the clipboard"), self.get_root())

