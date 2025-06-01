# latex.py
"""
Representation of Latex equations
"""

import gi
from gi.repository import Gtk, Gdk, Adw

from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.figure import Figure
from .. import dialog

class LatexRenderer(Gtk.Button):
    __gtype_name__ = 'AlpacaLatexRenderer'

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
            self.set_hexpand(True)
            self.set_vexpand(True)
            self.set_size_request(-1, bbox.height)
            self.set_content_width(bbox.width)
            self.set_css_classes(['latex_renderer'])
            self.set_sensitive(False)

    def __init__(self, content:str=None):
        super().__init__(
            child=Adw.Spinner(),
            css_classes=['flat', 'p10'],
            tooltip_text=_('Copy Equation')
        )
        self.connect('clicked', lambda button: self.copy_equation())
        if content:
            self.set_content(content)

    def get_content(self) -> str:
        return '${}$'.format(self.equation)

    def set_content(self, value:str) -> None:
        value = value.strip()
        for p in ('\\[', '$$', '$'):
            value.removeprefix(p)
        for s in ('\\]', '$$', '$'):
            value.removesuffix(s)
        self.equation = value
        child = self.get_child()
        try:
            child = Gtk.ScrolledWindow(
                propagate_natural_height=True,
                hscrollbar_policy=1,
                vscrollbar_policy=2,
                child=self.LatexCanvas(self.get_content())
            )
        except Exception as e:
            child = Gtk.Label(
                label=str(e).strip(),
                css_classes=['error'],
                wrap=True
            )
        self.set_child(child)

    def copy_equation(self):
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.content)
        dialog.show_toast(_("Equation copied to the clipboard"), self.get_root())
