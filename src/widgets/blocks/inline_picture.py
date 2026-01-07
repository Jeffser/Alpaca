# inline_picture.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, base64
from .. import dialog, activities, attachments

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/blocks/inline_picture.ui')
class InlinePicture(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaInlinePicture'

    button = Gtk.Template.Child()

    def __init__(self, url:str):
        super().__init__()
        self.url = url
        self.activity = None
        self.texture = None
        self.content = None

        try:
            self.content = attachments.extract_online_image(
                image_url=self.url,
                max_size=480
            )
            image_data = base64.b64decode(self.content)
            self.texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            image = Gtk.Picture.new_for_paintable(self.texture)
            image.set_size_request(int((self.texture.get_width() * 240) / self.texture.get_height()), 240)
            self.button.set_tooltip_text(_("Image"))
            self.button.set_child(image)
            self.button.set_sensitive(True)
        except Exception as e:
            logger.error(e)

    def get_content(self) -> str:
        return '![]({})'.format(self.url)

    def get_content_for_dictation(self) -> str:
        return '[IMAGE]'

    def on_download(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            path = file.get_path()
            if path:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(self.content))
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
        except GLib.Error as e:
            logger.error(e)

    def prompt_download(self, override_root=None):
        name = 'image.png'
        name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)

        dialog = Gtk.FileDialog(
            title=_("Save Image"),
            initial_name=name
        )
        dialog.save(override_root or self.get_root(), None, self.on_download, None)

    @Gtk.Template.Callback()
    def show_activity(self, button=None):
        if self.activity and self.activity.get_root():
            self.activity.on_reload()
        elif self.texture:
            page = activities.ImageViewer(
                texture=self.texture,
                title=_("Image"),
                delete_callback=None,
                download_callback=self.prompt_download
            )
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

        actions = [
            [
                {
                    'label': _('Download Image'),
                    'callback': self.prompt_download,
                    'icon': 'folder-download-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()
