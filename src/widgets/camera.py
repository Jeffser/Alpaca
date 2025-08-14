# camera.py
"""
Manages the camera feature to send pictures to AI
"""

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf, GObject, Gst
from . import attachments, dialog
import cv2, threading, base64
import numpy as np

Gst.init(None)
pipeline = Gst.parse_launch('pipewiresrc ! videoconvert ! appsink name=sink')

class CameraDialog(Adw.Dialog):
    __gtype_name___ = 'AlpacaCameraDialog'

    def __init__(self, capture):
        self.capture = capture
        self.image = Gtk.Picture(
            content_fit=2
        )
        overlay = Gtk.Overlay(
            child=self.image
        )

        header_bar = Adw.HeaderBar(
            valign=1,
            css_classes=['osd'],
            show_title=False
        )
        overlay.add_overlay(header_bar)

        capture_button = Gtk.Button(
            child=Gtk.Image(
                icon_name='big-dot-symbolic',
                icon_size=2
            ),
            halign=3,
            valign=2,
            css_classes=['circular', 'flat', 'camera_button', 'accent'],
            margin_bottom=10
        )
        capture_button.connect('clicked', lambda *_: self.take_photo())
        overlay.add_overlay(capture_button)

        super().__init__(
            follows_content_size=True,
            child=overlay
        )
        self.running = False
        self.connect('closed', lambda *_: self.on_closed())
        self.connect('realize', lambda *_: self.on_realize())

    def on_realize(self):
        self.running = True
        threading.Thread(target=self.update_frame, daemon=True).start()

    def update_frame(self):
        while self.running and self.capture.isOpened():
            ret, frame = self.capture.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, c = frame_rgb.shape
                pb = GdkPixbuf.Pixbuf.new_from_data(
                    frame_rgb.tobytes(),
                    GdkPixbuf.Colorspace.RGB,
                    False,
                    8,
                    w,
                    h,
                    w * c
                )
                GLib.idle_add(self.image.set_paintable, Gdk.Texture.new_for_pixbuf(pb))
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
        self.capture.release()
        texture = self.image.get_paintable()
        width, height = self.get_new_resolution(texture.get_width(), texture.get_height())
        texture.compute_concrete_size(width, height, width, height)

        picture_bytes = bytes(texture.save_to_png_bytes().get_data())

        attachment = attachments.Attachment(
            file_id="-1",
            file_name=_('Photo'),
            file_type='image',
            file_content=base64.b64encode(picture_bytes).decode('utf-8')
        )
        self.get_root().global_footer.attachment_container.add_attachment(attachment)
        self.close()

    def on_closed(self):
        self.capture.release()
        self.running = False

def show_webcam_dialog(root_widget:Gtk.Widget):
    capture = cv2.VideoCapture(0)
    if capture.isOpened():
        CameraDialog(capture).present(root_widget)
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

