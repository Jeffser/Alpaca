# guide.py

from gi.repository import Adw, Gtk, Gio, GLib, Gdk
from .instances import OllamaManager, create_instance_row
from ..constants import is_ollama_installed, IN_FLATPAK
from ..sql_manager import generate_uuid, Instance as SQL

@Gtk.Template(resource_path='/com/jeffser/Alpaca/guide.ui')
class Guide(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaGuide'

    main_stack = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def begin_guide(self, button):
        self.main_stack.set_visible_child_name('instance')

    @Gtk.Template.Callback()
    def create_ollama_instance(self, button):
        row = create_instance_row({
            'properties': {
                'name': 'Alpaca',
                'url': 'http://127.0.0.1:11435'
            },
            'id': generate_uuid(),
            'type': 'ollama:managed'
        })
        row.instance.row = row

        def save_instance():
            SQL.insert_or_update_instance(
                instance_id=row.instance.instance_id,
                pinned=False,
                instance_type=row.instance.instance_type,
                properties=row.instance.properties
            )
            self.get_root().instance_listbox.append(row)
            self.get_root().instance_listbox.select_row(row)
            self.get_root().instance_manager_stack.set_visible_child_name('content')
            self.main_stack.set_visible_child_name('model')

        if is_ollama_installed():
            save_instance()
        else:
            dialog = OllamaManager(row.instance)
            dialog.connect('closed', lambda *_: save_instance() if is_ollama_installed() else None)
            dialog.present(self.get_root())

    @Gtk.Template.Callback()
    def create_external_instance(self, button):
        connection_id = None
        def row_selected(list_box, row):
            print(list_box, row)
            self.get_root().instance_listbox.disconnect(connection_id)
            if row.instance.instance_type != 'empty':
                self.main_stack.set_visible_child_name('model')

        self.get_root().add_instance(
            button=button,
            hide_ollama_managed=True
        )
        connection_id = self.get_root().instance_listbox.connect('row-selected', row_selected)

    @Gtk.Template.Callback()
    def open_end(self, button):
        self.main_stack.set_visible_child_name('end')

    @Gtk.Template.Callback()
    def close_guide(self, button):
        self.get_root().main_navigation_view.replace_with_tags(['chat'])

def show_EOL_flatpak_extension_dialog(window):
    if IN_FLATPAK:# and shutil.which('ollama'):
        def copy_command(btn):
            btn.set_icon_name('check-plain-symbolic')
            Gdk.Display().get_default().get_clipboard().set(btn.get_ancestor(Adw.ActionRow).get_subtitle())

        container = Gtk.Box(
            orientation=1,
            spacing=10
        )

        command_row = Adw.ActionRow(
            overflow=1,
            title=_("Uninstall Ollama Command"),
            subtitle="flatpak uninstall com.jeffser.Alpaca.Plugins.Ollama",
            css_classes = ["p0", "card", "black_background"]
        )
        list(list(list(command_row)[0])[2])[1].set_selectable(True)
        copy_button = Gtk.Button(
            tooltip_text=_("Copy Command"),
            icon_name="edit-copy-symbolic",
            valign=3,
            css_classes=['flat']
        )
        copy_button.connect('clicked', copy_command)
        command_row.add_suffix(copy_button)
        container.append(command_row)

        command_row = Adw.ActionRow(
            overflow=1,
            title=_("Uninstall ROCm Command"),
            subtitle="flatpak uninstall com.jeffser.Alpaca.Plugins.AMD",
            css_classes = ["p0", "card", "black_background"]
        )
        list(list(list(command_row)[0])[2])[1].set_selectable(True)
        copy_button = Gtk.Button(
            tooltip_text=_("Copy Command"),
            icon_name="edit-copy-symbolic",
            valign=3,
            css_classes=['flat']
        )
        copy_button.connect('clicked', copy_command)
        command_row.add_suffix(copy_button)
        container.append(command_row)

        dialog = Adw.AlertDialog(
            heading=_("Deprecated Extension Found"),
            body=_("As of Alpaca 9, the Flatpak extensions are no longer used, make sure to uninstall them to save space in your device and to stop this dialog from appearing."),
            extra_child=container
        )

        dialog.add_response(
            id='close',
            label=_('Close')
        )
        GLib.idle_add(dialog.choose, window)
