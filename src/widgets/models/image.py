# image.py

from gi.repository import Gtk, Gio, Adw, Gdk
import logging, os
from ...constants import STT_MODELS, TTS_VOICES, REMBG_MODELS, data_dir, cache_dir
from .. import dialog
from .common import BasicModelDialog

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/background_remover_model_button.ui')
class BackgroundRemoverModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaBackgroundRemoverModelButton'

    title_label = Gtk.Template.Child()

    def __init__(self, model_name:str):
        super().__init__()
        self.set_name(model_name)
        self.model_title = REMBG_MODELS.get(model_name, {}).get('display_name', model_name.title())
        self.title_label.set_label(self.model_title)

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    @Gtk.Template.Callback()
    def on_click(self, button):
        dialog = BasicModelDialog(self)

        dialog.status_page.set_icon_name('image-missing-symbolic')
        author = REMBG_MODELS.get(self.get_name(), {}).get('author')
        if author:
            dialog.status_page.set_description(_("Local background removal model provided by {}.").format(author))
        dialog.status_page.set_child(
            Gtk.Label(
                label=REMBG_MODELS.get(self.get_name(), {}).get('size', '~151mb'),
                css_classes=["dim-label"]
            )
        )

        url = REMBG_MODELS.get(self.get_name(), {}).get('link')
        dialog.webpage_button.set_tooltip_text(url)
        dialog.webpage_button.set_visible(url)

        dialog.present(self.get_root())

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
                    'label': _('Delete Model'),
                    'callback': self.prompt_remove_model,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

    def remove_model(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, BackgroundRemoverModelDialog):
            dialog.close()

        file_path = os.path.join(data_dir, '.u2net', '{}.onnx'.format(self.get_name()))
        if os.path.isfile(file_path):
            os.remove(file_path)
        self.get_parent().get_parent().remove(self.get_parent())

    def prompt_remove_model(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        )

