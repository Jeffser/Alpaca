# viewers.py

from gi.repository import Adw, Gtk, Gdk, GLib
from .. import blocks

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/image_viewer.ui')
class ImageViewer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaImageViewer'

    fixed = Gtk.Template.Child()
    picture = Gtk.Template.Child()
    delete_button = Gtk.Template.Child()
    download_button = Gtk.Template.Child()
    attach_button = Gtk.Template.Child()
    reset_button = Gtk.Template.Child()

    def __init__(self, texture:Gdk.Texture, title:str=_('Image'), delete_callback:callable=None, download_callback:callable=None, attachment_callback:callable=None):
        super().__init__()

        self.texture = texture
        self.picture.set_paintable(self.texture)

        self.delete_callback = delete_callback
        self.download_callback = download_callback
        self.attachment_callback = attachment_callback

        # State variables
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_start = None
        self.original_width = self.texture.get_width()
        self.original_height = self.texture.get_height()
        self.pointer_x = 0
        self.pointer_y = 0
        self.scrollable = False

        self.delete_button.set_visible(bool(self.delete_callback))
        self.download_button.set_visible(bool(self.download_callback))
        self.attach_button.set_visible(bool(self.attachment_callback))

        # Activity
        self.buttons = {
            'start': [
                self.delete_button,
                self.download_button,
                self.attach_button
            ],
            'end': [
                self.reset_button
            ]
        }
        self.extend_to_edge = True
        self.title = title
        self.activity_icon = 'image-x-generic-symbolic'

        self.loop_id = GLib.timeout_add(1, lambda: (self.update_picture() if not self.scrollable else None) or True)

        GLib.idle_add(self.on_reload)

    def on_reload(self):
        self.scale = self.get_min_scale()
        self.update_picture()

    def on_close(self):
        if self.loop_id:
            GLib.source_remove(self.loop_id)
        self.loop_id = None

    def get_min_scale(self):
        viewport_width = self.get_allocated_width()
        viewport_height = self.get_allocated_height()

        if self.original_width == 0 or self.original_height == 0:
            return 1.0

        scale_x = viewport_width / self.original_width
        scale_y = viewport_height / self.original_height

        return min(scale_x, scale_y)

    def update_picture(self):
        min_scale = self.get_min_scale()
        if self.scrollable:
            self.scale = max(self.scale, min_scale)
            self.scale = min(self.scale, min_scale + 5.0)
        else:
            self.scale = min_scale

        width = int(self.original_width * self.scale)
        height = int(self.original_height * self.scale)
        self.picture.set_size_request(width, height)

        viewport_width = self.get_allocated_width()
        viewport_height = self.get_allocated_height()

        x_offset = max((viewport_width - width) // 2, 0)
        y_offset = max((viewport_height - height) // 2, 0)

        self.fixed.move(self.picture, x_offset, y_offset)
        self.scrollable = self.scale != min_scale
        self.reset_button.set_sensitive(self.scrollable)

    def prepare_to_zoom(self, new_scale):
        mx = self.pointer_x
        my = self.pointer_y

        old_scale, self.scale = self.scale, new_scale

        if self.scale < self.get_min_scale() + 5.0:
            adj = self.get_hadjustment()
            adj.set_value((adj.get_value() + mx) * self.scale / old_scale - mx)
            vadj = self.get_vadjustment()
            vadj.set_value((vadj.get_value() + my) * self.scale / old_scale - my)

        self.scrollable = True
        self.reset_button.set_sensitive(True)
        self.update_picture()

    @Gtk.Template.Callback()
    def on_gesture_zoom(self, gesture, value):
        if value >= 1:
            value = self.scale + value / 10
        else:
            value = self.scale - value / 10
        self.prepare_to_zoom(value)

    @Gtk.Template.Callback()
    def delete_requested(self, button=None):
        if self.delete_callback:
            self.delete_callback(self.get_root())

    @Gtk.Template.Callback()
    def download_requested(self, button=None):
        if self.download_callback:
            self.download_callback(self.get_root())

    @Gtk.Template.Callback()
    def attach_requested(self, button=None):
        if self.attachment_callback:
            self.attachment_callback()

    @Gtk.Template.Callback()
    def reset_view_requested(self, button=None):
        self.on_reload()

    @Gtk.Template.Callback()
    def on_motion(self, controller, x, y):
        self.pointer_x = x
        self.pointer_y = y

    @Gtk.Template.Callback()
    def on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if not (state & Gdk.ModifierType.CONTROL_MASK):
            return False
        event = controller.get_current_event()
        if event is None:
            return False

        self.prepare_to_zoom(self.scale * 1.1 if dy < 0 else 0.9)
        return True

    @Gtk.Template.Callback()
    def on_drag_update(self, gesture, dx, dy):
        adj = self.get_hadjustment()
        vadj = self.get_vadjustment()
        adj.set_value(adj.get_value() - dx)
        vadj.set_value(vadj.get_value() - dy)

    def close(self):
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.close_page(parent.get_page(self))
        else:
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/file_viewer.ui')
class FileViewer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaFileViewer'

    container = Gtk.Template.Child()
    delete_button = Gtk.Template.Child()
    download_button = Gtk.Template.Child()

    def __init__(self, attachment):
        self.attachment = attachment
        super().__init__()

        self.delete_button.set_visible(self.attachment.file_type != 'model_context')

        # Activity
        self.buttons = {
            'start': [self.delete_button, self.download_button],
            'end': []
        }
        self.extend_to_edge = False
        self.title = self.attachment.file_name
        self.activity_icon = self.attachment.get_child().get_icon_name()

        content = self.attachment.get_content()
        for block in blocks.text_to_block_list(content):
            self.container.append(block)

    @Gtk.Template.Callback()
    def delete_requested(self, button):
        self.attachment.prompt_delete(self.get_root())

    @Gtk.Template.Callback()
    def download_requested(self, button):
        self.attachment.prompt_download(self.get_root())

    def on_reload(self):
        pass

    def on_close(self):
        pass

    def close(self):
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.close_page(parent.get_page(self))
        else:
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()
