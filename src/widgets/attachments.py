# attachments.py

import gi
from gi.repository import Adw, Gtk, Gio, Gdk, GdkPixbuf

import odf.opendocument as odfopen
import odf.table as odftable
from markitdown import MarkItDown
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from html2text import html2text
from io import BytesIO
from PIL import Image
import requests, json, base64, tempfile, shutil

from . import blocks, dialog
from ..sql_manager import Instance as SQL

def extract_content(file_type:str, file_path:str) -> str:
    if file_type in ('plain_text', 'code'):
        with open(file_path, 'r') as f:
            return f.read()
    elif file_type in ('pdf', 'docx', 'pptx', 'xlsx'):
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
        response = requests.get(file_path)
        if response.status_code == 200:
            return '{}\n\n{}'.format(file_path, html2text(response.text))

def extract_online_image(image_url:str, max_size:int) -> str:
    image_response = requests.get(image_url, stream=True)
    if image_response.status_code == 200:
        with tempfile.NamedTemporaryFile(delete=True, suffix='.jpg') as tmp_file:
            image_response.raw.decode_content = True
            shutil.copyfileobj(image_response.raw, tmp_file)
            return extract_image(tmp_file.name, max_size)

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

def extract_youtube_content(youtube_url:str, caption_id:str) -> tuple:
    try:
        metadata = requests.get('https://noembed.com/embed?url={}'.format(youtube_url)).json()
    except Exception as e:
        print(e)
        metadata = {}

    video_id = youtube_url.split('?v=')[-1]
    if caption_id.lower().startswith('translate:'):
        available_captions = get_youtube_transcripts(video_id)
        original_caption_name = available_captions[0].split(' (')[-1][:-1]
        transcript = YouTubeTranscriptApi.list_transcripts(video_id).find_transcript([original_caption_name]).translate(caption_id.split(':')[-1]).fetch()
    else:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[caption_id])

    return metadata.get('title'), "{}\n{}\n{}\n\n{}".format(
        metadata.get('title'),
        metadata.get('author_name'),
        metadata.get('url'),
        TextFormatter().format_transcript(transcript)
    )

def get_youtube_transcripts(youtube_url:str) -> list:
    return ['{} ({})'.format(t.language, t.language_code) for t in YouTubeTranscriptApi.list_transcripts(youtube_url)]

class AttachmentDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaAttachmentDialog'

    def __init__(self, attachment):
        self.attachment = attachment

        super().__init__(
            title=self.attachment.file_name,
            child = Adw.ToolbarView(),
            content_height=420
        )
        header = Adw.HeaderBar()

        delete_button = Gtk.Button(
            css_classes=['error'],
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Attachment'),
            vexpand=False,
            valign=3
        )
        delete_button.connect('clicked', lambda *_: self.prompt_delete())
        header.pack_start(delete_button)

        if self.attachment.file_type == 'notebook':
            try:
                chat = self.attachment.get_parent().get_parent().get_parent().get_parent().get_parent().get_parent().get_parent().chat
                if chat.chat_type == 'notebook':
                    notebook_button = Gtk.Button(
                        css_classes=['accent'],
                        icon_name='open-book-symbolic',
                        tooltip_text=_('Replace Notebook Content'),
                        vexpand=False,
                        valign=3
                    )
                    notebook_button.connect('clicked', lambda *_, notebook=chat: self.replace_notebook_content(notebook))
                    header.pack_start(notebook_button)
            except:
                pass

        self.get_child().add_top_bar(header)
        self.get_child().set_content(
            Gtk.ScrolledWindow(
                hexpand=True,
                vexpand=True,
                propagate_natural_width=True,
                propagate_natural_height=True,
                css_classes=['undershoot-bottom'],
                max_content_width=500,
                min_content_width=300
            )
        )

        if self.attachment.file_type == 'image':
            image_element = Gtk.Image(
                hexpand=True,
                vexpand=True,
                css_classes=['rounded_image'],
                margin_start=10,
                margin_end=10,
                margin_bottom=10
            )
            image_data = base64.b64decode(self.attachment.get_content())
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image_element.set_from_paintable(texture)
            image_element.set_size_request(360, 360)
            image_element.set_overflow(1)
            self.get_child().get_content().set_child(image_element)
        else:
            container = Gtk.Box(
                orientation=1,
                margin_start=10,
                margin_end=10,
                margin_top=10,
                margin_bottom=10,
                hexpand=True
            )

            if self.attachment.file_type == "code":
                extension = self.attachment.file_name.split('.')[-1]
                block = blocks.Code(self.attachment.get_content(), extension)
                block.edit_button.set_visible(False)
                self.set_follows_content_size(False)
                self.set_content_width(700)
                self.set_content_height(800)
                container.append(block)
            else:
                content = self.attachment.get_content()
                for block in blocks.text_to_block_list(content):
                    container.append(block)

            self.get_child().get_content().set_child(container)

    def prompt_delete(self):
        self.close()
        dialog.simple(
            parent = self.get_root(),
            heading = _('Delete Attachment?'),
            body = _("Are you sure you want to delete '{}'?").format(self.attachment.file_name),
            callback = lambda: self.attachment.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

    def replace_notebook_content(self, notebook):
        notebook.set_notebook(self.attachment.file_content)
        self.close()

class Attachment(Gtk.Button):
    __gtype_name__ = 'AlpacaAttachment'

    def __init__(self, file_id:str, file_name:str, file_type:str, file_content:str):
        self.file_name = file_name
        self.file_type = file_type
        self.file_content = file_content

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
                    "notebook": "open-book-symbolic"
                }.get(self.file_type, "document-text-symbolic")
            )
        )

        if self.file_type == 'link':
            self.connect("clicked", lambda button, uri=self.file_content: Gio.AppInfo.launch_default_for_uri(uri))
        else:
            self.connect("clicked", lambda button: AttachmentDialog(self).present(self.get_root()))

    def get_content(self) -> str:
        return self.file_content

    def delete(self):
        if len(list(self.get_parent())) == 1:
            self.get_parent().get_parent().get_parent().set_visible(False)
        self.get_parent().remove(self)
        if self.get_name() != "-1":
            SQL.delete_attachment(self)

class ImageAttachment(Gtk.Button):
    __gtype_name__ = 'AlpacaImageAttachment'

    def __init__(self, file_id:str, file_name:str, file_content:str):
        self.file_name = file_name
        self.file_type = 'image'
        self.file_content = file_content

        try:
            image_data = base64.b64decode(self.file_content)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            self.width = int((pixbuf.get_property('width') * 240) / pixbuf.get_property('height'))
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image = Gtk.Picture.new_for_paintable(texture)
            image.set_size_request(self.width, 240)
            super().__init__(
                child=image,
                css_classes=["flat", "chat_image_button"],
                name=file_id,
                tooltip_text=_("Image"),
                overflow=1
            )
            self.connect("clicked", lambda button: AttachmentDialog(self).present(self.get_root()))
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

    def get_content(self) -> str:
        return self.file_content

    def delete(self):
        if len(list(self.get_parent())) == 1:
            self.get_parent().get_parent().get_parent().set_visible(False)
        self.get_parent().remove(self)
        if self.get_name() != "-1":
            SQL.delete_attachment(self)

class AttachmentContainer(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentContainer'

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

    def __init__(self):
        self.container = Gtk.Box(
            orientation=0,
            spacing=12
        )

        super().__init__(
            height_request = 240,
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
