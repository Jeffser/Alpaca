# background_remover.py

from gi.repository import Gtk, Gio, Adw, GLib, GdkPixbuf, Gdk
from ...constants import IN_FLATPAK, data_dir, REMBG_MODELS
from .. import dialog, attachments, models
import base64, os, threading
from PIL import Image
from io import BytesIO

class BackgroundRemoverPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaBackgroundRemoverPage'

    def __init__(self, save_func:callable=None, close_callback:callable=None):
        self.save_func = save_func
        self.close_callback = close_callback
        self.input_image_data = None
        self.output_image_data = None

        self.main_stack = Gtk.Stack(
            transition_type=1
        )

        # Main Button
        main_select_button = Gtk.Button(
            child=Adw.ButtonContent(
                label=_("Select Image"),
                icon_name="image-x-generic-symbolic",
                tooltip_text=_("Select Image")
            ),
            halign=3,
            valign=3,
            css_classes=['suggested-action', 'pill']
        )
        main_select_button.connect('clicked', lambda *_: self.load_image_requested())
        self.main_stack.add_named(
            main_select_button,
            'button'
        )

        # Container
        container = Gtk.Box(
            orientation=1,
            spacing=10,
            valign=3,
            halign=3
        )
        self.main_stack.add_named(
            container,
            'content'
        )
        ## Secondary Stack
        self.image_stack = Gtk.Stack(
            transition_type=6,
            hexpand=True,
            vexpand=True
        )
        ## Stack Switcher
        self.stack_switcher = Adw.ToggleGroup(
            halign=3
        )
        self.stack_switcher.connect('notify::active', lambda toggle_group, gparam: self.image_stack.set_visible_child_name(toggle_group.get_active_name()))
        self.stack_switcher.add(
            Adw.Toggle(
                label=_("Original"),
                name='input'
            )
        )
        self.stack_switcher.add(
            Adw.Toggle(
                label=_("Result"),
                name='output'
            )
        )
        container.append(self.stack_switcher)
        container.append(self.image_stack)
        ### Input Picture
        self.image_stack.add_named(
            Gtk.Picture(
                css_classes=['rounded_image'],
                margin_start=10,
                margin_end=10,
                margin_bottom=10
            ),
            'input'
        )
        ### Output Picture
        self.image_stack.add_named(
            Gtk.Overlay(
                child=Gtk.Picture(
                    css_classes=['rounded_image'],
                    margin_start=10,
                    margin_end=10,
                    margin_bottom=10
                )
            ),
            'output'
        )
        self.output_spinner = Adw.Spinner()
        self.image_stack.get_child_by_name('output').add_overlay(self.output_spinner)

        super().__init__(
            child=self.main_stack,
            hexpand=True
        )

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
        self.output_spinner.set_visible(True)
        self.stack_switcher.set_active_name('output')
        self.select_button.set_sensitive(False)
        self.download_button.set_sensitive(False)
        from rembg import remove, new_session
        session = new_session(model_name)
        input_image = Image.open(BytesIO(base64.b64decode(self.input_image_data)))
        output_image = remove(input_image, session=session)
        buffered = BytesIO()
        output_image.save(buffered, format="PNG")

        self.output_image_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        texture = self.make_texture(self.output_image_data)
        self.stack_switcher.set_active_name('output')
        self.image_stack.get_child_by_name('output').get_child().set_paintable(texture)
        self.image_stack.get_child_by_name('output').get_child().remove_css_class('loading_image')
        self.output_spinner.set_visible(False)
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

    def make_texture(self, image_data:str):
        data = base64.b64decode(image_data)
        loader = GdkPixbuf.PixbufLoader.new()
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        height = int((pixbuf.get_property('height') * 240) / pixbuf.get_property('width'))
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        return texture

    def load_image(self, image_data:str):
        self.input_image_data = image_data
        texture = self.make_texture(self.input_image_data)
        self.image_stack.get_child_by_name('input').set_paintable(texture)
        self.image_stack.get_child_by_name('output').get_child().set_paintable(texture)
        self.image_stack.get_child_by_name('output').get_child().add_css_class('loading_image')
        self.main_stack.set_visible_child_name('content')
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
