# attachments.py

from gi.repository import Adw, Gtk, Gio, Gdk, GLib, Xdp

import odf.opendocument as odfopen
import odf.table as odftable
from pydbus import SessionBus, Variant
from markitdown import MarkItDown
from html2text import html2text
from io import BytesIO
from PIL import Image
from ..constants import cache_dir
import numpy as np
import requests, json, base64, tempfile, shutil, logging, threading, os, re, cairo

from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

from . import blocks, dialog, voice, activities
from ..sql_manager import Instance as SQL

logger = logging.getLogger(__name__)

def extract_content(file_type:str, file_path:str) -> str:
    if file_type in ('plain_text', 'code'):
        with open(file_path, 'r') as f:
            return f.read()
    elif file_type in ('pdf', 'docx', 'pptx', 'youtube'):
        return MarkItDown(enable_plugins=False).convert(file_path).text_content
    elif file_type == 'odt':
        doc = odfopen.load(file_path)
        markdown_elements = []
        for child in doc.text.childNodes:
            if child.qname[1] == 'p' or child.qname[1] == 'span':
                markdown_elements.append(str(child))
            elif child.qname[1] == 'h':
                markdown_elements.append('# {}'.format(str(child)))
            elif child.qname[1] == 'table':
                generated_table = []
                column_sizes = []
                for row in child.getElementsByType(odftable.TableRow):
                    generated_table.append([])
                    for column_n, cell in enumerate(row.getElementsByType(odftable.TableCell)):
                        if column_n + 1 > len(column_sizes):
                            column_sizes.append(0)
                        if len(str(cell)) > column_sizes[column_n]:
                            column_sizes[column_n] = len(str(cell))
                        generated_table[-1].append(str(cell))
                generated_table.insert(1, [])
                for column_n in range(len(generated_table[0])):
                    generated_table[1].append('-' * column_sizes[column_n])
                table_str = ''
                for row in generated_table:
                    for column_n, cell in enumerate(row):
                        table_str += '| {} '.format(cell.ljust(column_sizes[column_n], ' '))
                    table_str += '|\n'
                markdown_elements.append(table_str)
        return '\n\n'.join(markdown_elements)
    elif file_type == 'website':
        parsed_url = urlparse(file_path)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Load and parse robots.txt
        robots_url = f"{base_url}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()

        if rp.can_fetch("AlpacaBot", file_path):
            headers = {"User-Agent": "AlpacaBot"}
            response = requests.get(file_path, headers=headers)
            if response.status_code == 200:
                return '{}\n\n{}'.format(file_path, html2text(response.text))
            else:
                return "Failed to fetch the page: {}".format(response.status_code)
        else:
            return "Fetching this URL is disallowed by robots.txt"

def extract_online_image(image_url:str, max_size:int) -> str | None:
    image_response = requests.get(image_url)
    if image_response.status_code == 200:
        image_data = None
        image_path = os.path.join(cache_dir, 'image_web.jpg')
        with open(image_path, 'wb') as handler:
            handler.write(image_response.content)
        image_data = extract_image(image_path, max_size)
        #if os.path.isfile(image_path):
            #os.remove(image_path)
        return image_data

def extract_image(image_path:str, max_size:int) -> str:
    #Normal Image: 640, Profile Pictures: 128
    with Image.open(image_path) as img:
        width, height = img.size
        if width > height:
            new_width = max_size
            new_height = int((max_size / width) * height)
        else:
            new_height = max_size
            new_width = int((max_size / height) * width)
        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
        with BytesIO() as output:
            resized_img.save(output, format="PNG")
            image_data = output.getvalue()
        return base64.b64encode(image_data).decode("utf-8")

class AttachmentImagePage(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentImagePage'

    def __init__(self, texture:Gdk.Texture, title:str=_('Image'), delete_callback:callable=None, download_callback:callable=None, attachment_callback:callable=None):
        self.texture = texture
        self.picture = Gtk.Picture.new_for_paintable(self.texture)

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

        self.fixed = Gtk.Fixed()
        super().__init__(
            child=self.fixed
        )

        self.fixed.put(self.picture, 0, 0)

        motion = Gtk.EventControllerMotion()
        self.add_controller(motion)
        motion.connect("motion", self.on_motion)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        self.picture.add_controller(scroll)
        scroll.connect("scroll", self.on_scroll)

        drag = Gtk.GestureDrag.new()
        self.picture.add_controller(drag)
        drag.connect("drag-update", self.on_drag_update)

        # Activity
        self.buttons = []
        self.title = title
        self.activity_icon = 'image-x-generic-symbolic'

        self.connect('realize', lambda *_: GLib.idle_add(self.on_reload))
        self.loop_id = GLib.timeout_add(1, lambda: (self.update_picture() if not self.scrollable else None) or True)

        if delete_callback:
            delete_button = Gtk.Button(
                css_classes=['error'],
                icon_name='user-trash-symbolic',
                tooltip_text=_('Remove Image'),
                vexpand=False,
                valign=3
            )
            delete_button.connect('clicked', lambda *_, cb=delete_callback: cb(self.get_root()))
            self.buttons.append(delete_button)
        if download_callback:
            download_button = Gtk.Button(
                icon_name='folder-download-symbolic',
                tooltip_text=_('Download Image'),
                vexpand=False,
                valign=3
            )
            download_button.connect('clicked', lambda *_, cb=download_callback: cb(self.get_root()))
            self.buttons.append(download_button)
        if attachment_callback:
            attach_button = Gtk.Button(
                icon_name='chain-link-loose-symbolic',
                tooltip_text=_('Attach Image'),
                vexpand=False,
                valign=3
            )
            attach_button.connect('clicked', lambda *_, cb=attachment_callback: cb())
            self.buttons.append(attach_button)

        self.reset_button = Gtk.Button(
            icon_name='zoom-fit-best-symbolic',
            tooltip_text=_('Reset View'),
            vexpand=False,
            valign=3
        )
        self.reset_button.connect('clicked', lambda *_: self.on_reload())
        self.buttons.append(self.reset_button)

    def on_reload(self):
        self.scale = self.get_min_scale()
        self.update_picture()

    def on_close(self):
        if self.loop_id:
            GLib.source_remove(self.loop_id)
        self.loop_id = None

    def on_motion(self, controller, x, y):
        self.pointer_x = x
        self.pointer_y = y

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

    def on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if not (state & Gdk.ModifierType.CONTROL_MASK):
            return False
        event = controller.get_current_event()
        if event is None:
            return False

        mx = self.pointer_x
        my = self.pointer_y

        old_scale = self.scale
        self.scale *= 1.1 if dy < 0 else 0.9

        if self.scale < self.get_min_scale() + 5.0:
            adj = self.get_hadjustment()
            adj.set_value((adj.get_value() + mx) * self.scale / old_scale - mx)
            vadj = self.get_vadjustment()
            vadj.set_value((vadj.get_value() + my) * self.scale / old_scale - my)

        self.scrollable = True
        self.reset_button.set_sensitive(True)
        self.update_picture()
        return True

    def on_drag_update(self, gesture, dx, dy):
        adj = self.get_hadjustment()
        vadj = self.get_vadjustment()
        adj.set_value(adj.get_value() - dx)
        vadj.set_value(vadj.get_value() - dy)

class AttachmentPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentPage'

    def __init__(self, attachment):
        self.attachment = attachment

        # Activity
        self.buttons = []
        self.title = self.attachment.file_name
        self.activity_icon = self.attachment.get_child().get_icon_name()

        if self.attachment.file_type != 'model_context':
            delete_button = Gtk.Button(
                css_classes=['error'],
                icon_name='user-trash-symbolic',
                tooltip_text=_('Remove Attachment'),
                vexpand=False,
                valign=3
            )
            delete_button.connect('clicked', lambda *_: self.attachment.prompt_delete(self.get_root()))
            self.buttons.append(delete_button)

        download_button = Gtk.Button(
            icon_name='folder-download-symbolic',
            tooltip_text=_('Download Attachment'),
            vexpand=False,
            valign=3
        )
        download_button.connect('clicked', lambda *_: self.attachment.prompt_download(self.get_root()))
        self.buttons.append(download_button)

        container = Gtk.Box(
            orientation=1,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=50,
            hexpand=True
        )
        super().__init__(
            child=container,
            hexpand=True,
            vexpand=True,
            propagate_natural_width=True,
            propagate_natural_height=True,
            css_classes=['undershoot-bottom'],
            max_content_width=500
        )

        content = self.attachment.get_content()
        for block in blocks.text_to_block_list(content):
            container.append(block)

    # Activity
    def on_reload(self):
        pass

    def on_close(self):
        pass

    def close(self):
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.close_page(self.get_parent().tab)
        else:
            parent = self.get_ancestor(Adw.Dialog)
            if parent:
                parent.close()

class Attachment(Gtk.Button):
    __gtype_name__ = 'AlpacaAttachment'

    def __init__(self, file_id:str, file_name:str, file_type:str, file_content:str):
        self.file_name = file_name
        self.file_type = file_type
        self.file_content = file_content
        self.activity = None

        super().__init__(
            vexpand=True,
            valign=0,
            name=file_id,
            css_classes=["flat"],
            tooltip_text=self.file_content if self.file_type == 'link' else self.file_name,
            child= Adw.ButtonContent(
                label=file_name,
                icon_name={
                    "code": "code-symbolic",
                    "youtube": "play-symbolic",
                    "website": "globe-symbolic",
                    "thought": "brain-augemnted-symbolic",
                    "tool": "processor-symbolic",
                    "link": "globe-symbolic",
                    "image": "image-x-generic-symbolic",
                    "audio": "music-note-single-symbolic"
                }.get(self.file_type, "document-text-symbolic")
            )
        )

        if self.file_type == 'link':
            self.connect("clicked", lambda button, uri=self.file_content: Gio.AppInfo.launch_default_for_uri(uri))
        else:
            self.connect("clicked", lambda button: self.show_activity())

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def show_activity(self):
        if self.activity and self.activity.get_root():
            self.activity.reload()
        else:
            if self.file_type == 'image':
                image_data = base64.b64decode(self.get_content())
                page = AttachmentImagePage(
                    texture=Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data)),
                    title=self.file_name,
                    delete_callback=self.prompt_delete,
                    download_callback=self.prompt_download
                )

                self.activity = activities.show_activity(
                    page,
                    self.get_root(),
                    self.get_parent().get_parent().get_parent().force_dialog
                )
            elif self.file_type in ('code', 'website'):
                code = self.get_content()
                language = None
                try:
                    language = self.file_name.split('.')[-1].lower()
                except:
                    pass
                if self.file_type == 'website':
                    language='md'
                page = activities.CodeEditor(
                    language=language,
                    code_getter=lambda:code
                )
                page.title = self.file_name
                page.activity_icon = 'code-symbolic'
                page.buttons = []

                delete_button = Gtk.Button(
                    css_classes=['error'],
                    icon_name='user-trash-symbolic',
                    tooltip_text=_('Remove Attachment'),
                    vexpand=False,
                    valign=3
                )
                delete_button.connect('clicked', lambda *_: self.prompt_delete(page.get_root()))
                page.buttons.append(delete_button)

                download_button = Gtk.Button(
                    icon_name='folder-download-symbolic',
                    tooltip_text=_('Download Attachment'),
                    vexpand=False,
                    valign=3
                )
                download_button.connect('clicked', lambda *_: self.prompt_download(page.get_root()))
                page.buttons.append(download_button)

                self.activity = activities.show_activity(
                    page,
                    self.get_root(),
                    self.get_parent().get_parent().get_parent().force_dialog
                )

            else:
                self.activity = activities.show_activity(
                    AttachmentPage(self),
                    self.get_root(),
                    self.get_parent().get_parent().get_parent().force_dialog
                )

    def get_content(self) -> str:
        return self.file_content

    def delete(self):
        if self.activity:
            self.activity.close()
        if len(list(self.get_parent())) == 1:
            self.get_parent().get_parent().get_parent().set_visible(False)
        self.get_parent().remove(self)
        if self.get_name() != "-1":
            SQL.delete_attachment(self)

    def prompt_delete(self, override_root=None):
        dialog.simple(
            parent = override_root or self.get_root(),
            heading = _('Delete Attachment?'),
            body = _("Are you sure you want to delete '{}'?").format(self.file_name),
            callback = lambda: self.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

    def on_download(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            path = file.get_path()
            if path:
                if self.file_type == 'image':
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(self.file_content))
                else:
                    with open(path, "w") as f:
                        f.write(self.file_content)
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
        except GLib.Error as e:
            logger.error(e)

    def prompt_download(self, override_root=None):
        name = os.path.splitext(self.file_name)[0]
        if self.file_type == 'image':
            name += '.png'
        else:
            name += '.md'

        name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)

        dialog = Gtk.FileDialog(
            title=_("Save Attachment"),
            initial_name=name
        )
        dialog.save(override_root or self.get_root(), None, self.on_download, None)

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Download Attachment'),
                    'callback': self.prompt_download,
                    'icon': 'folder-download-symbolic'
                }
            ]
        ]
        if self.file_type != 'model_context':
            actions[0].append({
                'label': _('Remove Attachment'),
                'callback': self.prompt_delete,
                'icon': 'user-trash-symbolic'
            })
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

class ImageAttachment(Gtk.Button):
    __gtype_name__ = 'AlpacaImageAttachment'

    def __init__(self, file_id:str, file_name:str, file_content:str):
        self.file_name = file_name
        self.file_type = 'image'
        self.file_content = file_content
        self.activity = None
        self.texture = None
        try:
            image_data = base64.b64decode(self.file_content)
            self.texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            image = Gtk.Picture.new_for_paintable(self.texture)
            image.set_size_request(int((self.texture.get_width() * 240) / self.texture.get_height()), 240)
            super().__init__(
                child=image,
                css_classes=["flat", "chat_image_button"],
                name=file_id,
                tooltip_text=_("Image"),
                overflow=1
            )
            self.connect("clicked", lambda button: self.show_activity())
        except Exception as e:
            #logger.error(e)
            image_texture = Gtk.Image.new_from_icon_name("image-missing-symbolic")
            image_texture.set_icon_size(2)
            image_texture.set_vexpand(True)
            image_texture.set_pixel_size(120)
            image_label = Gtk.Label(
                label=_("Missing Image"),
            )
            image_box = Gtk.Box(
                spacing=10,
                orientation=1,
            )
            image_box.append(image_texture)
            image_box.append(image_label)
            image_box.set_size_request(240, 240)
            super().__init__(
                child=image_box,
                css_classes=["flat", "chat_image_button"],
                tooltip_text=_("Missing Image"),
                overflow=1,
                name=file_id
            )

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def show_activity(self):
        if self.activity and self.activity.get_root():
            self.activity.reload()
        elif self.texture:
            page = AttachmentImagePage(
                texture=self.texture,
                title=self.file_name,
                delete_callback=self.prompt_delete,
                download_callback=self.prompt_download
            )
            self.activity = activities.show_activity(
                page,
                self.get_root(),
                self.get_parent().get_parent().get_parent().force_dialog
            )

    def get_content(self) -> str:
        return self.file_content

    def delete(self):
        if self.activity:
            self.activity.close()
        if len(list(self.get_parent())) == 1:
            self.get_parent().get_parent().get_parent().set_visible(False)
        self.get_parent().remove(self)
        if self.get_name() != "-1":
            SQL.delete_attachment(self)

    def prompt_delete(self, override_root=None):
        dialog.simple(
            parent = override_root or self.get_root(),
            heading = _('Delete Image?'),
            body = _("Are you sure you want to delete '{}'?").format(self.file_name),
            callback = lambda: self.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

    def on_download(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            path = file.get_path()
            if path:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(self.file_content))
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
        except GLib.Error as e:
            logger.error(e)

    def prompt_download(self, override_root=None):
        name = os.path.splitext(self.file_name)[0] + '.png'
        name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)

        dialog = Gtk.FileDialog(
            title=_("Save Image"),
            initial_name=name
        )
        dialog.save(override_root or self.get_root(), None, self.on_download, None)

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
                    'label': _('Remove Image'),
                    'callback': self.prompt_delete,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

class AttachmentContainer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentContainer'

    force_dialog = False

    def __init__(self):
        self.container = Gtk.Box(
            orientation=0,
            spacing=10,
            valign=1
        )

        super().__init__(
            hexpand=True,
            child=self.container,
            vscrollbar_policy=2,
            visible=False,
            vexpand_set=True,
            valign=1,
            propagate_natural_width=True
        )

    def get_content(self) -> list:
        files = []
        for f in list(self.container):
            files.append({
                'id': f.get_name(),
                'name': f.file_name,
                'type': f.file_type,
                'content': f.file_content
            })
        return files

    def add_attachment(self, attachment:Attachment) -> None:
        self.set_visible(True)
        self.container.append(attachment)

class ImageAttachmentContainer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaImageAttachmentContainer'

    force_dialog = False

    def __init__(self):
        self.container = Gtk.Box(
            orientation=0,
            spacing=12
        )

        super().__init__(
            height_request=240,
            min_content_width=240,
            child=self.container,
            visible=False
        )

    def get_content(self) -> list:
        files = []
        for f in list(self.container):
            files.append({
                'id': f.get_name(),
                'name': f.file_name,
                'type': f.file_type,
                'content': f.file_content
            })
        return files

    def add_attachment(self, attachment:ImageAttachment) -> None:
        self.set_visible(True)
        self.container.append(attachment)

class GlobalAttachmentContainer(AttachmentContainer):
    __gtype_name__ = 'AlpacaGlobalAttachmentContainer'

    force_dialog = False

    def attach_website(self, url:str):
        GLib.idle_add(self.get_root().global_footer.remove_text, url)
        content = extract_content("website", url)
        website_title = 'website'
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            website_title = match.group(1)
        attachment = Attachment(
            file_id="-1",
            file_name=website_title,
            file_type="website",
            file_content=content
        )
        self.add_attachment(attachment)

    def attach_youtube(self, video_url:str):
        GLib.idle_add(self.get_root().global_footer.remove_text, video_url)
        content = extract_content('youtube', video_url)
        title = requests.get('https://noembed.com/embed?url={}'.format(video_url)).json().get('title', 'YouTube')
        attachment = Attachment(
            file_id="-1",
            file_name=title,
            file_type="youtube",
            file_content=content
        )
        self.add_attachment(attachment)

    def on_attachment(self, file:Gio.File, remove_original:bool=False):
        if not file:
            return
        file_types = {
            "plain_text": ["txt", "md"],
            "code": ["c", "h", "css", "html", "js", "ts", "py", "java", "json", "xml", "asm", "nasm",
                    "cs", "csx", "cpp", "cxx", "cp", "hxx", "inc", "csv", "lsp", "lisp", "el", "emacs",
                    "l", "cu", "dockerfile", "glsl", "g", "lua", "php", "rb", "ru", "rs", "sql", "sh", "p8",
                    "yaml"],
            "image": ["png", "jpeg", "jpg", "webp", "gif"],
            "pdf": ["pdf"],
            "odt": ["odt"],
            "docx": ["docx"],
            "pptx": ["pptx"],
            'audio': ["wav", "mp3", "flac", "ogg", "oga", "m4a", "acc", "aiff", "aif", "opus", "webm",
                    "mp4", "mkv", "mov", "avi"]
        }
        if file.query_info("standard::content-type", 0, None).get_content_type() == 'text/plain':
            extension = 'txt'
        else:
            extension = file.get_path().split(".")[-1]
        found_types = [key for key, value in file_types.items() if extension in value]
        if len(found_types) == 0:
            file_type = 'plain_text'
        else:
            file_type = found_types[0]
        if file_type == 'image':
            content = extract_image(file.get_path(), self.get_root().settings.get_value('max-image-size').unpack())
            if not self.get_root().get_selected_model().get_vision():
                dialog.show_toast(_("This model might not be compatible with image recognition"), self.get_root())
        elif file_type == 'audio':
            content = 'AUDIO NOT TRANSCRIBED'
        else:
            content = extract_content(file_type, file.get_path())
        if content:
            file_name = os.path.basename(file.get_path())
            if file_type == 'code':
                file_name = os.path.splitext(file_name)[0]
            if file_type != 'audio':
                attachment = Attachment(
                    file_id="-1",
                    file_name=file_name,
                    file_type=file_type,
                    file_content=content
                )
                self.add_attachment(attachment)
            elif voice.libraries.get('whisper'):
                def on_finish_transcription(text:str):
                    attachment = Attachment(
                        file_id="-1",
                        file_name=file_name,
                        file_type=file_type,
                        file_content=text
                    )
                    self.add_attachment(attachment)
                threading.Thread(target=voice.transcribe_audio_file, args=(
                    self.get_root(),
                    on_finish_transcription,
                    file.get_path()
                )).start()

    def attachment_request(self, block_images:bool=False):
        ff = Gtk.FileFilter()
        ff.set_name(_('Any compatible Alpaca attachment'))
        file_filters = [ff]
        mimes = [
            'text/plain',
            'application/pdf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        if voice.libraries.get('whisper'):
            audio_mimes = ('wav', 'x-wav', 'mpeg', 'flac', 'x-flac', 'ogg', 'mp4', 'x-m4a', 'aac', 'aiff', 'x-aiff', 'opus', 'webm')
            for m in audio_mimes:
                mimes.append('audio/{}'.format(m))
            video_mimes = ('mp4', 'x-matroska', 'quicktime', 'x-msvideo', 'webm')
            for m in video_mimes:
                mimes.append('video/{}'.format(m))

        for mime in mimes:
            ff = Gtk.FileFilter()
            ff.add_mime_type(mime)
            file_filters[0].add_mime_type(mime)
            file_filters.append(ff)
        if not block_images:
            file_filters[0].add_pixbuf_formats()
            file_filter = Gtk.FileFilter()
            file_filter.add_pixbuf_formats()
            file_filters.append(file_filter)
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = file_filters,
            callback = self.on_attachment
        )

    def request_screenshot(self):
        def on_response(portal, res, user_data):
            filename = portal.take_screenshot_finish(res)
            if filename:
                self.on_attachment(Gio.File.new_for_uri(filename))

        Xdp.Portal().take_screenshot(
            None,
            Xdp.ScreenshotFlags.INTERACTIVE,
            None,
            on_response,
            None
        )

class GlobalAttachmentButton(Gtk.Button):
    __gtype_name__ = 'AlpacaGlobalAttachmentButton'

    def __init__(self):
        super().__init__(
            vexpand=False,
            valign=3,
            icon_name='chain-link-loose-symbolic',
            css_classes=['circular'],
            tooltip_text=_('Attach File')
        )
        self.connect('clicked', lambda button: self.get_root().global_footer.attachment_container.attachment_request())
        gesture_click = Gtk.GestureClick(button=3)
        gesture_click.connect("released", lambda gesture, _n_press, x, y: self.show_popup(gesture, x, y))
        self.add_controller(gesture_click)
        gesture_long_press = Gtk.GestureLongPress()
        gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(gesture_long_press)

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Attach File'),
                    'callback': lambda: self.get_root().global_footer.attachment_container.attachment_request(),
                    'icon': 'document-text-symbolic'
                },
                {
                    'label': _('Attach Website'),
                    'callback': lambda: dialog.simple_entry(
                        parent=self.get_root(),
                        heading=_('Attach Website? (Experimental)'),
                        body=_('Please enter a website URL'),
                        callback=self.get_root().global_footer.attachment_container.attach_website,
                        entries={'placeholder': 'https://jeffser.com/alpaca/'}
                    ),
                    'icon': 'globe-symbolic'
                },
                {
                    'label': _('Attach YouTube Captions'),
                    'callback': lambda: dialog.simple_entry(
                        parent=self.get_root(),
                        heading=_('Attach YouTube Captions?'),
                        body=_('Please enter a YouTube video URL'),
                        callback=lambda url: threading.Thread(target=self.get_root().global_footer.attachment_container.attach_youtube, args=(url,)).start(),
                        entries={'placeholder': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}
                    ),
                    'icon': 'play-symbolic'
                },
                {
                    'label': _('Attach Screenshot'),
                    'callback': lambda: self.get_root().global_footer.attachment_container.request_screenshot(),
                    'icon': 'image-x-generic-symbolic'
                },
                {
                    'label': _('Attach Photo From Camera'),
                    'callback': lambda: activities.show_webcam_dialog(
                        self.get_root(),
                        lambda att: self.get_root().global_footer.attachment_container.add_attachment(att)
                    ),
                    'icon': 'camera-photo-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()


