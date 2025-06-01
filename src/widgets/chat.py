#chat.py
"""
Handles the chat widget
"""

import gi
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
import logging, os, datetime, random, json, threading
from ..constants import SAMPLE_PROMPTS, cache_dir
from ..sql_manager import generate_uuid, generate_numbered_name, Instance as SQL
from . import dialog
from .message import Message

logger = logging.getLogger(__name__)

window = None

class Notebook(Gtk.Stack):
    __gtype_name__ = 'AlpacaNotebook'
    chat_type = 'notebook'

    def __init__(self, chat_id:str=None, name:str=_("New Notebook")):
        super().__init__(
            name=name,
            transition_type=1
        )
        self.container = Gtk.Box(
            orientation=1,
            hexpand=True,
            vexpand=True,
            spacing=12,
            css_classes=['p10']
        )
        self.scrolledwindow = Gtk.ScrolledWindow(
            child=self.container,
            propagate_natural_height=True,
            kinetic_scrolling=True,
            vexpand=True,
            hexpand=True,
            css_classes=["undershoot-bottom"],
            hscrollbar_policy=2,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10,
            overflow=1
        )

        self.textview = Gtk.TextView(
            css_classes=["p10"],
            wrap_mode=3
        )
        self.textview.connect('notify::has-focus', lambda *_: self.textview_focus_changed())
        book_scrolledwindow = Gtk.ScrolledWindow(
            child=self.textview,
            propagate_natural_height=True,
            kinetic_scrolling=True,
            vexpand=True,
            hexpand=True,
            css_classes=["undershoot-bottom", "card"],
            hscrollbar_policy=2,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10,
            overflow=1
        )

        paned = Gtk.Paned(
            wide_handle=True,
            position=400
        )
        paned.set_start_child(self.scrolledwindow)
        paned.set_end_child(book_scrolledwindow)
        list(paned)[1].add_css_class('card')
        window.split_view_overlay.connect('notify::collapsed', lambda *_: paned.set_orientation(window.split_view_overlay.get_collapsed()))

        clamp = Adw.Clamp(
            maximum_size=1000,
            tightening_threshold=800,
            child=paned
        )
        self.add_named(Adw.Spinner(), 'loading')
        self.add_named(clamp, 'content')

        welcome_screen = Adw.StatusPage(
            icon_name="open-book-symbolic",
            title=_("Notebook"),
            description=_("Start a notebook with a message"),
            vexpand=True
        )
        list(welcome_screen)[0].add_css_class('undershoot-bottom')
        self.add_named(welcome_screen, 'welcome-screen')

        self.add_named(Adw.StatusPage(
            icon_name="sad-computer-symbolic",
            title=_("No Messages Found"),
            description=_("Uh oh! No messages found for your search.")
        ), 'no-results')

        self.busy = False
        self.chat_id = chat_id
        self.row = ChatRow(self)

    def textview_focus_changed(self):
        print('focus', self.textview.get_sensitive())
        return

        if not self.textview.has_focus() and len(list(self.container)) > 0:
            last_message = list(self.container)[-1]
            if last_message:
                last_notebook = None
                for att in list(last_message.attachment_container.container):
                    if att.file_type == 'notebook':
                        last_notebook = att
                if last_notebook:
                    last_notebook.file_content = self.get_notebook()
                    SQL.insert_or_update_attachment(last_message, last_notebook)


    def append_notebook(self, content:str):
        content += '\n\n'
        buffer = self.textview.get_buffer()
        buffer.insert(buffer.get_end_iter(), content, len(content.encode('utf8')))

    def set_notebook(self, content:str):
        content = content.replace('\n', '\n\n')
        buffer = self.textview.get_buffer()
        buffer.set_text(content, len(content.encode('utf8')))

    def get_notebook(self) -> str:
        buffer = self.textview.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def stop_message(self):
        self.busy = False
        window.switch_send_stop_button(True)

    def unload_messages(self):
        self.stop_message()
        for widget in list(self.container):
            self.container.remove(widget)
        self.set_visible_child_name('loading')

    def add_message(self, message):
        self.container.append(message)

    def load_messages(self):
        messages = SQL.get_messages(self)
        last_notebook = None
        for message in messages:
            message_element = Message(
                dt=datetime.datetime.strptime(message[3] + (":00" if message[3].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S'),
                message_id=message[0],
                chat=self,
                mode=('user', 'assistant', 'system').index(message[1]),
                author=message[2]
            )
            self.container.append(message_element)

            attachments = SQL.get_attachments(message_element)
            for attachment in attachments:
                message_element.add_attachment(
                    file_id=attachment[0],
                    name=attachment[2],
                    attachment_type=attachment[1],
                    content=attachment[3]
                )
                if attachment[1] == 'notebook' and attachment[3]:
                    last_notebook = attachment[3]
            GLib.idle_add(message_element.block_container.set_content, message[4])
        self.set_visible_child_name('content' if len(messages) > 0 else 'welcome-screen')
        if last_notebook:
            self.set_notebook(last_notebook)
    def convert_to_json(self, include_metadata:bool=False) -> dict:
        messages = []
        for message in list(self.container)[-2:]:
            if message.get_content() and message.dt:
                message_data = {
                    'role': ('user', 'assistant', 'system')[message.mode],
                    'content': []
                }
                for image in message.image_attachment_container.get_content():
                    message_data['content'].append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{image.get_content()}'
                        }
                    })
                message_data['content'].append({
                    'type': 'text',
                    'text': ''
                })
                for attachment in message.attachment_container.get_content():
                    message_data['content'][0]['text'] += '```{} ({})\n{}\n```\n\n'.format(attachment.get('name'), attachment.get('type'), attachment.get('content'))
                message_data['content'][0 if ("text" in message_data["content"][0]) else 1]['text'] += message.get_content()
                if include_metadata:
                    message_data['date'] = message.dt.strftime("%Y/%m/%d %H:%M:%S")
                    message_data['model'] = message.model
                messages.append(message_data)
        return messages

class Chat(Gtk.Stack):
    __gtype_name__ = 'AlpacaChat'
    chat_type = 'chat'

    def __init__(self, chat_id:str=None, name:str=_("New Chat")):
        super().__init__(
            name=name,
            transition_type=1
        )
        self.container = Gtk.Box(
            orientation=1,
            hexpand=True,
            vexpand=True,
            spacing=12,
            css_classes=['p10']
        )
        clamp = Adw.Clamp(
            maximum_size=1000,
            tightening_threshold=800,
            child=self.container
        )
        self.scrolledwindow = Gtk.ScrolledWindow(
            child=clamp,
            propagate_natural_height=True,
            kinetic_scrolling=True,
            vexpand=True,
            hexpand=True,
            css_classes=["undershoot-bottom"],
            hscrollbar_policy=2
        )
        self.add_named(Adw.Spinner(), 'loading')
        self.add_named(self.scrolledwindow, 'content')

        self.welcome_screen = Adw.StatusPage(
            icon_name="com.jeffser.Alpaca",
            title="Alpaca",
            description=_("Try one of these prompts"),
            vexpand=True
        )
        list(self.welcome_screen)[0].add_css_class('undershoot-bottom')
        self.add_named(self.welcome_screen, 'welcome-screen')
        self.refresh_welcome_screen_prompts()

        self.add_named(Adw.StatusPage(
            icon_name="sad-computer-symbolic",
            title=_("No Messages Found"),
            description=_("Uh oh! No messages found for your search.")
        ), 'no-results')

        self.busy = False
        self.chat_id = chat_id
        self.row = ChatRow(self)

    def refresh_welcome_screen_prompts(self):
        button_container = Gtk.Box(
            orientation=1,
            spacing=10,
            halign=3
        )
        for prompt in random.sample(SAMPLE_PROMPTS, 3):
            prompt_button = Gtk.Button(
                child=Gtk.Label(
                    label=prompt,
                    justify=2,
                    wrap=True
                ),
                tooltip_text=_("Send prompt: '{}'").format(prompt)
            )
            prompt_button.connect('clicked', lambda *_, prompt=prompt : self.send_sample_prompt(prompt))
            button_container.append(prompt_button)
        refresh_button = Gtk.Button(
            icon_name='view-refresh-symbolic',
            tooltip_text=_("Refresh Prompts"),
            halign=3,
            css_classes=["circular", "accent"]
        )
        refresh_button.connect('clicked', lambda *_: self.refresh_welcome_screen_prompts())
        button_container.append(refresh_button)
        self.welcome_screen.set_child(button_container)

    def stop_message(self):
        self.busy = False
        window.switch_send_stop_button(True)

    def unload_messages(self):
        self.stop_message()
        for widget in list(self.container):
            self.container.remove(widget)
        self.set_visible_child_name('loading')

    def add_message(self, message):
        self.container.append(message)

    def load_messages(self):
        messages = SQL.get_messages(self)
        for message in messages:
            message_element = Message(
                dt=datetime.datetime.strptime(message[3] + (":00" if message[3].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S'),
                message_id=message[0],
                chat=self,
                mode=('user', 'assistant', 'system').index(message[1]),
                author=message[2]
            )
            self.container.append(message_element)

            attachments = SQL.get_attachments(message_element)
            for attachment in attachments:
                message_element.add_attachment(
                    file_id=attachment[0],
                    name=attachment[2],
                    attachment_type=attachment[1],
                    content=attachment[3]
                )
            GLib.idle_add(message_element.block_container.set_content, message[4])
        self.set_visible_child_name('content' if len(messages) > 0 else 'welcome-screen')

    def send_sample_prompt(self, prompt:str):
        if len(list(window.local_model_flowbox)) > 0:
            if not self.chat_id:
                window.quick_chat(prompt, 0)
            else:
                buffer = window.message_text_view.get_buffer()
                buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
                buffer.insert(buffer.get_start_iter(), prompt, len(prompt.encode('utf-8')))
                window.send_message()
        elif window.get_current_instance().instance_type == 'empty':
            window.get_application().lookup_action('instance_manager').activate()
        else:
            window.get_application().lookup_action('model_manager').activate()

    def convert_to_json(self, include_metadata:bool=False) -> dict:
        messages = []
        for message in list(self.container):
            if message.get_content() and message.dt:
                message_data = {
                    'role': ('user', 'assistant', 'system')[message.mode],
                    'content': []
                }
                for image in message.image_attachment_container.get_content():
                    message_data['content'].append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{image.get_content()}'
                        }
                    })
                message_data['content'].append({
                    'type': 'text',
                    'text': ''
                })
                for attachment in message.attachment_container.get_content():
                    message_data['content'][0]['text'] += '```{} ({})\n{}\n```\n\n'.format(attachment.get('name'), attachment.get('type'), attachment.get('content'))
                message_data['content'][0 if ("text" in message_data["content"][0]) else 1]['text'] += message.get_content()
                if include_metadata:
                    message_data['date'] = message.dt.strftime("%Y/%m/%d %H:%M:%S")
                    message_data['model'] = message.model
                messages.append(message_data)
        return messages

class ChatRow(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaChatRow'

    def __init__(self, chat:Chat):
        self.chat = chat
        self.spinner = Adw.Spinner(visible=False)
        self.label = Gtk.Label(
            label=self.chat.get_name(),
            tooltip_text=self.chat.get_name(),
            hexpand=True,
            halign=0,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            xalign=0
        )
        self.indicator = Gtk.Image.new_from_icon_name("chat-bubble-text-symbolic")
        self.indicator.set_visible(False)
        self.indicator.set_css_classes(['accent'])
        container = Gtk.Box(
            spacing=5
        )
        if self.chat.chat_type == 'notebook':
            container.append(Gtk.Image.new_from_icon_name("open-book-symbolic"))
        container.append(self.label)
        container.append(self.spinner)
        container.append(self.indicator)
        super().__init__(
            css_classes = ['chat_row'],
            height_request = 45,
            child = container,
            name=self.chat.get_name()
        )

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.open_menu(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.open_menu)
        self.add_controller(self.gesture_long_press)

    def open_menu(self, gesture, x, y):
        position = Gdk.Rectangle()
        position.x = x
        position.y = y

        popover = Gtk.PopoverMenu(
            menu_model=window.chat_right_click_menu,
            has_arrow=False,
            halign=1,
            height_request=155
        )

        popover.add_child(Gtk.Button(label='fun'), '1')

        window.selected_chat_row = self

        popover.set_parent(self.get_child())
        popover.set_pointing_to(position)
        popover.popup()

    def update_profile_pictures(self):
        for msg in list(self.chat.container):
            msg.update_profile_picture()

    def rename(self, new_name:str):
        new_name = generate_numbered_name(new_name, [row.get_name() for row in list(self.get_parent())])
        self.label.set_label(new_name)
        self.label.set_tooltip_text(new_name)
        self.chat.set_name(new_name)
        self.set_name(new_name)
        SQL.insert_or_update_chat(self.chat)

    def prompt_rename(self):
        dialog.simple_entry(
            parent = self.get_root(),
            heading = _('Rename Chat?'),
            body = _("Renaming '{}'").format(self.get_name()),
            callback = lambda new_name: self.rename(new_name),
            entries = {'placeholder': _('Chat name'), 'default': True, 'text': self.get_name()},
            button_name = _('Rename')
        )

    def delete(self):
        self.chat.stop_message()
        list_box = self.get_parent()
        list_box.remove(self)
        self.chat.get_parent().remove(self.chat)
        SQL.delete_chat(self.chat)
        if len(list(list_box)) == 0:
            window.new_chat(chat_type='chat')
        if not list_box.get_selected_row() or list_box.get_selected_row() == self:
            list_box.select_row(list_box.get_row_at_index(0))

    def prompt_delete(self):
        dialog.simple(
            parent = self.chat.get_root(),
            heading = _('Delete Chat?'),
            body = _("Are you sure you want to delete '{}'?").format(self.get_name()),
            callback = lambda: self.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

    def duplicate(self):
        new_chat_name = _("Copy of {}".format(self.get_name()))
        new_chat_id = generate_uuid()
        new_chat = window.add_chat(
            chat_name=new_chat_name,
            chat_id=new_chat_id,
            chat_type=self.chat.chat_type,
            mode=1
        )
        SQL.duplicate_chat(self.chat, new_chat)
        new_chat.load_messages()

    def on_export_successful(self, file, result):
        file.replace_contents_finish(result)
        dialog.show_toast(_("Chat exported successfully"), self.get_root())

    def on_export_chat(self, file_dialog, result, temp_path):
        file = file_dialog.save_finish(result)
        if file:
            with open(temp_path, "rb") as db:
                file.replace_contents_async(
                    db.read(),
                    etag=None,
                    make_backup=False,
                    flags=Gio.FileCreateFlags.NONE,
                    cancellable=None,
                    callback=self.on_export_successful
                )

    def export_md(self, obsidian:bool):
        logger.info("Exporting chat (MD)")
        markdown = []
        for message_element in list(self.chat.container):
            if message_element.text and message_element.dt:
                message_author = _('User')
                if message_element.bot:
                    message_author = window.convert_model_name(message_element.model, 0)
                if message_element.system:
                    message_author = _('System')

                markdown.append('### **{}** | {}'.format(message_author, message_element.dt.strftime("%Y/%m/%d %H:%M:%S")))
                markdown.append(message_element.text)
                if message_element.image_c:
                    for file in message_element.image_c.files:
                        markdown.append('![🖼️ {}](data:image/{};base64,{})'.format(file.get_name(), file.get_name().split('.')[1], file.file_content))
                if message_element.attachment_c:
                    emojis = {
                        'plain_text': '📃',
                        'code': '💻',
                        'pdf': '📕',
                        'youtube': '📹',
                        'website': '🌐',
                        'thought': '🧠'
                    }
                    for file in message_element.attachment_c.files:
                        if obsidian:
                            file_block = "> [!quote]- {}\n".format(file.get_name())
                            for line in file.file_content.split("\n"):
                                file_block += "> {}\n".format(line)
                            markdown.append(file_block)
                        else:
                            markdown.append('<details>\n\n<summary>{} {}</summary>\n\n```TXT\n{}\n```\n\n</details>'.format(emojis.get(file.file_type, ''), file.get_name(), file.file_content))
                markdown.append('----')
        markdown.append('Generated from [Alpaca](https://github.com/Jeffser/Alpaca)')
        with open(os.path.join(cache_dir, 'export.md'), 'w') as f:
            f.write('\n\n'.join(markdown))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.md")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.md'): self.on_export_chat(file_dialog, result, temp_path))

    def export_db(self):
        logger.info("Exporting chat (DB)")
        if os.path.isfile(os.path.join(cache_dir, 'export.db')):
            os.remove(os.path.join(cache_dir, 'export.db'))
        SQL.export_db(self.chat, os.path.join(cache_dir, 'export.db'))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.db")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.db'): self.on_export_chat(file_dialog, result, temp_path))

    def export_json(self, include_metadata:bool):
        logger.info("Exporting chat (JSON)")
        with open(os.path.join(cache_dir, 'export.json'), 'w') as f:
            f.write(json.dumps({self.get_name() if include_metadata else 'messages': self.chat.convert_to_json(include_metadata)}, indent=4))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.json")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.json'): self.on_export_chat(file_dialog, result, temp_path))

    def prompt_export(self):
        options = {
            _("Importable (.db)"): self.export_db,
            _("Markdown"): lambda: self.export_md(False),
            _("Markdown (Obsidian Style)"): lambda: self.export_md(True),
            _("JSON"): lambda: self.export_json(False),
            _("JSON (Include Metadata)"): lambda: self.export_json(True)
        }
        dialog.simple_dropdown(
            parent = self.chat.get_root(),
            heading = _("Export Chat"),
            body = _("Select a method to export the chat"),
            callback = lambda option, options=options: options[option](),
            items = options.keys()
        )
