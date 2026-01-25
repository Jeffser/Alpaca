# export_page.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import getpass, time, json, io, base64
from .. import dialog
from ...sql_manager import Instance as SQL

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/characters/export_page.ui')
class CharacterExportPage(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaCharacterExportPage'

    creator_el = Gtk.Template.Child()
    character_version_el = Gtk.Template.Child()
    character_book_name_el = Gtk.Template.Child()
    character_book_description_el = Gtk.Template.Child()
    creator_notes_el = Gtk.Template.Child()
    add_tag_button = Gtk.Template.Child()
    tag_wrapbox = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.creator_el.set_text((getpass.getuser() or '').title())

    def export(self, file_dialog, result, character_dict, picture_b64):
        file = file_dialog.save_finish(result)
        if file:
            image_data = base64.b64decode(picture_b64)
            image_file = io.BytesIO(image_data)
            with Image.open(image_file) as img:
                img.load()
                metadata = PngInfo()
                metadata.add_text('chara', json.dumps(character_dict))

                img.save(
                    file.get_path(),
                    format="PNG",
                    pnginfo=metadata,
                    exif=img.info.get('exif'),
                    dpi=img.info.get('dpi')
                )

            toast_overlay = self.get_ancestor(Adw.ToastOverlay)
            toast = Adw.Toast(
                title=_("Character Card Exported Successfully")
            )
            toast_overlay.add_toast(toast)
            navigation_view = self.get_ancestor(Adw.NavigationView)
            navigation_view.pop_to_tag('model')

    @Gtk.Template.Callback()
    def export_requested(self, button):
        model_id = self.get_ancestor(Adw.Dialog).model.get_name()
        model_preferences = SQL.get_model_preferences(model_id)
        picture_b64 = model_preferences.get('picture')

        if not picture_b64:
            toast_overlay = self.get_ancestor(Adw.ToastOverlay)
            toast = Adw.Toast(
                title=_("Error Exporting Character Card")
            )
            toast_overlay.add_toast(toast)
            navigation_view = self.get_ancestor(Adw.NavigationView)
            navigation_view.pop_to_tag('model')
            return

        character_dict = model_preferences.get('character', {})

        character_dict['data']['creator'] = self.creator_el.get_text()
        character_dict['data']['character_version'] = self.character_version_el.get_text()
        character_dict['data']['character_book']['name'] = self.character_book_name_el.get_text()
        character_dict['data']['character_book']['description'] = self.character_book_description_el.get_text()
        character_dict['data']['creator_notes'] = self.creator_notes_el.get_text()
        character_dict['data']['tags'] = [t.get_name() for t in list(self.tag_wrapbox)[1:]]
        character_dict['data']['modification_date'] = int(time.time() * 1000)

        SQL.insert_or_update_model_character(model_id, character_dict)

        file_dialog = Gtk.FileDialog(
            initial_name='{}.png'.format(_("Character Card"))
        )
        file_dialog.save(
            self.get_root(),
            None,
            self.export,
            character_dict,
            picture_b64
        )

    @Gtk.Template.Callback()
    def add_tag_requested(self, button):
        def add_tag(tag:str):
            button = Gtk.Button(
                name=tag,
                child=Adw.ButtonContent(
                    label=tag,
                    icon_name="cross-large-symbolic"
                ),
                css_classes=["small_button", "circular", "button_no_bold"],
                tooltip_text=_("Remove Tag")
            )
            button.connect('clicked', lambda btn: btn.unparent())
            self.tag_wrapbox.insert_child_after(button, self.add_tag_button)

        dialog.simple_entry(
            parent=self.get_root(),
            heading=_("Add Tag"),
            body="",
            callback=add_tag,
            entries={'placeholder': _("Tag")}
        )
