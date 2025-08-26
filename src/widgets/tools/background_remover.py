# background_remover.py

from gi.repository import Adw, Gtk, Gio, Gdk, GdkPixbuf, GLib

import os, threading, base64, importlib.util
from .tools import Base
from PIL import Image
from io import BytesIO

from .. import activities, dialog, models, attachments
from ...constants import data_dir, REMBG_MODELS
from ...sql_manager import generate_uuid, Instance as SQL

class BackgroundRemoverPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaBackgroundRemoverPage'

    def __init__(self, save_func:callable=None, close_callback:callable=None):
        self.save_func = save_func
        self.close_callback = close_callback
        self.input_image_data = None
        self.output_image_data = None
        container = Gtk.Box(
            orientation=1,
            spacing=10,
            vexpand=True,
            css_classes=['p10']
        )

        super().__init__(
            child=container,
            hexpand=True
        )

        big_select_button = Gtk.Button(
            child=Adw.ButtonContent(
                label=_("Select Image"),
                icon_name="image-x-generic-symbolic",
                tooltip_text=_("Select Image")
            ),
            halign=3,
            valign=3,
            css_classes=['suggested-action', 'pill']
        )
        big_select_button.connect('clicked', lambda *_: self.load_image_requested())
        self.input_container = Adw.Bin(
            child=big_select_button,
            halign=3,
            vexpand=True,
            css_classes=['p10']
        )
        container.append(self.input_container)
        self.output_container = Gtk.Stack(
            visible=False,
            halign=3,
            vexpand=True,
            css_classes=['p10']
        )
        self.output_container.add_named(
            Adw.Spinner(
                width_request=140,
                height_request=140
            ),
            'loading'
        )
        self.output_container.add_named(
            Adw.Bin(),
            'result'
        )
        container.append(self.output_container)
        self.pulling_model = None

        string_list = Gtk.StringList()
        for m in REMBG_MODELS.values():
            string_list.append('{} ({})'.format(m.get('display_name'), m.get('size')) )
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))
        self.model_dropdown = Gtk.DropDown(
            model=string_list,
            factory=factory,
            halign=3
        )
        self.select_button = Gtk.Button(
            icon_name="image-x-generic-symbolic",
            tooltip_text=_("Select Image")
        )
        self.select_button.connect('clicked', lambda *_: self.load_image_requested())

        self.download_button = Gtk.Button(
            icon_name='folder-download-symbolic',
            tooltip_text=_("Download Result"),
            sensitive=False
        )
        self.download_button.connect('clicked', lambda *_: self.prompt_download())

        self.buttons = [self.model_dropdown, self.select_button, self.download_button]
        self.title = _("Background Remover")
        self.activity_icon = 'image-missing-symbolic'

    def run(self, model_name:str):
        self.output_container.set_visible_child_name('loading')
        self.output_container.set_visible(True)
        self.select_button.set_sensitive(False)
        self.download_button.set_sensitive(False)
        from rembg import remove, new_session
        session = new_session(model_name)
        input_image = Image.open(BytesIO(base64.b64decode(self.input_image_data)))
        output_image = remove(input_image, session=session)
        buffered = BytesIO()
        output_image.save(buffered, format="PNG")

        self.output_image_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        self.output_container.get_child_by_name('result').set_child(self.make_image(self.output_image_data))
        self.output_container.set_visible_child_name('result')

        self.select_button.set_sensitive(True)
        self.download_button.set_sensitive(True)
        if self.pulling_model:
            threading.Thread(target=self.pulling_model.update_progressbar, args=({'status': 'success'},)).start()
        if self.save_func:
            self.save_func(self.output_image_data)

    def prepare_model_download(self, model_name:str):
        self.pulling_model = models.pulling.PullingModelButton(
            model_name,
            lambda model_name, window=self.get_root(): models.common.prepend_added_model(window, models.image.BackgroundRemoverModelButton(model_name)),
            None,
            False
        )
        models.common.prepend_added_model(self.get_root(), self.pulling_model)
        threading.Thread(target=self.run, args=(model_name,)).start()

    def verify_model(self):
        model = list(REMBG_MODELS)[self.model_dropdown.get_selected()]
        model_dir = os.path.join(data_dir, '.u2net')
        if os.path.isdir(model_dir) and '{}.onnx'.format(model) in os.listdir(model_dir):
            threading.Thread(target=self.run, args=(model,)).start()
        else:
            GLib.idle_add(dialog.simple,
                self.get_root(),
                _('Download Background Removal Model'),
                _("To use this tool you'll need to download a special model ({})").format(REMBG_MODELS.get(model, {}).get('size')),
                lambda m=model: self.prepare_model_download(model)
            )

    def make_image(self, image_data:str):
        data = base64.b64decode(image_data)
        loader = GdkPixbuf.PixbufLoader.new()
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        height = int((pixbuf.get_property('height') * 240) / pixbuf.get_property('width'))
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        image = Gtk.Picture.new_for_paintable(texture)
        image.set_size_request(240, height)
        return image

    def load_image(self, image_data:str):
        self.input_image_data = image_data
        image = self.make_image(self.input_image_data)
        image.add_css_class('r10')
        image.set_valign(3)
        self.input_container.set_child(image)
        self.verify_model()

    def on_attachment(self, file:Gio.File, remove_original:bool=False):
        if not file:
            return
        self.load_image(attachments.extract_image(file.get_path(), self.get_root().settings.get_value('max-image-size').unpack()))

    def load_image_requested(self):
        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = [file_filter],
            callback = self.on_attachment
        )

    def on_download(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            path = file.get_path()
            if path:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(self.output_image_data))
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
        except GLib.Error as e:
            logger.error(e)

    def prompt_download(self):
        dialog = Gtk.FileDialog(
            title=_("Save Image"),
            initial_name='output.png'
        )
        dialog.save(self.get_root(), None, self.on_download, None)

    def on_reload(self):
        pass

    def on_close(self):
        if self.close_callback:
            self.close_callback()

if importlib.util.find_spec('rembg'):
    class BackgroundRemover(Base):
        tool_metadata = {
            "name": "background_remover",
            "description": "Removes the background of the image provided by the user",
            "parameters": {}
        }
        name = _("Image Background Remover")
        description = _("Removes the background of the last image sent")
        variables = {
            'model': {
                'display_name': _("Background Remover Model"),
                'value': 0,
                'type': 'options',
                'options': ['{} ({})'.format(m.get('display_name'), m.get('size')) for m in REMBG_MODELS.values()]
            }
        }

        def on_save(self, data:str, bot_message):
            if data:
                attachment = bot_message.add_attachment(
                    file_id=generate_uuid(),
                    name=_('Output'),
                    attachment_type='image',
                    content=data
                )
                SQL.insert_or_update_attachment(bot_message, attachment)
                self.status = 1
            else:
                self.status = 2

        def on_close(self):
            self.status = 2

        def run(self, arguments, messages, bot_message) -> tuple:
            threading.Thread(target=bot_message.update_message, args=(_('Loading Image...') + '\n',)).start()
            image_b64 = self.get_latest_image(messages)
            if image_b64:
                self.status = 0 # 0 waiting, 1 finished, 2 canceled / empty image
                model_index = self.variables.get('model', {}).get('value', 0)
                page = BackgroundRemoverPage(
                    save_func=lambda data, bm=bot_message: self.on_save(data, bm),
                    close_callback=self.on_close
                )
                page.model_dropdown.set_selected(model_index)
                GLib.idle_add(
                    activities.show_activity,
                    page,
                    bot_message.get_root(),
                    not bot_message.chat.chat_id
                )
                page.load_image(image_b64)

                while self.status == 0:
                    continue

                if self.status == 1:
                    return False, "**Model Used: **{}\n**Status: **Background removed successfully!".format(list(REMBG_MODELS)[model_index])
                else:
                    return False, "An error occurred"
            else:
                return False, "Error: User didn't attach an image"
            return False, "Error: Couldn't remove the background"

