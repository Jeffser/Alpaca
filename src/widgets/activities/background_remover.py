# background_remover.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ...constants import IN_FLATPAK, data_dir, REMBG_MODELS
from .. import dialog, attachments, models
import base64, os, threading
from PIL import Image
from io import BytesIO

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/background_remover_image.ui')
class BackgroundRemoverImage(Gtk.Button):
    __gtype_name__ = 'AlpacaBackgroundRemoverImage'

    @Gtk.Template.Callback()
    def open_image_viewer(self, button):
        from . import show_activity, ImageViewer
        page = ImageViewer(
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
        self.get_root().get_application().get_main_window().global_footer.attachment_container.add_attachment(attachment)

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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/background_remover.ui')
class BackgroundRemover(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaBackgroundRemover'

    main_stack = Gtk.Template.Child()
    stack_switcher = Gtk.Template.Child()
    image_stack = Gtk.Template.Child()

    model_dropdown = Gtk.Template.Child()
    select_button = Gtk.Template.Child()

    input_picture_button = Gtk.Template.Child()
    output_picture_button = Gtk.Template.Child()
    output_spinner = Gtk.Template.Child()

    def __init__(self, save_func:callable=None, close_callback:callable=None):
        self.save_func = save_func
        self.close_callback = close_callback
        super().__init__()

        self.pulling_model = None

        selected_index = Gio.Settings(schema_id="com.jeffser.Alpaca").get_value('activity-background-remover-model').unpack()
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))
        self.model_dropdown.set_factory(factory)
        for m in REMBG_MODELS.values():
            self.model_dropdown.get_model().append('{} ({})'.format(m.get('display_name'), m.get('size')) )
        self.model_dropdown.set_selected(selected_index)
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)

        self.stack_switcher.connect('notify::active', lambda toggle_group, gparam: self.image_stack.set_visible_child_name(toggle_group.get_active_name()))

        # ACTIVITY
        self.buttons = {
            'start': [self.select_button],
            'center': self.model_dropdown
        }
        self.extend_to_edge = False
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
            self.pulling_model.update_progressbar(-1)
        if self.save_func:
            self.save_func(output_image_data)

    def prepare_model_download(self, model_name:str, input_image_data):
        model_dir = os.path.join(data_dir, '.u2net', model_name)
        self.pulling_model = models.create_background_remover_model(model_dir)
        self.pulling_model.update_progressbar(1)
        models.common.append_added_model(self.get_root(), self.pulling_model)
        threading.Thread(target=self.run, args=(model_name, input_image_data), daemon=True).start()

    def verify_model(self, input_image_data):
        model = list(REMBG_MODELS)[self.model_dropdown.get_selected()]
        model_dir = os.path.join(data_dir, '.u2net')
        if os.path.isdir(model_dir) and '{}.onnx'.format(model) in os.listdir(model_dir):
            threading.Thread(target=self.run, args=(model, input_image_data), daemon=True).start()
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

    @Gtk.Template.Callback()
    def load_image_requested(self, button):
        def on_loaded(file:Gio.File, remove_original:bool=False):
            if not file:
                return
            self.load_image(attachments.extract_image(file.get_path(), self.get_root().settings.get_value('max-image-size').unpack()))

        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = [file_filter],
            callback = on_loaded
        )

    def on_reload(self):
        pass

    def on_close(self):
        if self.close_callback:
            self.close_callback()
