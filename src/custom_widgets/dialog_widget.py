#dialog_widget.py
"""
Handles all dialogs
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, Gio, Adw, Gdk, GLib

window=None

button_appearance={
    'suggested': Adw.ResponseAppearance.SUGGESTED,
    'destructive': Adw.ResponseAppearance.DESTRUCTIVE
}

# Don't call this directly outside this script
class baseDialog(Adw.AlertDialog):
    __gtype_name__ = 'AlpacaDialogBase'

    def __init__(self, heading:str, body:str, close_response:str, options:dict):
        self.options = options
        super().__init__(
            heading=heading,
            body=body,
            close_response=close_response
        )
        for option, data in self.options.items():
            self.add_response(option, option)
            if 'appearance' in data:
                self.set_response_appearance(option, button_appearance[data['appearance']])
            if 'default' in data and data['default']:
                self.set_default_response(option)


class Options(baseDialog):
    __gtype_name__ = 'AlpacaDialogOptions'

    def __init__(self, heading:str, body:str, close_response:str, options:dict):
        super().__init__(
            heading,
            body,
            close_response,
            options
        )
        self.choose(
            parent = window,
            cancellable = None,
            callback = self.response
        )

    def response(self, dialog, task):
        result = dialog.choose_finish(task)
        if result in self.options and 'callback' in self.options[result]:
            self.options[result]['callback']()

class Entry(baseDialog):
    __gtype_name__ = 'AlpacaDialogEntry'

    def __init__(self, heading:str, body:str, close_response:str, options:dict, entries:list or dict):
        super().__init__(
            heading,
            body,
            close_response,
            options
        )

        self.container = Gtk.Box(
            orientation=1,
            spacing=10
        )

        if isinstance(entries, dict):
            entries = [entries]

        for data in entries:
            entry = Gtk.Entry()
            if 'placeholder' in data and data['placeholder']:
                entry.set_placeholder_text(data['placeholder'])
            if 'css' in data and data['css']:
                entry.set_css_classes(data['css'])
            if 'text' in data and data['text']:
                entry.set_text(data['text'])
            self.container.append(entry)

        self.set_extra_child(self.container)

        self.connect('realize', lambda *_: list(self.container)[0].grab_focus())
        self.choose(
            parent = window,
            cancellable = None,
            callback = self.response
        )

    def response(self, dialog, task):
        result = dialog.choose_finish(task)
        if result in self.options and 'callback' in self.options[result]:
            entry_results = []
            for entry in list(self.container):
                entry_results.append(entry.get_text())
            self.options[result]['callback'](*entry_results)

class DropDown(baseDialog):
    __gtype_name__ = 'AlpacaDialogDropDown'

    def __init__(self, heading:str, body:str, close_response:str, options:dict, items:list):
        super().__init__(
            heading,
            body,
            close_response,
            options
        )
        string_list = Gtk.StringList()
        for item in items:
            string_list.append(item)
        self.set_extra_child(Gtk.DropDown(
            enable_search=len(items) > 10,
            model=string_list
        ))

        self.connect('realize', lambda *_: self.get_extra_child().grab_focus())
        self.choose(
            parent = window,
            cancellable = None,
            callback = lambda dialog, task, dropdown=self.get_extra_child(): self.response(dialog, task, dropdown.get_selected_item().get_string())
        )

    def response(self, dialog, task, item:str):
        result = dialog.choose_finish(task)
        if result in self.options and 'callback' in self.options[result]:
            self.options[result]['callback'](item)

def simple(heading:str, body:str, callback:callable, button_name:str=_('Accept'), button_appearance:str='suggested'):
    options = {
        _('Cancel'): {},
        button_name: {
            'appearance': button_appearance,
            'callback': callback,
            'default': True
        }
    }

    return Options(heading, body, 'cancel', options)

def simple_entry(heading:str, body:str, callback:callable, entries:list or dict, button_name:str=_('Accept'), button_appearance:str='suggested'):
    options = {
        _('Cancel'): {},
        button_name: {
            'appearance': button_appearance,
            'callback': callback,
            'default': True
        }
    }

    return Entry(heading, body, 'cancel', options, entries)

def simple_dropdown(heading:str, body:str, callback:callable, items:list, button_name:str=_('Accept'), button_appearance:str='suggested'):
    options = {
        _('Cancel'): {},
        button_name: {
            'appearance': button_appearance,
            'callback': callback,
            'default': True
        }
    }

    return DropDown(heading, body, 'cancel', options, items)

def simple_file(file_filter:Gtk.FileFilter, callback:callable):
    file_dialog = Gtk.FileDialog(default_filter=file_filter)
    file_dialog.open(window, None, lambda file_dialog, result: callback(file_dialog.open_finish(result)) if result else None)

