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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/attachments/attachment.ui')
class Attachment(Gtk.Button):
    __gtype_name__ = 'AlpacaAttachment'

    def __init__(self, file_id:str, file_name:str, file_type:str, file_content:str):
        self.file_name = file_name
        self.file_type = file_type
        self.file_content = file_content
        self.activity = None

        super().__init__(
            name=file_id,
            tooltip_text=self.file_content if self.file_type == 'link' else self.file_name,
            sensitive=bool(self.file_content)
        )
        self.get_child().set_label(self.file_name)
        self.get_child().set_icon_name({
            "code": "code-symbolic",
            "youtube": "play-symbolic",
            "website": "globe-symbolic",
            "thought": "brain-augemnted-symbolic",
            "tool": "processor-symbolic",
            "link": "globe-symbolic",
            "image": "image-x-generic-symbolic",
            "audio": "music-note-single-symbolic",
            "metadata": "table-symbolic",
        }.get(self.file_type, "document-text-symbolic"))

    @Gtk.Template.Callback()
    def show_activity(self, button=None):
        if self.file_type == 'link':
            Gio.AppInfo.launch_default_for_uri(self.file_content)
            return

        if self.activity and self.activity.get_root():
            self.activity.on_reload()
        else:
            if self.file_type == 'image':
                image_data = base64.b64decode(self.get_content())
                page = activities.ImageViewer(
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
                    activities.FileViewer(self),
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
        self.unparent()
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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/attachments/image_attachment.ui')
class ImageAttachment(Gtk.Button):
    __gtype_name__ = 'AlpacaImageAttachment'

    def __init__(self, file_id:str, file_name:str, file_content:str):
        super().__init__()
        self.file_name = file_name
        self.file_type = 'image'
        self.file_content = file_content
        self.activity = None
        self.texture = None
        self.set_name(file_id)

        try:
            image_data = base64.b64decode(self.file_content)
            self.texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            image = Gtk.Picture.new_for_paintable(self.texture)
            image.set_size_request(int((self.texture.get_width() * 240) / self.texture.get_height()), 240)
            self.set_tooltip_text(_("Image"))
            self.set_child(image)
            self.set_sensitive(True)
        except Exception as e:
            logger.error(e)

    @Gtk.Template.Callback()
    def show_activity(self, button=None):
        if self.activity and self.activity.get_root():
            self.activity.on_reload()
        elif self.texture:
            page = activities.ImageViewer(
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
        self.unparent()
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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/attachments/attachment_container.ui')
class AttachmentContainer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentContainer'

    force_dialog = False
    container = Gtk.Template.Child()

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
                activities.show_activity(
                    activities.Transcriber(file),
                    self.get_root()
                )

    def attachment_request(self, block_images:bool=False):
        ff = Gtk.FileFilter()
        ff.set_name(_('Any compatible Alpaca attachment'))
        file_filters = [ff]
        mimes = [
            'text/plain',
            'application/pdf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ]
        if voice.libraries.get('whisper'):
            audio_mimes = ('wav', 'mpeg', 'flac', 'x-flac', 'ogg', 'mp4', 'x-m4a', 'aac', 'aiff', 'x-aiff', 'opus', 'webm')
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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/attachments/image_attachment_container.ui')
class ImageAttachmentContainer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaImageAttachmentContainer'

    force_dialog = False
    container = Gtk.Template.Child()

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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/attachments/global_attachment_button.ui')
class GlobalAttachmentButton(Gtk.Button):
    __gtype_name__ = 'AlpacaGlobalAttachmentButton'

    def __init__(self):
        super().__init__()
        self.attachment_container = None

    def set_attachment_container(self, attachment_container):
        self.attachment_container = attachment_container

    @Gtk.Template.Callback()
    def request_attachment(self, button=None):
        self.attachment_container.attachment_request()

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
                    'label': _('Attach File'),
                    'callback': self.request_attachment,
                    'icon': 'document-text-symbolic'
                },
                {
                    'label': _('Attach Website'),
                    'callback': lambda: dialog.simple_entry(
                        parent=self.get_root(),
                        heading=_('Attach Website? (Experimental)'),
                        body=_('Please enter a website URL'),
                        callback=self.attachment_container.attach_website,
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
                        callback=lambda url: threading.Thread(target=self.attachment_container.attach_youtube, args=(url,), daemon=True).start(),
                        entries={'placeholder': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}
                    ),
                    'icon': 'play-symbolic'
                },
                {
                    'label': _('Attach Screenshot'),
                    'callback': lambda: self.attachment_container.request_screenshot(),
                    'icon': 'image-x-generic-symbolic'
                },
                {
                    'label': _('Attach Photo From Camera'),
                    'callback': lambda: activities.show_activity(
                        page=activities.Camera(),
                        root=self.get_root()
                    ),
                    'icon': 'camera-photo-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()



