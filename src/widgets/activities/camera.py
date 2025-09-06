# camera.py
"""
Manages the camera feature to send pictures to AI
"""

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject, Gst
from .. import attachments, dialog, activities
import cv2, threading, base64
import numpy as np

Gst.init(None)
pipeline = Gst.parse_launch('pipewiresrc ! videoconvert ! appsink name=sink')

class Camera(Gtk.Picture):
    __gtype_name___ = 'AlpacaCamera'

    def __init__(self, capture, attachment_func:callable):
        self.capture = capture
        self.attachment_func = attachment_func
        super().__init__(
            content_fit=2
        )

        capture_button = Gtk.Button(
            tooltip_text=_('Capture Picture'),
            child=Gtk.Image(
                icon_name='big-dot-symbolic',
                icon_size=2
            )
        )
        capture_button.connect('clicked', lambda *_: self.take_photo())

        self.running = False
        self.connect('realize', lambda *_: self.on_realize())

        # Activity
        self.buttons = [capture_button]
        self.title = _('Camera')
        self.activity_icon = 'camera-photo-symbolic'

    def on_realize(self):
        self.running = True
        threading.Thread(target=self.update_frame, daemon=True).start()

    def update_frame(self):
        while self.running and self.capture.isOpened():
            ret, frame = self.capture.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.uint8)
                h, w, c = frame_rgb.shape

                texture = Gdk.MemoryTexture.new(
                    width=w,
                    height=h,
                    format=7,
                    bytes=GLib.Bytes.new(frame_rgb.tobytes()),
                    stride=w*c
                )

                GLib.idle_add(self.set_paintable, texture)
            else:
                break

    def get_new_resolution(self, width:int, height:int) -> tuple:
        size = 640
        if width <= size and height <= size:
            return width, height

        if height >= width:
            new_width = size
            new_height = int((size / width) * height)
        else:
            new_height = size
            new_width = int((size / height) * width)

        return new_width, new_height

    def take_photo(self):
        texture = self.get_paintable()
        width, height = self.get_new_resolution(texture.get_width(), texture.get_height())
        texture.compute_concrete_size(width, height, width, height)

        picture_bytes = bytes(texture.save_to_png_bytes().get_data())

        attachment = attachments.Attachment(
            file_id="-1",
            file_name=_('Photo'),
            file_type='image',
            file_content=base64.b64encode(picture_bytes).decode('utf-8')
        )
        self.attachment_func(attachment)
        self.close()

    def on_close(self):
        self.capture.release()
        self.running = False

    def on_reload(self):
        pass

    def close(self):
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.close_page(self.get_parent().tab)
        else:
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()

def show_webcam_dialog(root_widget:Gtk.Widget, attachment_func:callable, return_page:bool=False):
    capture = cv2.VideoCapture(0)
    if capture.isOpened():
        page=Camera(
            capture,
            attachment_func
        )
        if return_page:
            return page
        activities.show_activity(
            page=page,
            root=root_widget
        )
    else:
        options = {
            _('Close'): {'default': True},
        }
        dialog.Options(
            heading=_('No Camera Detected'),
            body=_('Please check if camera is plugged in and turned on'),
            close_response=list(options.keys())[0],
            options=options
        ).show(root_widget)

