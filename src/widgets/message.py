#message.py
"""
Handles the message widget
"""

import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GtkSource, Spelling
import os, datetime, threading, sys, base64, logging, re, tempfile
from ..sql_manager import prettify_model_name, generate_uuid, format_datetime, Instance as SQL
from . import attachments, blocks, dialog, voice, tools, models, chat, activities


logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/popup.ui')
class OptionPopup(Gtk.Popover):
    __gtype_name__ = 'AlpacaMessagePopup'

    model_button = Gtk.Template.Child()
    delete_button = Gtk.Template.Child()
    copy_button = Gtk.Template.Child()
    edit_button = Gtk.Template.Child()
    regenerate_button = Gtk.Template.Child()
    tts_button = Gtk.Template.Child()

    def change_status(self, status:bool):
        self.delete_button.set_sensitive(status)
        self.edit_button.set_sensitive(status)
        self.regenerate_button.set_sensitive(status)

    @Gtk.Template.Callback()
    def on_show(self, udata):
        message_element = self.get_ancestor(Message)
        found_model = models.added.list_from_selector().get(message_element.author)
        self.model_button.set_visible(bool(found_model))

    @Gtk.Template.Callback()
    def show_model_dialog(self, button):
        self.popdown()
        message_element = self.get_ancestor(Message)
        found_model = models.added.list_from_selector().get(message_element.author)
        if found_model:
            models.added.AddedModelDialog(found_model).present(self.get_root())

    @Gtk.Template.Callback()
    def delete_message(self, button=None):
        message_element = self.get_ancestor(Message)
        chat_element = self.get_ancestor(chat.Chat)
        message_id = message_element.message_id
        SQL.delete_message(message_element)
        message_element.unparent()
        if len(list(chat_element.container)) == 0:
            chat_element.set_visible_child_name('welcome-screen')

    @Gtk.Template.Callback()
    def copy_message(self, button=None):
        message_element = self.get_ancestor(Message)
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(message_element.get_content())
        dialog.show_toast(_("Message copied to the clipboard"), self.get_root())

    @Gtk.Template.Callback()
    def edit_message(self, button=None):
        message_element = self.get_ancestor(Message)
        self.popdown()
        self.change_status(False)
        message_element.set_halign(0)
        message_element.main_stack.get_child_by_name('editing').set_visible(True)
        message_element.main_stack.get_child_by_name('editing').set_content(message_element.get_content())
        message_element.main_stack.set_visible_child_name('editing')

    @Gtk.Template.Callback()
    def regenerate_message(self, button=None):
        message_element = self.get_ancestor(Message)
        chat_element = self.get_ancestor(chat.Chat)
        current_model = self.get_root().get_selected_model().get_name()

        if not chat_element.busy and current_model:
            for att in list(message_element.image_attachment_container.container) + list(message_element.attachment_container.container):
                SQL.delete_attachment(att)
                att.unparent()

            message_element.block_container.clear()
            message_element.main_stack.set_visible_child_name('loading')
            message_element.author = current_model
            message_element.update_profile_picture()

            selected_tool = self.get_root().global_footer.tool_selector.get_selected_item()
            tools = {}
            if selected_tool.runnable:
                tools = {selected_tool.name: selected_tool}
            elif selected_tool.name == 'auto_tool':
                tools = {t.name: t for t in list(self.get_root().global_footer.tool_selector.get_model()) if t.runnable}

            if len(tools) > 0:
                threading.Thread(
                    target=self.get_root().get_current_instance().use_tools,
                    args=(
                        message_element,
                        current_model,
                        tools,
                        True
                    ),
                    daemon=True
                ).start()
            else:
                threading.Thread(
                    target=message_element.get_root().get_current_instance().generate_message,
                    args=(
                        message_element,
                        current_model
                    ),
                    daemon=True
                ).start()

            message_element.main_stack.set_visible_child_name('loading')
        else:
            dialog.show_toast(_("Message cannot be regenerated while receiving a response"), self.get_root())

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/block_container.ui')
class BlockContainer(Gtk.Box):
    __gtype_name__ = 'AlpacaBlockContainer'

    def __init__(self):
        super().__init__()
        self.generating_block = None
        self.thinking_block = None

    def show_generating_block(self):
        if not self.generating_block or not self.generating_block.get_parent():
            self.generating_block = blocks.GeneratingText()
            GLib.idle_add(self.append, self.generating_block)

    def remove_generating_block(self):
        if self.generating_block.get_parent():
            self.remove(self.generating_block)

    def show_thinking_block(self):
        if not self.thinking_block or not self.thinking_block.get_parent():
            self.thinking_block = blocks.Thinking()
            GLib.idle_add(self.prepend, self.thinking_block)

    def remove_thinking_block(self):
        if self.thinking_block.get_parent():
            self.remove(self.thinking_block)

    def clear(self) -> None:
        for child in list(self):
            if child != self.generating_block:
                self.remove(child)

    def set_content(self, content:str) -> None:
        self.clear()
        message = self.get_ancestor(Message)

        for block in blocks.text_to_block_list(content):
            GLib.idle_add(self.append, block)
        GLib.idle_add(message.main_stack.set_visible_child_name, 'content')

    def check_if_should_tts(self):
        chat_element = self.get_ancestor(chat.Chat)
        if not self.get_root():
            return
        message = self.get_ancestor(Message)
        if not message.popup.tts_button.get_active() and (self.get_root().settings.get_value('tts-auto-dictate').unpack() or (chat_element and chat_element.chat_id=='LiveChat')):
            message.popup.tts_button.set_active(True)

    def add_content(self, content:str) -> None:
        """
        Used for live generation rendering
        """

        for block in blocks.text_to_block_list(content):
            if len(list(self)) <= 1:
                self.prepend(block)
            else:
                if isinstance(list(self)[-2], blocks.Text) and isinstance(block, blocks.Text):
                    if not list(self)[-2].get_content().endswith('\n') and not block.get_content().startswith('\n'):
                        GLib.idle_add(list(self)[-2].append_content, '\n{}'.format(block.get_content()))
                    else:
                        GLib.idle_add(list(self)[-2].append_content, block.get_content())
                elif isinstance(list(self)[-2], blocks.Text) and not isinstance(block, blocks.Text):
                    list(self)[-2].set_content(list(self)[-2].get_content().strip())
                    self.insert_child_after(block, list(self)[-2])
                else:
                    self.insert_child_after(block, list(self)[-2])
        GLib.idle_add(self.check_if_should_tts)

    def get_content(self) -> list:
        return [block.get_content() for block in list(self)]

    def add_thinking(self, content:str) -> None:
        self.show_thinking_block()
        GLib.idle_add(self.thinking_block.append_content, content)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/message.ui')
class Message(Gtk.Box):
    __gtype_name__ = 'AlpacaMessage'

    main_container = Gtk.Template.Child()
    pfp_options_button = Gtk.Template.Child()
    header_options_button = Gtk.Template.Child()
    header_label = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    content_container = Gtk.Template.Child()
    image_attachment_container = Gtk.Template.Child()
    attachment_container = Gtk.Template.Child()
    block_container = Gtk.Template.Child()

    def __init__(self, dt:datetime.datetime, message_id:str=-1, mode:int=0, author:str=None):
        """
        Mode 0: User
        Mode 1: Assistant
        Mode 2: System
        """
        self.mode = mode
        self.author = author
        self.dt = dt
        self.option_button = None
        self.message_id = message_id

        super().__init__()
        self.popup = OptionPopup()
        self.popup.regenerate_button.set_visible(self.author)

        self.set_halign(2 if mode == 0 else 0)
        self.main_container.set_css_classes(['card', 'user_message'] if mode==0 else ['response_message'])
        self.main_container.set_size_request(100 if mode==0 else -1, -1)

        if self.mode == 2:
            self.block_container.set_css_classes(['dim-label'])

        self.update_profile_picture()

    def get_content(self) -> str:
        return ''.join(self.block_container.get_content())

    def get_content_for_dictation(self) -> str:
        return '\n'.join([c.get_content_for_dictation().strip() for c in list(self.block_container) if c is not None])

    def get_model(self) -> str or None:
        """
        Get the model name if the author is a model
        """
        if self.mode == 1:
            return self.author

    def update_header(self, pfp_b64:str = None) -> None:
        author = prettify_model_name(self.get_model())
        if not author:
            author = ""

        if ':' in author:
            author = author.split(':')
            if author[1].lower() not in ('latest', 'custom'):
                author = '{} ({})'.format(author[0], author[1])
            else:
                author = author[0]
        author = author.title()

        self.popup.unparent()
        if pfp_b64: # There's going to be a profile picture
            # Adjust header label
            self.header_label.set_margin_start(5)
            self.header_label.remove_css_class('dim-label')
            self.header_label.set_markup(
                "<span weight='bold'>{}</span>\n<small>{}</small>".format(
                    author,
                    GLib.markup_escape_text(format_datetime(self.dt))
                )
            )

            # Prepare profile picture
            image_data = base64.b64decode(pfp_b64)
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            image_element = Gtk.Image.new_from_paintable(texture)
            image_element.set_size_request(40, 40)
            image_element.set_pixel_size(40)
            self.pfp_options_button.set_child(image_element)
            list(self.pfp_options_button)[0].set_overflow(1)

            # Give popup to profile picture
            self.pfp_options_button.set_popover(self.popup)
        else:
            # Adjust header label
            self.header_label.set_margin_start(0)
            self.header_label.add_css_class('dim-label')
            self.header_label.set_markup(
                "<small>{}{}</small>".format(
                    ('{} • ' if author else '{}').format(author),
                    GLib.markup_escape_text(format_datetime(self.dt))
                )
            )

            # Give popup to header ... button
            self.header_options_button.set_popover(self.popup)

        self.header_options_button.set_visible(not pfp_b64)
        self.pfp_options_button.set_visible(pfp_b64)

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
            GLib.idle_add(self.block_container.generating_block.append_content, content)
            self.main_stack.set_visible_child_name('content')

            chat_element = self.get_ancestor(chat.Chat)
            if chat_element:
                vadjustment = chat_element.scrolledwindow.get_vadjustment()
                if vadjustment.get_value() + 150 >= vadjustment.get_upper() - vadjustment.get_page_size():
                    GLib.idle_add(vadjustment.set_value, vadjustment.get_upper() - vadjustment.get_page_size())
        if self.block_container.thinking_block and self.block_container.thinking_block.get_parent():
            attachment = attachments.Attachment(
                generate_uuid(),
                _('Thought'),
                'thought',
                self.block_container.thinking_block.get_content()
            )
            self.attachment_container.add_attachment(attachment)
            SQL.insert_or_update_attachment(self, attachment)
            self.block_container.remove_thinking_block()

    def update_thinking(self, content):
        if content:
            self.block_container.add_thinking(content)
            self.main_stack.set_visible_child_name('content')

            chat_element = self.get_ancestor(chat.Chat)
            if chat_element:
                vadjustment = chat_element.scrolledwindow.get_vadjustment()
                if vadjustment.get_value() + 150 >= vadjustment.get_upper() - vadjustment.get_page_size():
                    GLib.idle_add(vadjustment.set_value, vadjustment.get_upper() - vadjustment.get_page_size())

    def finish_generation(self, response_metadata:str=None):
        chat_element = self.get_ancestor(chat.Chat)
        root = chat_element.get_root() or chat_element.row.get_root()

        def send_notification():
            result_text = self.get_content()
            if result_text and root:
                dialog.show_notification(
                    root_widget=root,
                    title=chat_element.get_name() if chat_element else _("Chat"),
                    body=result_text[:200] + (result_text[200:] and '…'),
                    icon=Gio.ThemedIcon.new('chat-message-new-symbolic')
                )

        if root and root.get_name() == 'AlpacaWindow' and chat_element:
            chat_element.row.spinner.set_visible(False)
            if root.chat_bin.get_child().get_name() != chat_element.get_name():
                chat_element.row.indicator.set_visible(True)
        elif root and root.get_name() == 'AlpacaQuickAsk':
            root.save_button.set_sensitive(True)

        self.popup.change_status(True)

        if chat_element and root:
            chat_element.stop_message()
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
        chat_element = self.get_ancestor(chat.Chat)
        if chat_element and chat_element.chat_id:
            SQL.insert_or_update_message(self)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/global_message_textview.ui')
class GlobalMessageTextView(GtkSource.View):
    __gtype_name__ = 'AlpacaGlobalMessageTextView'

    def __init__(self):
        super().__init__()
        self.remove_css_class('view')

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', lambda *_: self.get_ancestor(GlobalFooter).on_file_drop(*_))
        self.add_controller(drop_target)
        self.get_buffer().set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('adwaita'))

        adapter = Spelling.TextBufferAdapter.new(self.get_buffer(), Spelling.Checker.get_default())
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
                    callback = lambda url=text: threading.Thread(target=self.get_ancestor(GlobalFooter).attachment_container.attach_youtube, args=(url,), daemon=True).start()
                )
            elif url_regex.match(text):
                dialog.simple(
                    parent = self.get_root(),
                    heading = _('Attach Website? (Experimental)'),
                    body = _("Are you sure you want to attach\n'{}'?").format(text),
                    callback = lambda url=text: threading.Thread(target=self.get_ancestor(GlobalFooter).attachment_container.attach_website, args=(url,), daemon=True).start()
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
                self.get_ancestor(GlobalFooter).attachment_container.on_attachment(file)
                tdir.cleanup()
        except Exception as e:
            pass

    @Gtk.Template.Callback()
    def on_clipboard_paste(self, textview):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_texture_async(None, self.cb_image_received)
        clipboard.read_text_async(None, self.cb_text_received)

    @Gtk.Template.Callback()
    def enter_key_handler(self, controller, keyval, keycode, state):
        if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK): # Enter pressed without shift
            if state & Gdk.ModifierType.CONTROL_MASK: # Ctrl, send system message
                self.get_ancestor(GlobalFooter).send_callback(1)
            else:
                self.get_ancestor(GlobalFooter).action_stack.use_default_mode()
            return True

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/global_action_stack.ui')
class GlobalActionStack(Gtk.Stack):
    __gtype_name__ = 'AlpacaGlobalActionStack'

    @Gtk.Template.Callback()
    def stop_message(self, button=None):
        self.get_root().chat_bin.get_child().stop_message()

    @Gtk.Template.Callback()
    def use_default_mode(self, button=None):
        parent_footer = self.get_ancestor(GlobalFooter)
        if not parent_footer.send_callback:
            return

        selected_tool = parent_footer.tool_selector.get_selected_item()
        if selected_tool.runnable:
            parent_footer.send_callback(0, {selected_tool.name: selected_tool})
        elif selected_tool.name == 'auto_tool':
            parent_footer.send_callback(0, {t.name: t for t in list(parent_footer.tool_selector.get_model()) if t.runnable})
        else:
            parent_footer.send_callback(0)

    @Gtk.Template.Callback()
    def show_popup(self, *args):
        if not self.get_ancestor(GlobalFooter).send_callback:
            return

        rect = Gdk.Rectangle()
        if len(args) == 4:
            rect.x, rect.y = args[2], args[3]
        else:
            rect.x, rect.y = args[1], args[2]

        actions = [
            [
                {
                    'label': _('Send as User'),
                    'callback': self.use_default_mode,
                    'icon': None
                },
                {
                    'label': _('Send as System'),
                    'callback': lambda: self.get_ancestor(GlobalFooter).send_callback(1),
                    'icon': None
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/global_footer.ui')
class GlobalFooter(Gtk.Box):
    __gtype_name__ = 'AlpacaGlobalFooter'

    attachment_container = Gtk.Template.Child()
    message_text_view_container = Gtk.Template.Child()
    message_text_view = Gtk.Template.Child()
    action_stack = Gtk.Template.Child()
    attachment_button = Gtk.Template.Child()
    microphone_button = Gtk.Template.Child()
    model_manager_shortcut = Gtk.Template.Child()
    model_selector = Gtk.Template.Child()
    tool_selector = Gtk.Template.Child()
    wrap_box = Gtk.Template.Child()

    def __init__(self):
        self.send_callback = None
        super().__init__()
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.on_file_drop)
        self.add_controller(drop_target)

        self.microphone_button.set_text_view(self.message_text_view)
        self.attachment_button.set_attachment_container(self.attachment_container)

        settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        settings.bind('show-model-manager-shortcut', self.model_manager_shortcut, 'visible', Gio.SettingsBindFlags.DEFAULT)

        self.model_selector.selector.connect('notify::selected', lambda dropdown, gparam: self.tool_selector.model_changed(dropdown))
        self.action_stack.set_sensitive(len(models.added.model_selector_model) > 0)
        models.added.model_selector_model.connect('notify::n-items', lambda m, p: self.action_stack.set_sensitive(len(m) > 0))
        GLib.idle_add(self.set_send_callback)

    def set_send_callback(self):
        live_chat = self.get_ancestor(activities.LiveChat)
        if live_chat:
            self.send_callback = live_chat.send_message
        else:
            self.send_callback = self.get_root().send_message

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


@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/message/scrollable_textview.ui')
class ScrollableTextView(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaScrollableTextView'

    text_view = Gtk.Template.Child()
    buffer = Gtk.Template.Child()

    def set_text(self, text:str) -> None:
        self.buffer.set_text(text, len(text.encode('utf-8')))

    def get_text(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
