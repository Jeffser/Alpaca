#model_widget.py
"""
Handles the model widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk
import logging, os, datetime, re, shutil, threading
from ..internal import config_dir, data_dir, cache_dir, source_dir

logger = logging.getLogger(__name__)

window = None

class model_selector_popup(Gtk.Popover):
    __gtype_name__ = 'AlpacaModelSelectorPopup'

    def __init__(self):
        manage_models_button = Gtk.Button(
            tooltip_text=_('Model Manager'),
            child=Gtk.Label(label=_('Model Manager')),
            hexpand=True,
            css_classes=['manage_models_button', 'flat']
        )
        manage_models_button.set_action_name("app.manage_models")
        manage_models_button.connect("clicked", lambda *_: self.hide())
        self.model_list_box = Gtk.ListBox(
            css_classes=['navigation-sidebar', 'model_list_box'],
            height_request=0
        )
        container = Gtk.Box(
            orientation=1,
            spacing=5
        )
        container.append(self.model_list_box)
        container.append(Gtk.Separator())
        container.append(manage_models_button)

        scroller = Gtk.ScrolledWindow(
            max_content_height=300,
            propagate_natural_width=True,
            propagate_natural_height=True,
            child=container
        )

        super().__init__(
            css_classes=['model_popover'],
            has_arrow=False,
            child=scroller
        )

class model_selector_button(Gtk.MenuButton):
    __gtype_name__ = 'AlpacaModelSelectorButton'

    def __init__(self):
        self.popover = model_selector_popup()
        self.popover.model_list_box.connect('selected-rows-changed', self.model_changed)
        self.popover.model_list_box.connect('row-activated', lambda *_: self.get_popover().hide())
        super().__init__(
            tooltip_text=_('Select a Model'),
            child=Adw.ButtonContent(
                label=_('Select a model'),
                icon_name='down-symbolic'
            ),
            popover=self.popover
        )

    def change_model(self, model_name:str):
        for model_row in list(self.get_popover().model_list_box):
            if model_name == model_row.get_name():
                self.get_popover().model_list_box.select_row(model_row)
                break

    def model_changed(self, listbox:Gtk.ListBox):
        row = listbox.get_selected_row()
        if row:
            model_name = row.get_name()
            self.get_child().set_label(window.convert_model_name(model_name, 0))
            self.set_tooltip_text(window.convert_model_name(model_name, 0))
        elif len(list(listbox)) == 0:
            self.get_child().set_label(_("Select a model"))
            self.set_tooltip_text(_("Select a Model"))

    def get_model(self) -> str:
        row = self.get_popover().model_list_box.get_selected_row()
        if row:
            return row.get_name()

    def add_model(self, model_name:str):
        model_row = Gtk.ListBoxRow(
            child = Gtk.Label(
                label=window.convert_model_name(model_name, 0),
                halign=1,
                hexpand=True
            ),
            halign=0,
            hexpand=True,
            name=model_name,
            tooltip_text=window.convert_model_name(model_name, 0)
        )
        self.get_popover().model_list_box.append(model_row)
        self.change_model(model_name)

    def get_model_list(self) -> list:
        return [model.get_name() for model in list(self.get_popover().model_list_box)]

    def clear_list(self):
        self.get_popover().model_list_box.remove_all()
