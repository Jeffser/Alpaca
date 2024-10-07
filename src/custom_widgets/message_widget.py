#message_widget.py
"""
Handles the message widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk
import logging, os, datetime, re, shutil, threading, sys
from ..internal import config_dir, data_dir, cache_dir, source_dir
from .table_widget import TableWidget
from .. import dialogs

logger = logging.getLogger(__name__)

window = None

class edit_text_block(Gtk.TextView):
    __gtype_name__ = 'AlpacaEditTextBlock'

    def __init__(self, text:str):
        super().__init__(
            hexpand=True,
            halign=0,
            margin_top=5,
            margin_bottom=5,
            margin_start=5,
            margin_end=5,
            css_classes=["view", "editing_message_textview"]
        )
        self.get_buffer().insert(self.get_buffer().get_start_iter(), text, len(text.encode('utf-8')))
        enter_key_controller = Gtk.EventControllerKey.new()
        enter_key_controller.connect("key-pressed", lambda controller, keyval, keycode, state: self.edit_message() if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK) else None)
        self.add_controller(enter_key_controller)

    def edit_message(self):
        self.get_parent().get_parent().action_buttons.set_visible(True)
        self.get_parent().get_parent().set_text(self.get_buffer().get_text(self.get_buffer().get_start_iter(), self.get_buffer().get_end_iter(), False))
        self.get_parent().get_parent().add_footer(self.get_parent().get_parent().dt)
        window.save_history(self.get_parent().get_parent().get_parent().get_parent().get_parent().get_parent())
        self.get_parent().remove(self)
        window.show_toast(_("Message edited successfully"), window.main_overlay)
        return True

class text_block(Gtk.Label):
    __gtype_name__ = 'AlpacaTextBlock'

    def __init__(self, bot:bool):
        super().__init__(
            hexpand=True,
            halign=0,
            wrap=True,
            wrap_mode=0,
            xalign=0,
            margin_top=5,
            margin_start=5,
            margin_end=5,
            focusable=True,
            selectable=True
        )
        self.update_property([4, 7], [_("Response message") if bot else _("User message"), False])
        self.connect('notify::has-focus', lambda *_: GLib.idle_add(self.remove_selection) if self.has_focus() else None)

    def remove_selection(self):
        self.set_selectable(False)
        self.set_selectable(True)

    def insert_at_end(self, text:str, markdown:bool):
        if markdown:
            self.set_markup(self.get_text() + text)
        else:
            self.set_text(self.get_text() + text)
        self.update_property([1], [self.get_text()])

    def clear_text(self):
        self.buffer.delete(self.textbuffer.get_start_iter(), self.textbuffer.get_end_iter())
        self.update_property([1], [""])

class code_block(Gtk.Box):
    __gtype_name__ = 'AlpacaCodeBlock'

    def __init__(self, text:str, language_name:str=None):
        super().__init__(
            css_classes=["card", "code_block"],
            orientation=1,
            overflow=1,
            margin_start=5,
            margin_end=5
        )

        self.language = None
        if language_name:
            self.language = GtkSource.LanguageManager.get_default().get_language(language_name)
        if self.language:
            self.buffer = GtkSource.Buffer.new_with_language(self.language)
        else:
            self.buffer = GtkSource.Buffer()
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))
        self.source_view = GtkSource.View(
            auto_indent=True, indent_width=4, buffer=self.buffer, show_line_numbers=True, editable=None,
            top_margin=6, bottom_margin=6, left_margin=12, right_margin=12, css_classes=["code_block"]
        )
        self.source_view.update_property([4], [_("{}Code Block").format('{} '.format(self.language.get_name()) if self.language else "")])

        title_box = Gtk.Box(margin_start=12, margin_top=3, margin_bottom=3, margin_end=3)
        title_box.append(Gtk.Label(label=self.language.get_name() if self.language else (language_name.title() if language_name else _("Code Block")), hexpand=True, xalign=0))
        copy_button = Gtk.Button(icon_name="edit-copy-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Copy Message"))
        copy_button.connect("clicked", lambda *_: self.on_copy())
        title_box.append(copy_button)
        if language_name.lower() == 'bash':
            run_button = Gtk.Button(icon_name="execute-from-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Run Script"))
            run_button.connect("clicked", lambda *_: self.run_script())
            title_box.append(run_button)
        self.append(title_box)
        self.append(Gtk.Separator())
        self.append(self.source_view)
        self.buffer.set_text(text)

    def on_copy(self):
        logger.debug("Copying code")
        clipboard = Gdk.Display().get_default().get_clipboard()
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, False)
        clipboard.set(text)
        window.show_toast(_("Code copied to the clipboard"), window.main_overlay)

    def run_script(self):
        logger.debug("Running script")
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        dialogs.run_script(window, self.buffer.get_text(start, end, False))

class attachment(Gtk.Button):
    __gtype_name__ = 'AlpacaAttachment'

    def __init__(self, file_name:str, file_path:str, file_type:str):
        self.file_name = file_name
        self.file_path = file_path
        self.file_type = file_type

        directory, file_name = os.path.split(self.file_path)
        head, last_dir = os.path.split(directory)
        head, second_last_dir = os.path.split(head)
        self.file_path = os.path.join(head, '{selected_chat}', last_dir, file_name)

        button_content = Adw.ButtonContent(
            label=self.file_name,
            icon_name={
                "plain_text": "document-text-symbolic",
                "pdf": "document-text-symbolic",
                "youtube": "play-symbolic",
                "website": "globe-symbolic"
            }[self.file_type]
        )

        super().__init__(
            vexpand=False,
            valign=3,
            name=self.file_name,
            css_classes=["flat"],
            tooltip_text=self.file_name,
            child=button_content
        )

        self.connect("clicked", lambda button, file_path=self.file_path, file_type=self.file_type: window.preview_file(file_path, file_type, None))

class attachment_container(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentContainer'

    def __init__(self):
        self.files = []

        self.container = Gtk.Box(
            orientation=0,
            spacing=12
        )

        super().__init__(
            margin_top=10,
            margin_start=10,
            margin_end=10,
            hexpand=True,
            child=self.container
        )

    def add_file(self, file:attachment):
        self.container.append(file)
        self.files.append(file)

class image(Gtk.Button):
    __gtype_name__ = 'AlpacaImage'

    def __init__(self, image_path:str):
        self.image_path = image_path
        self.image_name = os.path.basename(self.image_path)

        directory, file_name = os.path.split(self.image_path)
        head, last_dir = os.path.split(directory)
        head, second_last_dir = os.path.split(head)

        try:
            if not os.path.isfile(self.image_path):
                raise FileNotFoundError("'{}' was not found or is a directory".format(self.image_path))
            image = Gtk.Image.new_from_file(self.image_path)
            image.set_size_request(240, 240)
            super().__init__(
                child=image,
                css_classes=["flat", "chat_image_button"],
                name=self.image_name,
                tooltip_text=_("Image")
            )
            image.update_property([4], [_("Image")])
        except Exception as e:
            logger.error(e)
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
                margin_top=10,
                margin_bottom=10,
                margin_start=10,
                margin_end=10
            )
            image_box.append(image_texture)
            image_box.append(image_label)
            image_box.set_size_request(220, 220)
            super().__init__(
                child=image_box,
                css_classes=["flat", "chat_image_button"],
                tooltip_text=_("Missing Image")
            )
            image_texture.update_property([4], [_("Missing image")])
        self.connect("clicked", lambda button, file_path=os.path.join(head, '{selected_chat}', last_dir, file_name): window.preview_file(file_path, 'image', None))

class image_container(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaImageContainer'

    def __init__(self):
        self.files = []

        self.container = Gtk.Box(
            orientation=0,
            spacing=12
        )

        super().__init__(
            margin_top=10,
            margin_start=10,
            margin_end=10,
            hexpand=True,
            height_request = 240,
            child=self.container
        )

    def add_image(self, img:image):
        self.container.append(img)
        self.files.append(img)

class footer(Gtk.Label):
    __gtype_name__ = 'AlpacaMessageFooter'

    def __init__(self, dt:datetime.datetime, model:str=None):
        super().__init__(
            hexpand=False,
            halign=0,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            xalign=0,
            margin_bottom=5,
            margin_start=5,
            focusable=True
        )
        self.set_markup("<small>{}{}</small>".format((window.convert_model_name(model, 0) + " • ") if model else "", GLib.markup_escape_text(self.format_datetime(dt))))

    def format_datetime(self, dt:datetime) -> str:
        date = GLib.DateTime.new(GLib.DateTime.new_now_local().get_timezone(), dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        current_date = GLib.DateTime.new_now_local()
        if date.format("%Y/%m/%d") == current_date.format("%Y/%m/%d"):
            return date.format("%H:%M %p")
        if date.format("%Y") == current_date.format("%Y"):
            return date.format("%b %d, %H:%M %p")
        return date.format("%b %d %Y, %H:%M %p")

class action_buttons(Gtk.Box):
    __gtype_name__ = 'AlpacaActionButtonContainer'

    def __init__(self, bot:bool):
        super().__init__(
            orientation=0,
            spacing=6,
            margin_end=6,
            margin_bottom=6,
            valign="end",
            halign="end"
        )

        self.delete_button = Gtk.Button(
            icon_name = "user-trash-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Remove Message")
        )
        self.delete_button.connect('clicked', lambda *_: self.delete_message())
        self.append(self.delete_button)

        self.copy_button = Gtk.Button(
            icon_name = "edit-copy-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Copy Message")
        )
        self.copy_button.connect('clicked', lambda *_: self.copy_message())
        self.append(self.copy_button)

        self.regenerate_button = Gtk.Button(
            icon_name = "update-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Regenerate Message")
        )
        self.regenerate_button.connect('clicked', lambda *_: self.regenerate_message())

        self.edit_button = Gtk.Button(
            icon_name = "edit-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Edit Message")
        )
        self.edit_button.connect('clicked', lambda *_: self.edit_message())

        self.append(self.regenerate_button if bot else self.edit_button)

    def delete_message(self):
        logger.debug("Deleting message")
        chat = self.get_parent().get_parent().get_parent().get_parent().get_parent()
        message_id = self.get_parent().message_id
        self.get_parent().get_parent().remove(self.get_parent())
        if os.path.exists(os.path.join(data_dir, "chats", window.chat_list_box.get_current_chat().get_name(), self.get_parent().message_id)):
            shutil.rmtree(os.path.join(data_dir, "chats", window.chat_list_box.get_current_chat().get_name(), self.get_parent().message_id))
        del chat.messages[message_id]
        window.save_history(chat)
        if len(chat.messages) == 0:
            chat.show_welcome_screen(len(window.model_manager.get_model_list()) > 0)

    def copy_message(self):
        logger.debug("Copying message")
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.get_parent().text)
        window.show_toast(_("Message copied to the clipboard"), window.main_overlay)

    def regenerate_message(self):
        chat = self.get_parent().get_parent().get_parent().get_parent().get_parent()
        message_element = self.get_parent()
        if message_element.spinner:
            message_element.container.remove(message_element.spinner)
            message_element.spinner = None
        if not chat.busy:
            message_element.set_text()
            if message_element.footer:
                message_element.container.remove(message_element.footer)
            message_element.remove_overlay(self)
            message_element.action_buttons = None
            history = window.convert_history_to_ollama(chat)[:list(chat.messages).index(message_element.message_id)]
            data = {
                "model": window.model_manager.get_selected_model(),
                "messages": history,
                "options": {"temperature": window.ollama_instance.tweaks["temperature"], "seed": window.ollama_instance.tweaks["seed"]},
                "keep_alive": f"{window.ollama_instance.tweaks['keep_alive']}m"
            }
            thread = threading.Thread(target=window.run_message, args=(data, message_element, chat))
            thread.start()
        else:
            window.show_toast(_("Message cannot be regenerated while receiving a response"), window.main_overlay)

    def edit_message(self):
        logger.debug("Editing message")
        self.get_parent().action_buttons.set_visible(False)
        for child in self.get_parent().content_children:
            self.get_parent().container.remove(child)
        self.get_parent().content_children = []
        self.get_parent().container.remove(self.get_parent().footer)
        self.get_parent().footer = None
        edit_text_b = edit_text_block(self.get_parent().text)
        self.get_parent().container.append(edit_text_b)
        window.set_focus(edit_text_b)


class message(Gtk.Overlay):
    __gtype_name__ = 'AlpacaMessage'

    def __init__(self, message_id:str, model:str=None):
        self.message_id = message_id
        self.bot = model != None
        self.dt = None
        self.model = model
        self.action_buttons = None
        self.content_children = [] #These are the code blocks, text blocks and tables
        self.footer = None
        self.image_c = None
        self.attachment_c = None
        self.spinner = None
        self.text = None

        self.container = Gtk.Box(
            orientation=1,
            halign='fill',
            css_classes=["response_message"] if self.bot else ["card", "user_message"],
            spacing=12
        )

        super().__init__(css_classes=["message"], name=message_id)
        self.set_child(self.container)

    def add_attachments(self, attachments:dict):
        self.attachment_c = attachment_container()
        self.container.append(self.attachment_c)
        for file_path, file_type in attachments.items():
            file = attachment(os.path.basename(file_path), file_path, file_type)
            self.attachment_c.add_file(file)

    def add_images(self, images:list):
        self.image_c = image_container()
        self.container.append(self.image_c)
        for image_path in images:
            image_element = image(image_path)
            self.image_c.add_image(image_element)

    def add_footer(self, dt:datetime.datetime):
        self.dt = dt
        self.footer = footer(self.dt, self.model)
        self.container.append(self.footer)

    def add_action_buttons(self):
        if not self.action_buttons:
            self.action_buttons = action_buttons(self.bot)
            self.add_overlay(self.action_buttons)
            if not self.text:
                self.action_buttons.set_visible(False)

    def update_message(self, data:dict):
        chat = self.get_parent().get_parent().get_parent().get_parent()
        if chat.busy:
            vadjustment = chat.get_vadjustment()
            if self.spinner:
                self.container.remove(self.spinner)
                self.spinner = None
                self.content_children[-1].set_visible(True)
                GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
            elif vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
                GLib.idle_add(vadjustment.set_value, vadjustment.get_upper() - vadjustment.get_page_size())
            GLib.idle_add(self.content_children[-1].insert_at_end, data['message']['content'], False)
            if 'done' in data and data['done']:
                window.chat_list_box.get_tab_by_name(chat.get_name()).spinner.set_visible(False)
                if window.chat_list_box.get_current_chat().get_name() != chat.get_name():
                    window.chat_list_box.get_tab_by_name(chat.get_name()).indicator.set_visible(True)
                if chat.welcome_screen:
                    chat.container.remove(chat.welcome_screen)
                    chat.welcome_screen = None
                chat.stop_message()
                self.text = self.content_children[-1].get_label()
                GLib.idle_add(self.set_text, self.content_children[-1].get_label())
                self.dt = datetime.datetime.now()
                GLib.idle_add(self.add_footer, self.dt)
                window.show_notification(chat.get_name(), self.text[:200] + (self.text[200:] and '...'), Gio.ThemedIcon.new("chat-message-new-symbolic"))
                GLib.idle_add(window.save_history, chat)
        else:
            if self.spinner:
                GLib.idle_add(self.container.remove, self.spinner)
                self.spinner = None
            chat_tab = window.chat_list_box.get_tab_by_name(chat.get_name())
            if chat_tab.spinner:
                GLib.idle_add(chat_tab.spinner.set_visible, False)
            sys.exit()

    def set_text(self, text:str=None):
        self.text = text
        for child in self.content_children:
            self.container.remove(child)
        self.content_children = []
        if text:
            self.content_children = []
            code_block_pattern = re.compile(r'```(\w*)\n(.*?)\n\s*```', re.DOTALL)
            no_lang_code_block_pattern = re.compile(r'`\n(.*?)\n`', re.DOTALL)
            table_pattern = re.compile(r'((\r?\n){2}|^)([^\r\n]*\|[^\r\n]*(\r?\n)?)+(?=(\r?\n){2}|$)', re.MULTILINE)
            bold_pattern = re.compile(r'\*\*(.*?)\*\*') #"**text**"
            code_pattern = re.compile(r'`([^`\n]*?)`') #"`text`"
            h1_pattern = re.compile(r'^#\s(.*)$') #"# text"
            h2_pattern = re.compile(r'^##\s(.*)$') #"## text"
            markup_pattern = re.compile(r'<(b|u|tt|span.*)>(.*?)<\/(b|u|tt|span)>') #heh butt span, I'm so funny
            parts = []
            pos = 0
            # Code blocks
            for match in code_block_pattern.finditer(self.text):
                start, end = match.span()
                if pos < start:
                    normal_text = self.text[pos:start]
                    parts.append({"type": "normal", "text": normal_text.strip()})
                language = match.group(1)
                code_text = match.group(2)
                parts.append({"type": "code", "text": code_text, "language": 'python3' if language == 'python' else language})
                pos = end
            # Code blocks (No language)
            for match in no_lang_code_block_pattern.finditer(self.text):
                start, end = match.span()
                if pos < start:
                    normal_text = self.text[pos:start]
                    parts.append({"type": "normal", "text": normal_text.strip()})
                code_text = match.group(1)
                parts.append({"type": "code", "text": code_text, "language": None})
                pos = end
            # Tables
            for match in table_pattern.finditer(self.text):
                start, end = match.span()
                if pos < start:
                    normal_text = self.text[pos:start]
                    parts.append({"type": "normal", "text": normal_text.strip()})
                table_text = match.group(0)
                parts.append({"type": "table", "text": table_text})
                pos = end
            # Text blocks
            if pos < len(text):
                normal_text = text[pos:]
                if normal_text.strip():
                    parts.append({"type": "normal", "text": normal_text.strip()})

            for part in parts:
                if part['type'] == 'normal':
                    text_b = text_block(self.bot)
                    part['text'] = part['text'].replace("\n* ", "\n• ")
                    part['text'] = code_pattern.sub(r'<tt>\1</tt>', part['text'])
                    part['text'] = bold_pattern.sub(r'<b>\1</b>', part['text'])
                    part['text'] = h1_pattern.sub(r'<span size="x-large">\1</span>', part['text'])
                    part['text'] = h2_pattern.sub(r'<span size="large">\1</span>', part['text'])
                    pos = 0
                    for match in markup_pattern.finditer(part['text']):
                        start, end = match.span()
                        if pos < start:
                            text_b.insert_at_end(part['text'][pos:start], False)
                        text_b.insert_at_end(match.group(0), True)
                        pos = end

                    if pos < len(part['text']):
                        text_b.insert_at_end(part['text'][pos:], False)
                    self.content_children.append(text_b)
                    self.container.append(text_b)
                elif part['type'] == 'code':
                    code_b = code_block(part['text'], part['language'])
                    self.content_children.append(code_b)
                    self.container.append(code_b)
                elif part['type'] == 'table':
                    table_w = TableWidget(part['text'])
                    self.content_children.append(table_w)
                    self.container.append(table_w)
            self.add_action_buttons()
        else:
            text_b = text_block(self.bot)
            text_b.set_visible(False)
            self.content_children.append(text_b)
            if self.spinner:
                self.container.remove(self.spinner)
                self.spinner = None
            self.spinner = Gtk.Spinner(spinning=True, margin_top=12, margin_bottom=12, hexpand=True)
            self.container.append(self.spinner)
            self.container.append(text_b)
        self.container.queue_draw()


