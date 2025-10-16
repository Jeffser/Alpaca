from ...sql_manager import Instance as SQL
from gi.repository import Gtk, GObject, Gio, Adw
import importlib.util
from .tools import Base

class ToolSelector(Gtk.DropDown):
    __gtype_name__ = 'AlpacaToolSelector'

    def __init__(self):
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self.on_item_setup)
        factory.connect('bind', self.on_item_bind)

        super().__init__(
            factory=factory,
            model=Gio.ListStore.new(Base)
        )

        for t in Base.__subclasses__():
            if all(importlib.util.find_spec(lib) for lib in t.required_libraries) or len(t.required_libraries) == 0:
                self.get_model().append(t())

        self.connect('realize', lambda *_: self.on_realize())

    def on_realize(self):
        list(list(self)[1].get_child())[1].set_propagate_natural_width(True)
        list(self)[0].add_css_class('flat')

    def model_changed(self, dropdown):
        if 'tools' in dropdown.get_selected_item().model.data.get('capabilities', ['tools']):
            self.set_sensitive(True)
            self.set_tooltip_text(_('Select a Tool To Use'))
        else:
            self.set_sensitive(False)
            self.set_selected(0)
            self.set_tooltip_text(_('Selected Model is Not Compatible With Tools'))

    def on_item_setup(self, factory, item):
        item.set_child(Adw.Bin())

    def on_item_bind(self, factory, item):
        item_data = item.get_item()
        icon = Gtk.Image.new_from_icon_name(
            item_data.icon_name
        )
        icon.add_css_class('dim-label')
        label = Gtk.Label(
            label=item_data.display_name,
            ellipsize=3,
            xalign=0
        )

        item.get_child().set_child(
            Gtk.Box(spacing=5)
        )
        item.get_child().get_child().append(icon)
        item.get_child().get_child().append(label)
