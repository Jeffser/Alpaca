#dialog.py
"""
Handles all dialogs
"""

import gi
from gi.repository import Gtk, Gio, Adw, GLib

button_appearance={
    'suggested': Adw.ResponseAppearance.SUGGESTED,
    'destructive': Adw.ResponseAppearance.DESTRUCTIVE
}

def get_dialog_showing(parent:Gtk.Widget) -> bool:
    return any([True for dt in (Options, Entry, DropDown, Adw.Dialog) if isinstance(parent.get_visible_dialog(), dt)])

# Don't call this directly outside this script
class Base(Adw.AlertDialog):
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


class Options(Base):
    __gtype_name__ = 'AlpacaDialogOptions'

    def __init__(self, heading:str, body:str, close_response:str, options:dict):
        super().__init__(
            heading,
            body,
            close_response,
            options
        )

    def response(self, result:str):
        self.close()
        if 'callback' in self.options.get(result, {}):
            self.options[result]['callback']()

    def show(self, parent:Gtk.Widget):
        if not get_dialog_showing(parent):
            self.choose(
                parent = parent,
                cancellable = None,
                callback = lambda dialog, task: self.response(dialog.choose_finish(task))
            )

class Entry(Base):
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

        default_action = [name for name, value in options.items() if value.get('default', False)]
        for i, entry in enumerate(list(self.container)):
            if i < len(list(self.container)) - 1:
                entry.connect('activate', lambda *_, index=i: list(self.container)[index+1].grab_focus())
            elif default_action:
                entry.connect('activate', lambda *_, action=default_action[0]: self.response(action))

        self.set_extra_child(self.container)

        self.connect('realize', lambda *_: list(self.container)[0].grab_focus())

    def response(self, result:str):
        self.close()
        if 'callback' in self.options.get(result, {}):
            entry_results = []
            for entry in list(self.container):
                entry_results.append(entry.get_text())
            self.options[result]['callback'](*entry_results)

    def show(self, parent:Gtk.Widget):
        if not get_dialog_showing(parent):
            self.choose(
                parent = parent,
                cancellable = None,
                callback = lambda dialog, task: self.response(dialog.choose_finish(task))
            )

class DropDown(Base):
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
            model=string_list
        ))

        self.connect('realize', lambda *_: self.get_extra_child().grab_focus())

    def response(self, result:str, item:str):
        self.close()
        if 'callback' in self.options.get(result, {}):
            self.options[result]['callback'](item)

    def show(self, parent:Gtk.Widget):
        if not get_dialog_showing(parent):
            self.choose(
                parent = parent,
                cancellable = None,
                callback = lambda dialog, task, dropdown=self.get_extra_child(): self.response(dialog.choose_finish(task), dropdown.get_selected_item().get_string())
            )

def simple(parent:Gtk.Widget, heading:str, body:str, callback:callable, button_name:str=_('Accept'), button_appearance:str='suggested'):
    options = {
        _('Cancel'): {},
        button_name: {
            'appearance': button_appearance,
            'callback': callback,
            'default': True
        }
    }

    dialog = Options(heading, body, list(options.keys())[0], options)
    dialog.show(parent)

def simple_entry(parent:Gtk.Widget, heading:str, body:str, callback:callable, entries:list or dict, button_name:str=_('Accept'), button_appearance:str='suggested'):
    options = {
        _('Cancel'): {},
        button_name: {
            'appearance': button_appearance,
            'callback': callback,
            'default': True
        }
    }

    dialog = Entry(heading, body, list(options.keys())[0], options, entries)
    dialog.show(parent)

def simple_dropdown(parent:Gtk.Widget, heading:str, body:str, callback:callable, items:list, button_name:str=_('Accept'), button_appearance:str='suggested'):
    options = {
        _('Cancel'): {},
        button_name: {
            'appearance': button_appearance,
            'callback': callback,
            'default': True
        }
    }

    dialog = DropDown(heading, body, list(options.keys())[0], options, items)
    dialog.show(parent)

def simple_log(parent:Gtk.Widget, title:str, summary_text:str, summary_classes:list, log_text:str):
    if get_dialog_showing(parent):
        return
    container = Gtk.Box(
        hexpand=True,
        vexpand=True,
        orientation=1,
        spacing=10,
        css_classes=['p10']
    )
    container.append(Gtk.Label(
        label=summary_text,
        wrap=True,
        wrap_mode=2,
        css_classes=summary_classes,
        use_markup=True,
        justify=2
    ))
    container.append(Gtk.ScrolledWindow(
        min_content_width=300,
        hscrollbar_policy=2,
        propagate_natural_height=True,
        propagate_natural_width=True,
        css_classes=['card', 'undershoot-bottom'],
        overflow=True,
        child=Gtk.Label(
            css_classes=['p10', 'monospace'],
            label=log_text,
            wrap=True,
            wrap_mode=2,
            selectable=True
        )
    ))

    tbv = Adw.ToolbarView()
    tbv.add_top_bar(Adw.HeaderBar())
    tbv.set_content(container)

    dialog = Adw.Dialog(
        title=title,
        follows_content_size=True,
        child=tbv
    )

    GLib.idle_add(dialog.present, parent)

def simple_error(parent:Gtk.Widget, title:str, body:str, error_log:str, callback:callable=None):
    if get_dialog_showing(parent):
        return
    container = Gtk.Box(
        hexpand=True,
        vexpand=True,
        orientation=1,
        spacing=10,
        css_classes=['p10']
    )
    container.append(Gtk.Label(
        label=body,
        wrap=True,
        wrap_mode=2
    ))
    container.append(Gtk.ScrolledWindow(
        min_content_width=300,
        hscrollbar_policy=2,
        propagate_natural_height=True,
        propagate_natural_width=True,
        css_classes=['card', 'undershoot-bottom'],
        overflow=True,
        child=Gtk.Label(
            css_classes=['p10', 'monospace', 'error'],
            label=error_log,
            wrap=True,
            wrap_mode=2,
            selectable=True
        )
    ))

    tbv = Adw.ToolbarView()
    tbv.add_top_bar(Adw.HeaderBar())
    tbv.set_content(container)

    dialog = Adw.Dialog(
        title=title,
        follows_content_size=True,
        child=tbv
    )

    if callback:
        dialog.connect('closed', lambda *_: callback())

    GLib.idle_add(dialog.present, parent)

def simple_file(parent:Gtk.Widget, file_filters:list, callback:callable):
    filter_list = Gio.ListStore.new(Gtk.FileFilter)

    for item in file_filters:
        filter_list.append(item)

    def __open_finish_wrapper(dialog, result):
        try:
            return dialog.open_finish(result)
        except gi.repository.GLib.GError:
            return

    file_dialog = Gtk.FileDialog(
        default_filter=file_filters[0],
        filters=filter_list
    )

    file_dialog.open(
        parent,
        None,
        lambda file_dialog, result: callback(__open_finish_wrapper(file_dialog, result)) if result else None
    )

def simple_directory(parent:Gtk.Widget, callback:callable):
    def __select_folder_finish_wrapper(dialog, result):
        try:
            return dialog.select_folder_finish(result)
        except gi.repository.GLib.GError:
            return

    Gtk.FileDialog().select_folder(
        parent,
        None,
        lambda directory_dialog, result: callback(__select_folder_finish_wrapper(directory_dialog, result))
    )

def show_toast(message:str, root_widget, action:str=None, action_name:str=None):
    try:
        overlay = root_widget.toast_overlay
    except Exception as e:
        print(e)
        return
    toast = Adw.Toast(
        title=message,
        timeout=2
    )
    if action and action_name:
        toast.set_action_name(action)
        toast.set_button_label(action_name)
    overlay.add_toast(toast)

def show_notification(root_widget, title:str, body:str, icon:Gio.ThemedIcon=None):
    if not root_widget.is_active():
        body = body.replace('<span>', '').replace('</span>', '')
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        if icon:
            notification.set_icon(icon)
        root_widget.get_application().send_notification(None, notification)
