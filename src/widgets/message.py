#message.py
"""
Handles the message widget
"""

import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf
import os, datetime, threading, sys, base64, logging
from ..constants import TTS_VOICES
from ..sql_manager import Instance as SQL
from . import model_manager, attachments, blocks, dialog

logger = logging.getLogger(__name__)

window = None

class OptionPopup(Gtk.Popover):
    __gtype_name__ = 'AlpacaMessagePopup'

    def __init__(self, message_element):
        self.message_element = message_element
        container = Gtk.Box(
            spacing=5
        )
        super().__init__(
            has_arrow=True,
            child=container
        )

        self.delete_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="user-trash-symbolic",
            css_classes = ["flat"],
            tooltip_text = _("Remove Message")
        )
        self.delete_button.connect('clicked', lambda *_: self.delete_message())
        container.append(self.delete_button)

        self.copy_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="edit-copy-symbolic",
            css_classes=["flat"],
            tooltip_text=_("Copy Message")
        )
        self.copy_button.connect('clicked', lambda *_: self.copy_message())
        container.append(self.copy_button)

        self.edit_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="edit-symbolic",
            css_classes=["flat"],
            tooltip_text=_("Edit Message")
        )
        self.edit_button.connect('clicked', lambda *_: self.edit_message())

        container.append(self.edit_button)
        if self.message_element.get_model():
            self.regenerate_button = Gtk.Button(
                halign=1,
                hexpand=True,
                icon_name="update-symbolic",
                css_classes=["flat"],
                tooltip_text=_("Regenerate Message")
            )
            self.regenerate_button.connect('clicked', lambda *_: self.regenerate_message())
            container.append(self.regenerate_button)

        self.tts_stack = Gtk.Stack()
        container.append(self.tts_stack)
        self.tts_button = Gtk.ToggleButton(
            halign=1,
            hexpand=True,
            icon_name='bullhorn-symbolic',
            css_classes=["flat"],
            tooltip_text=_("Dictate Message")
        )
        self.tts_button.connect('toggled', self.dictate_message)
        self.tts_stack.add_named(self.tts_button, 'button')
        self.tts_stack.add_named(Adw.Spinner(css_classes=['p10']), 'loading')

    def delete_message(self):
        logger.debug("Deleting message")
        chat = self.message_element.chat
        message_id = self.message_element.message_id
        SQL.delete_message(self.message_element)
        self.message_element.get_parent().remove(self.message_element)
        if len(list(chat.container)) == 0:
            chat.set_visible_child_name('welcome-screen')

    def copy_message(self):
        logger.debug("Copying message")
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.message_element.get_content())
        dialog.show_toast(_("Message copied to the clipboard"), self.get_root())

    def edit_message(self):
        logger.debug("Editing message")
        self.popdown()
        self.message_element.header_container.set_visible(False)
        self.message_element.set_halign(0)
        self.message_element.main_stack.get_child_by_name('editing').set_visible(True)
        self.message_element.main_stack.get_child_by_name('editing').set_content(self.message_element.get_content())
        self.message_element.main_stack.set_visible_child_name('editing')

    def dictate_message(self, button):
        # I know I'm not supposed to be importing stuff inside functions
        # but these libraries take a while to import and make the app launch 2x slower
        def run(text:str, btn):
            GLib.idle_add(self.tts_stack.set_visible_child_name, 'loading')
            import sounddevice as sd
            from kokoro import KPipeline
            voice = None
            if self.message_element.get_model():
                voice = SQL.get_model_preferences(self.message_element.get_model()).get('voice', 'af_heart')
            else:
                voice = SQL.get_preference('tts_voice', 'af_heart')
            if not voice:
                voice = 'af_heart'
            if model_manager.tts_model_path:
                if not os.path.islink(os.path.join(model_manager.tts_model_path, '{}.pt'.format(voice))):
                    pretty_name = [k for k, v in TTS_VOICES.items() if v == voice]
                    if len(pretty_name) > 0:
                        pretty_name = pretty_name[0]
                        window.local_model_flowbox.append(model_manager.TextToSpeechModel(pretty_name))
            tts_engine = KPipeline(lang_code=voice[0])

            generator = tts_engine(
                text,
                voice=voice,
                speed=1.2,
                split_pattern=r'\n+'
            )
            for gs, ps, audio in generator:
                if not btn.get_active():
                    break
                sd.play(audio, samplerate=24000)
                GLib.idle_add(self.tts_stack.set_visible_child_name, 'button')
                sd.wait()
            GLib.idle_add(self.tts_button.set_active, False)

        if button.get_active():
            GLib.idle_add(self.message_element.add_css_class, 'tts_message')
            if window.message_dictated and window.message_dictated.popup.tts_button.get_active():
                 window.message_dictated.popup.tts_button.set_active(False)
            window.message_dictated = self.message_element
            threading.Thread(target=run, args=(self.message_element.get_content(), button)).start()
        else:
            import sounddevice as sd
            GLib.idle_add(self.message_element.remove_css_class, 'tts_message')
            GLib.idle_add(self.tts_stack.set_visible_child_name, 'button')
            window.message_dictated = None
            threading.Thread(target=sd.stop).start()

    def regenerate_message(self):
        chat = self.message_element.chat
        model = model_manager.get_selected_model().get_name()
        if not chat.busy and model:
            self.message_element.block_container.clear()
            self.message_element.author = model
            self.message_element.update_profile_picture()
            self.message_element.options_button.set_sensitive(False)
            threading.Thread(target=window.get_current_instance().generate_message, args=(self.message_element, model)).start()
        else:
            dialog.show_toast(_("Message cannot be regenerated while receiving a response"), self.get_root())

class MessageHeader(Gtk.Box):
    __gtype_name__ = 'AlpacaMessageHeader'

    def __init__(self, message, dt:datetime.datetime, popover=None):
        self.message = message
        super().__init__(
            orientation=0,
            hexpand=True,
            spacing=5,
            halign=0
        )
        if popover:
            self.message.options_button = Gtk.MenuButton(
                icon_name='view-more-horizontal-symbolic',
                css_classes=['message_options_button', 'flat', 'circular', 'dim-label'],
                popover=popover
            )
            self.append(self.message.options_button)

        label = Gtk.Label(
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            margin_end=5,
            margin_start=0 if popover else 5,
            xalign=0,
            focusable=True,
            css_classes=['dim-label'] if popover else []
        )

        author = window.convert_model_name(self.message.get_model(), 0)
        if not author:
            author = ""

        if ':' in author:
            author = author.split(':')
            if author[1].lower() not in ('latest', 'custom'):
                author = '{} ({})'.format(author[0], author[1])
            else:
                author = author[0]
        author = author.title()

        if popover:
            label.set_markup(
                "<small>{}{}</small>".format(
                    ('{} • ' if self.message.author else '{}').format(author),
                    GLib.markup_escape_text(self.format_datetime(dt))
                )
            )
        else:
            label.set_markup(
                "<span weight='bold'>{}</span>\n<small>{}</small>".format(
                    author,
                    GLib.markup_escape_text(self.format_datetime(dt))
                )
            )
        self.append(label)

    def format_datetime(self, dt) -> str:
        date = GLib.DateTime.new(
            GLib.DateTime.new_now_local().get_timezone(),
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second
        )
        current_date = GLib.DateTime.new_now_local()
        if date.format("%Y/%m/%d") == current_date.format("%Y/%m/%d"):
            return date.format("%I:%M %p")
        if date.format("%Y") == current_date.format("%Y"):
            return date.format("%b %d, %I:%M %p")
        return date.format("%b %d %Y, %I:%M %p")

class BlockContainer(Gtk.Box):
    __gtype_name__ = 'AlpacaBlockContainer'

    def __init__(self, message):
        self.message = message
        super().__init__(
            orientation=1,
            halign=0,
            spacing=5,
            css_classes=['dim-label'] if message.mode == 2 else []
        )
        self.generating_block = None

    def get_generating_block(self) -> blocks.Text:
        """
        Gets the generating text block, creates it if it does not exist
        """
        if not self.generating_block:
            self.generating_block = blocks.GeneratingText()
            GLib.idle_add(self.append, self.generating_block)
            GLib.idle_add(self.message.options_button.set_sensitive, False)
        return self.generating_block

    def clear(self) -> None:
        self.message.main_stack.set_visible_child_name('loading')
        for child in list(self):
            self.remove(child)

    def set_content(self, content:str) -> None:
        self.clear()
        for block in blocks.text_to_block_list(content.strip(), self.message):
            self.append(block)
        self.message.main_stack.set_visible_child_name('content')

    def get_content(self) -> list:
        return [block.get_content() for block in list(self)]

class Message(Gtk.Box):
    __gtype_name__ = 'AlpacaMessage'

    def __init__(self, dt:datetime.datetime, message_id:str=-1, chat=None, mode:int=0, author:str=None):
        """
        Mode 0: User
        Mode 1: Assistant
        Mode 2: System
        """
        self.chat = chat
        self.mode = mode
        self.author = author
        self.dt = dt
        self.options_button = None
        self.message_id = message_id
        self.popup = None

        super().__init__(
            css_classes=["message"],
            name=message_id,
            halign=2 if mode == 0 else 0,
            spacing=2
        )
        self.pfp_container = Adw.Bin()
        self.append(self.pfp_container)

        main_container = Gtk.Box(
            orientation=1,
            halign=0,
            css_classes=["card", "user_message"] if mode==0 else ["response_message"],
            spacing=5,
            width_request=100 if mode==0 else -1
        )
        self.append(main_container)

        self.header_container = Adw.Bin(
            hexpand=True
        )
        main_container.append(self.header_container)

        self.main_stack = Gtk.Stack(
            transition_type=1
        )
        main_container.append(self.main_stack)
        self.main_stack.add_named(Adw.Spinner(css_classes=['p10']), 'loading')
        content_container = Gtk.Box(
            orientation=1,
            spacing=5
        )

        self.image_attachment_container = attachments.ImageAttachmentContainer()
        content_container.append(self.image_attachment_container)
        self.attachment_container = attachments.AttachmentContainer()
        content_container.append(self.attachment_container)

        self.block_container = BlockContainer(
            message=self
        )
        content_container.append(self.block_container)
        self.main_stack.add_named(content_container, 'content')
        self.main_stack.add_named(blocks.EditingText(self), 'editing')
        self.update_profile_picture()

    def get_content(self) -> str:
        return '\n\n'.join(self.block_container.get_content())

    def get_model(self) -> str or None:
        """
        Get the model name if the author is a model
        """
        if self.mode == 1:
            return self.author

    def update_header(self, pfp_b64:str = None) -> None:
        self.popup = OptionPopup(self)
        self.header_container.set_child(
            MessageHeader(
                message=self,
                dt=self.dt,
                popover=None if pfp_b64 else self.popup
            )
        )
        if pfp_b64:
            image_data = base64.b64decode(pfp_b64)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image_element = Gtk.Image.new_from_paintable(texture)
            image_element.set_size_request(40, 40)
            self.options_button = Gtk.MenuButton(
                width_request=40,
                height_request=40,
                css_classes=['circular', 'flat'],
                valign=1,
                popover=self.popup,
                margin_top=5,
                margin_start=5
            )
            self.options_button.set_overflow(1)
            self.options_button.set_child(image_element)
            list(self.options_button)[0].add_css_class('circular')
            list(self.options_button)[0].set_overflow(1)
            self.pfp_container.set_child(self.options_button)
        else:
            self.pfp_container.set_child()

    def update_profile_picture(self):
        model_name = self.get_model()
        if model_name:
            found_models = [model for model in list(model_manager.get_local_models().values()) if model.get_name() == model_name]
            if found_models:
                self.update_header(
                    pfp_b64=found_models[0].data.get('profile_picture')
                )
                return
        self.update_header()

    def add_attachment(self, file_id:str, name:str, attachment_type:str, content:str):
        if attachment_type == 'image':
            new_image = attachments.ImageAttachment(file_id, name, content)
            self.image_attachment_container.add_attachment(new_image)
            return new_image
        else:
            new_attachment = attachments.Attachment(file_id, name, attachment_type, content)
            self.attachment_container.add_attachment(new_attachment)
            return new_attachment

    def update_message(self, data:dict):
        if data.get('done'):
            self.options_button.set_sensitive(True)
            if self.chat.chat_id and self.chat.row:
                GLib.idle_add(self.chat.row.spinner.set_visible, False)
                if window.chat_list_box.get_selected_row().get_name() != self.chat.get_name():
                    GLib.idle_add(self.chat.row.indicator.set_visible, True)
                self.chat.set_visible_child_name('content')
            self.chat.stop_message()
            result_text = self.get_content()
            GLib.idle_add(self.block_container.set_content, result_text)
            self.dt = datetime.datetime.now()
            if result_text:
                window.show_notification(self.chat.get_name(), result_text[:200] + (result_text[200:] and '…'), Gio.ThemedIcon.new('chat-message-new-symbolic'))
            if not self.chat.chat_id:
                GLib.idle_add(window.quick_ask_save_button.set_sensitive, True)
            else:
                self.save()

            tts_auto_mode = SQL.get_preference('tts_auto_mode', 'never')
            if tts_auto_mode == 'always' or (tts_auto_mode == 'focused' and self.get_root().is_active()):
                self.popup.tts_button.set_active(True)

            sys.exit()

        elif data.get('content', False):
            GLib.idle_add(self.main_stack.set_visible_child_name, 'content')
            vadjustment = self.chat.scrolledwindow.get_vadjustment()
            if vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
                GLib.idle_add(vadjustment.set_value, vadjustment.get_upper() - vadjustment.get_page_size())
            GLib.idle_add(self.block_container.get_generating_block().append_content, data.get('content', ''))
        elif data.get('clear', False):
            GLib.idle_add(self.block_container.get_generating_block().set_content)
        elif data.get('add_css', False):
            GLib.idle_add(self.block_container.add_css_class, data.get('add_css'))
        elif data.get('remove_css', False):
            GLib.idle_add(self.block_container.remove_css_class, data.get('remove_css'))

    def save(self):
        if self.chat.chat_id:
            SQL.insert_or_update_message(self)
