# background_remover.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ...constants import IN_FLATPAK, data_dir, REMBG_MODELS
from .. import dialog, attachments, models
import base64, os, threading
from PIL import Image
from io import BytesIO

class BackgroundRemoverImage(Gtk.Button):
    __gtype_name__ = 'AlpacaBackgroundRemoverImage'

    def __init__(self, name:str):
        super().__init__(
            child=Gtk.Picture(
                css_classes=['rounded_image']
            ),
            margin_start=5,
            margin_end=5,
            margin_bottom=5,
            css_classes=['flat'],
            tooltip_text=_('Open in Image Viewer'),
            name=name
        )

        self.connect('clicked', self.open_image_viewer)
        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def open_image_viewer(self, button):
        from . import show_activity
        page = attachments.AttachmentImagePage(
            texture=self.get_texture(),
            title=self.get_name(),
            download_callback=lambda ovr: self.prompt_download(ovr),
            attachment_callback=lambda: self.on_attachment()
        )
        self.activity = show_activity(page, self.get_root())

    def get_texture(self) -> Gdk.Texture:
        return self.get_child().get_paintable()

    def set_texture(self, texture:Gdk.Texture):
        self.get_child().set_paintable(texture)

    def on_download(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            path = file.get_path()
            if path:
                self.get_texture().save_to_png(path)
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
        except GLib.Error as e:
            logger.error(e)

    def prompt_download(self, override_root=None):
        dialog = Gtk.FileDialog(
            title=_("Save Image"),
            initial_name='{}.png'.format(self.get_name())
        )
        dialog.save(override_root or self.get_root(), None, self.on_download, None)

    def on_attachment(self):
        image_data = self.get_texture().save_to_png_bytes().get_data()
        attachment = attachments.Attachment(
            file_id='-1',
            file_name=self.get_name(),
            file_type='image',
            file_content=base64.b64encode(image_data).decode('utf-8')
        )
        self.get_root().get_application().main_alpaca_window.global_footer.attachment_container.add_attachment(attachment)

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Download Image'),
                    'callback': self.prompt_download,
                    'icon': 'folder-download-symbolic'
                },
                {
                    'label': _('Attach Image'),
                    'callback': self.on_attachment,
                    'icon': 'chain-link-loose-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()


class BackgroundRemoverPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaBackgroundRemoverPage'

    def __init__(self, save_func:callable=None, close_callback:callable=None):
        self.save_func = save_func
        self.close_callback = close_callback

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
        self.input_picture_button = BackgroundRemoverImage(_('Original'))
        self.image_stack.add_named(
            self.input_picture_button,
            'input'
        )

        ### Output Picture
        self.output_picture_button = BackgroundRemoverImage(_('Result'))
        self.image_stack.add_named(
            Gtk.Overlay(
                child=self.output_picture_button
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
            factory=factory
        )
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)

        self.select_button = Gtk.Button(
            icon_name="image-x-generic-symbolic",
            tooltip_text=_("Select Image")
        )
        self.select_button.connect('clicked', lambda *_: self.load_image_requested())

        self.buttons = [self.model_dropdown, self.select_button]
        self.title = _("Background Remover")
        self.activity_icon = 'image-missing-symbolic'

    def set_status(self, generating:bool):
        self.output_spinner.set_visible(generating)
        if generating:
            self.stack_switcher.set_active_name('output')
        self.model_dropdown.set_sensitive(not generating)
        self.select_button.set_sensitive(not generating)

        if generating:
            self.output_picture_button.get_child().add_css_class('loading_image')
        else:
            self.output_picture_button.get_child().remove_css_class('loading_image')

    def run(self, model_name:str, input_image_data):
        self.set_status(True)

        from rembg import remove, new_session
        session = new_session(model_name)
        input_image = Image.open(BytesIO(base64.b64decode(input_image_data)))
        output_image = remove(input_image, session=session)
        buffered = BytesIO()
        output_image.save(buffered, format="PNG")

        output_image_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        texture = self.make_texture(output_image_data)
        self.output_picture_button.set_texture(texture)

        self.set_status(False)

        if self.pulling_model:
            threading.Thread(target=self.pulling_model.update_progressbar, args=({'status': 'success'},)).start()
        if self.save_func:
            self.save_func(output_image_data)

    def prepare_model_download(self, model_name:str, input_image_data):
        self.pulling_model = models.pulling.PullingModelButton(
            model_name,
            lambda model_name, window=self.get_root(): models.common.prepend_added_model(window, models.image.BackgroundRemoverModelButton(model_name)),
            None,
            False
        )
        models.common.prepend_added_model(self.get_root(), self.pulling_model)
        threading.Thread(target=self.run, args=(model_name, input_image_data)).start()

    def verify_model(self, input_image_data):
        model = list(REMBG_MODELS)[self.model_dropdown.get_selected()]
        model_dir = os.path.join(data_dir, '.u2net')
        if os.path.isdir(model_dir) and '{}.onnx'.format(model) in os.listdir(model_dir):
            threading.Thread(target=self.run, args=(model, input_image_data)).start()
        else:
            GLib.idle_add(dialog.simple,
                self.get_root(),
                _('Download Background Removal Model'),
                _("To use this tool you'll need to download a special model ({})").format(REMBG_MODELS.get(model, {}).get('size')),
                lambda m=model: self.prepare_model_download(model, input_image_data)
            )

    def make_texture(self, data:str):
        image_data = base64.b64decode(data)
        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
        return texture

    def load_image(self, image_data:str):
        input_image_data = image_data
        texture = self.make_texture(input_image_data)
        self.input_picture_button.set_texture(texture)
        self.output_picture_button.set_texture(texture)
        self.main_stack.set_visible_child_name('content')
        self.verify_model(input_image_data)

    def on_loaded(self, file:Gio.File, remove_original:bool=False):
        if not file:
            return
        self.load_image(attachments.extract_image(file.get_path(), self.get_root().settings.get_value('max-image-size').unpack()))

    def load_image_requested(self):
        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = [file_filter],
            callback = self.on_loaded
        )

    def on_reload(self):
        pass

    def on_close(self):
        if self.close_callback:
            self.close_callback()
