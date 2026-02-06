# selector.py

from gi.repository import Gtk, GObject, Gio, Adw
from .tools import Base
import importlib.util

tool_selector_model = Gio.ListStore.new(Base)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/tools/selector.ui')
class ToolSelector(Gtk.DropDown):
    __gtype_name__ = 'AlpacaToolSelector'

    def __init__(self):
        super().__init__(
            visible=False
        )
        global tool_selector_model

        self.set_model(tool_selector_model)
        tool_selector_model.connect('notify::n-items', self.n_items_changed)

        list(list(self)[1].get_child())[1].set_propagate_natural_width(True)
        list(self)[0].add_css_class('flat')

    def n_items_changed(self, model, gparam=None):
        self.set_enable_search(len(model) > 10) #TODO make this work
        self.set_visible(len(model) > 2)

    def model_changed(self, dropdown):
        if dropdown.get_selected_item() and 'tools' in dropdown.get_selected_item().model.data.get('capabilities', ['tools']):
            self.set_sensitive(True)
            self.set_selected(self.get_root().settings.get_value('default-tool').unpack())
            self.set_tooltip_text(_('Select a Tool To Use'))
        else:
            self.set_sensitive(False)
            self.set_selected(0)
            self.set_tooltip_text(_('Selected Model is Not Compatible With Tools'))

    @Gtk.Template.Callback()
    def on_item_setup(self, factory, item):
        item.set_child(Adw.Bin())

    @Gtk.Template.Callback()
    def on_item_bind(self, factory, item):
        item_data = item.get_item()
        icon = Gtk.Image.new_from_icon_name(
            item_data.icon_name
        )
        #icon.add_css_class('dim-label')
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


