#message.py
"""
Handles the message widget
"""

import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GtkSource, Spelling
import os, datetime, threading, sys, base64, logging, re, tempfile
from ..sql_manager import prettify_model_name, generate_uuid, Instance as SQL
from . import attachments, blocks, dialog, voice, tools

logger = logging.getLogger(__name__)

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
        self.regenerate_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="update-symbolic",
            css_classes=["flat"],
            tooltip_text=_("Regenerate Message")
        )
        if self.message_element.get_model():
            self.regenerate_button.connect('clicked', lambda *_: GLib.idle_add(self.regenerate_message))
            container.append(self.regenerate_button)
        self.tts_button = voice.DictateToggleButton(self.message_element)
        container.append(self.tts_button)

    def change_status(self, status:bool):
        self.delete_button.set_sensitive(status)
        self.edit_button.set_sensitive(status)
        self.regenerate_button.set_sensitive(status)

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

    def regenerate_message(self):
        chat = self.message_element.chat
        model = self.get_root().get_selected_model().get_name()
        is_tool = any(a.file_type == 'tool' for a in list(self.message_element.attachment_container.container))
        for att in list(self.message_element.image_attachment_container.container):
            SQL.delete_attachment(att)
            att.get_parent().remove(att)
        for att in list(self.message_element.attachment_container.container):
            SQL.delete_attachment(att)
            att.get_parent().remove(att)
        if not chat.busy and model:
            self.message_element.block_container.clear()
            self.message_element.author = model
            self.message_element.update_profile_picture()
            self.message_element.popup.change_status(False)
            if is_tool:
                threading.Thread(
                    target=self.get_root().get_current_instance().use_tools,
                    args=(
                        self.message_element,
                        model,
                        tools.get_enabled_tools(self.get_root().get_application().main_alpaca_window.tool_listbox),
                        True
                    )
                ).start()
            else:
                threading.Thread(
                    target=self.message_element.get_root().get_current_instance().generate_message,
                    args=(
                        self.message_element,
                        model
                    )
                ).start()
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

        author = prettify_model_name(self.message.get_model())
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
            if os.getenv('ALPACA_USE_24H', '0') == '1':
                return date.format("%H:%M")
            else:
                return date.format("%I:%M %p")
        if date.format("%Y") == current_date.format("%Y"):
            if os.getenv('ALPACA_USE_24H', '0') == '1':
                return date.format("%b %d, %H:%M")
            else:
                return date.format("%b %d, %H:%M")
        if os.getenv('ALPACA_USE_24H', '0') == '1':
            return date.format("%b %d %Y, %H:%M")
        else:
            return date.format("%b %d %Y, %H:%M")

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

    def prepare_generating_block(self):
        """
        Prepares the generating text block, creating it if it does not exist
        """
        if not self.generating_block:
            self.generating_block = blocks.GeneratingText()
            self.append(self.generating_block)
            GLib.idle_add(self.message.popup.change_status, False)

    def remove_generating_block(self):
        if self.generating_block:
            self.remove(self.generating_block)
            self.generating_block = None

    def clear(self) -> None:
        for child in list(self):
            if child != self.generating_block:
                self.remove(child)
                child.unmap()
                child.unrealize()
        if len(list(self)) + len(list(self.message.image_attachment_container)) + len(list(self.message.attachment_container)) == 0:
            self.message.main_stack.set_visible_child_name('loading')

    def set_content(self, content:str) -> None:
        self.clear()

        #Thought
        think_pattern = r'(<think>(.*?)</think>)|(<\|begin_of_thought\|>(.*?)<\|end_of_thought\|>)'
        matches = re.findall(think_pattern, content, flags=re.DOTALL)
        for thought in [m[1].strip() if m[1] else m[3].strip() for m in matches]:
            attachment = attachments.Attachment(
                generate_uuid(),
                _('Thought'),
                'thought',
                thought
            )
            self.message.attachment_container.add_attachment(attachment)
            SQL.insert_or_update_attachment(self.message, attachment)

        clean_content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
        for block in blocks.text_to_block_list(clean_content):
            self.append(block)
        self.message.main_stack.set_visible_child_name('content')

    def add_content(self, content:str) -> None:
        """
        Used for live generation rendering
        """

        #Thought
        think_pattern = r'(<think>(.*?)</think>)|(<\|begin_of_thought\|>(.*?)<\|end_of_thought\|>)'
        matches = re.findall(think_pattern, content, flags=re.DOTALL)
        for thought in [m[1].strip() if m[1] else m[3].strip() for m in matches]:
            attachment = attachments.Attachment(
                generate_uuid(),
                _('Thought'),
                'thought',
                thought
            )
            self.message.attachment_container.add_attachment(attachment)
            SQL.insert_or_update_attachment(self.message, attachment)

        clean_content = re.sub(think_pattern, '', content, flags=re.DOTALL)

        for block in blocks.text_to_block_list(clean_content):
            if len(list(self)) <= 1:
                GLib.idle_add(self.prepend, block)
            else:
                if isinstance(list(self)[-2], blocks.Text) and isinstance(block, blocks.Text):
                    if not list(self)[-2].get_content().endswith('\n') and not block.get_content().startswith('\n'):
                        GLib.idle_add(list(self)[-2].append_content, '\n{}'.format(block.get_content()))
                    else:
                        GLib.idle_add(list(self)[-2].append_content, block.get_content())
                elif isinstance(list(self)[-2], blocks.Text) and not isinstance(block, blocks.Text):
                    GLib.idle_add(list(self)[-2].set_content, list(self)[-2].get_content().strip())
                    GLib.idle_add(self.insert_child_after, block, list(self)[-2])
                else:
                    GLib.idle_add(self.insert_child_after, block, list(self)[-2])

        if not self.message.popup.tts_button.get_active() and (self.message.get_root().settings.get_value('tts-auto-dictate').unpack() or self.message.chat.chat_id=='LiveChat'):
            GLib.idle_add(self.message.popup.tts_button.set_active, True)

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

    def get_root(self) -> Gtk.Widget | None:
        root = super().get_root()
        if not root:
            root = self.chat.row.get_root()
        return root

    def get_content(self) -> str:
        return ''.join(self.block_container.get_content())

    def get_content_for_dictation(self) -> str:
        return '\n'.join([c.get_content_for_dictation() for c in list(self.block_container) if c is not None])

    def get_model(self) -> str or None:
        """
        Get the model name if the author is a model
        """
        if self.mode == 1:
            return self.author

    def update_header(self, pfp_b64:str = None) -> None:
        if self.popup:
            self.popup.get_parent().set_popover()
        else:
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
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
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
        self.update_header(
            pfp_b64=SQL.get_model_preferences(self.get_model()).get('picture')
        )

    def add_attachment(self, file_id:str, name:str, attachment_type:str, content:str):
        if attachment_type == 'image':
            new_image = attachments.ImageAttachment(file_id, name, content)
            self.image_attachment_container.add_attachment(new_image)
            return new_image
        else:
            new_attachment = attachments.Attachment(file_id, name, attachment_type, content)
            self.attachment_container.add_attachment(new_attachment)
            return new_attachment

    def update_message(self, content):
        if content:
            GLib.idle_add(self.main_stack.set_visible_child_name, 'content')
            vadjustment = self.chat.scrolledwindow.get_vadjustment()
            if vadjustment.get_value() + 150 >= vadjustment.get_upper() - vadjustment.get_page_size():
                GLib.idle_add(vadjustment.set_value, vadjustment.get_upper() - vadjustment.get_page_size())
            GLib.idle_add(self.block_container.generating_block.append_content, content)

    def finish_generation(self, response_metadata:str=None):
        def send_notification():
            result_text = self.get_content()
            if result_text:
                dialog.show_notification(
                    root_widget=self.get_root(),
                    title=self.chat.get_name(),
                    body=result_text[:200] + (result_text[200:] and '…'),
                    icon=Gio.ThemedIcon.new('chat-message-new-symbolic')
                )

        self.popup.change_status(True)
        if self.get_root().get_name() == 'AlpacaWindow':
            GLib.idle_add(self.chat.row.spinner.set_visible, False)
            if self.get_root().chat_bin.get_child().get_name() != self.chat.get_name():
                GLib.idle_add(self.chat.row.indicator.set_visible, True)
        elif self.get_root().get_name() == 'AlpacaQuickAsk':
            GLib.idle_add(self.get_root().save_button.set_sensitive, True)

        self.chat.stop_message()
        buffer = self.block_container.generating_block.buffer
        final_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        self.block_container.add_content(final_text)
        self.dt = datetime.datetime.now()
        GLib.idle_add(self.block_container.remove_generating_block)
        GLib.idle_add(self.update_profile_picture)
        GLib.idle_add(send_notification)
        GLib.idle_add(self.save)

        if response_metadata:
            attachment = self.add_attachment(
                file_id=generate_uuid(),
                name=_('Metadata'),
                attachment_type='metadata',
                content=response_metadata
            )
            SQL.insert_or_update_attachment(self, attachment)

        sys.exit() #Exit thread

    def save(self):
        if self.chat.chat_id:
            SQL.insert_or_update_message(self)

class GlobalMessageTextView(GtkSource.View):
    __gtype_name__ = 'AlpacaGlobalMessageTextView'

    def __init__(self, parent_footer):
        self.parent_footer = parent_footer
        super().__init__(
            css_classes=['message_text_view'],
            top_margin=10,
            bottom_margin=10,
            hexpand=True,
            wrap_mode=3,
            valign=3,
            name="main_text_view"
        )

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', lambda *_: self.parent_footer.on_file_drop(*_))
        self.add_controller(drop_target)
        self.get_buffer().set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('adwaita'))
        self.connect('paste-clipboard', self.on_clipboard_paste)
        enter_key_controller = Gtk.EventControllerKey.new()
        enter_key_controller.connect("key-pressed", self.enter_key_handler)
        self.add_controller(enter_key_controller)
        checker = Spelling.Checker.get_default()
        adapter = Spelling.TextBufferAdapter.new(self.get_buffer(), checker)
        self.set_extra_menu(adapter.get_menu_model())
        self.insert_action_group('spelling', adapter)
        adapter.set_enabled(True)

    def cb_text_received(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            #Check if text is a Youtube URL
            youtube_regex = re.compile(
                r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
                r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
            url_regex = re.compile(
                r'http[s]?://'
                r'(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|'
                r'(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                r'(?:\\:[0-9]{1,5})?'
                r'(?:/[^\\s]*)?'
            )
            if youtube_regex.match(text):
                dialog.simple(
                    parent = self.get_root(),
                    heading = _('Attach YouTube Video?'),
                    body = _('Note that YouTube might block access to captions, please check output'),
                    callback = lambda url=text: threading.Thread(target=self.parent_footer.attachment_container.attach_youtube, args=(url,)).start()
                )
            elif url_regex.match(text):
                dialog.simple(
                    parent = self.get_root(),
                    heading = _('Attach Website? (Experimental)'),
                    body = _("Are you sure you want to attach\n'{}'?").format(text),
                    callback = lambda url=text: threading.Thread(target=self.parent_footer.attachment_container.attach_website, args=(url,)).start()
                )
        except Exception as e:
            pass

    def cb_image_received(self, clipboard, result):
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                if not self.get_root().get_selected_model().get_vision():
                    dialog.show_toast(_("This model might not be compatible with image recognition"), self.get_root())
                tdir = tempfile.TemporaryDirectory()
                texture.save_to_png(os.path.join(tdir.name, 'image.png'))
                file = Gio.File.new_for_path(os.path.join(tdir.name, 'image.png'))
                self.parent_footer.attachment_container.on_attachment(file)
                tdir.cleanup()
        except Exception as e:
            pass

    def on_clipboard_paste(self, textview):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_texture_async(None, self.cb_image_received)
        clipboard.read_text_async(None, self.cb_text_received)

    def enter_key_handler(self, controller, keyval, keycode, state):
        if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK): # Enter pressed without shift
            mode = 0
            if state & Gdk.ModifierType.CONTROL_MASK: # Ctrl, send system message
                mode = 1
            elif state & Gdk.ModifierType.ALT_MASK or self.get_root().settings.get_value('prefer-tools').unpack(): # Alt, send tool message
                mode = 2
            self.parent_footer.send_callback(mode)
            return True

class GlobalActionStack(Gtk.Stack):
    __gtype_name__ = 'AlpacaGlobalActionStack'

    def __init__(self, parent_footer):
        self.parent_footer = parent_footer
        super().__init__(
            transition_type=1
        )
        send_button = Gtk.Button(
            vexpand=False,
            valign=3,
            tooltip_text=_('Send Message'),
            icon_name='paper-plane-symbolic',
            css_classes=['accent', 'circular', 'suggested-action']
        )
        self.add_named(send_button, 'send')

        stop_button = Gtk.Button(
            vexpand=False,
            valign=3,
            tooltip_text=_('Stop Message'),
            icon_name='media-playback-stop-symbolic',
            css_classes=['destructive-action', 'circular']
        )
        self.add_named(stop_button, 'stop')

        stop_button.connect('clicked', lambda button: self.get_root().chat_bin.get_child().stop_message())

        send_button.connect('clicked', lambda button: self.use_default_mode())
        gesture_click = Gtk.GestureClick(button=3)
        gesture_click.connect("released", lambda gesture, _n_press, x, y: self.show_popup(gesture, x, y))
        send_button.add_controller(gesture_click)
        gesture_long_press = Gtk.GestureLongPress()
        gesture_long_press.connect("pressed", self.show_popup)
        send_button.add_controller(gesture_long_press)

    def use_default_mode(self):
        if self.get_root().settings.get_value('prefer-tools').unpack():
            self.parent_footer.send_callback(2)
        else:
            self.parent_footer.send_callback(0)

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Send as User'),
                    'callback': lambda: self.parent_footer.send_callback(0),
                    'icon': None
                },
                {
                    'label': _('Send as System'),
                    'callback': lambda: self.parent_footer.send_callback(1),
                    'icon': None
                },
                {
                    'label': _('Use Tools'),
                    'callback': lambda: self.parent_footer.send_callback(2),
                    'icon': None
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

class GlobalFooter(Gtk.Box):
    __gtype_name__ = 'AlpacaGlobalFooter'

    def __init__(self, send_callback:callable):
        self.send_callback = send_callback
        super().__init__(
            spacing=12,
            orientation=1,
            css_classes=['p10']
        )
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.on_file_drop)
        self.add_controller(drop_target)

        self.attachment_container = attachments.GlobalAttachmentContainer()
        self.append(self.attachment_container)

        controls_container = Gtk.Box(spacing=12)
        self.append(controls_container)

        self.attachment_button = attachments.GlobalAttachmentButton()
        controls_container.append(self.attachment_button)

        self.message_text_view_container = Gtk.Box(
            overflow=1,
            css_classes=['card']
        )
        controls_container.append(self.message_text_view_container)
        self.message_text_view = GlobalMessageTextView(self)
        message_text_view_scroller = Gtk.ScrolledWindow(
            max_content_height=150,
            propagate_natural_height=True,
            min_content_height=1,
            css_classes=['undershoot-bottom'],
            child=self.message_text_view
        )
        self.message_text_view_container.append(message_text_view_scroller)

        self.microphone_button = voice.MicrophoneButton(self.message_text_view)
        self.message_text_view_container.append(self.microphone_button)

        self.action_stack = GlobalActionStack(self)
        controls_container.append(self.action_stack)

    def on_file_drop(self, drop_target, value, x, y):
        files = value.get_files()
        for file in files:
            self.attachment_container.on_attachment(file)

    def toggle_action_button(self, state:bool):
        self.action_stack.set_visible_child_name('send' if state else 'stop')

    def get_buffer(self):
        return self.message_text_view.get_buffer()

    def remove_text(self, text:str):
        buffer = self.get_buffer()
        current_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        current_text = current_text.replace(text, '')
        buffer.set_text(current_text, len(current_text.encode('utf-8')))



