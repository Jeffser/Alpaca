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

class Chat(Gtk.Stack):
    __gtype_name__ = 'AlpacaChat'

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
        self.clamp = Adw.Clamp(
            maximum_size=1000,
            tightening_threshold=800,
            child=self.container
        )
        self.scrolledwindow = Gtk.ScrolledWindow(
            child=self.clamp,
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

        self.busy = False
        self.chat_id = chat_id
        self.row = ChatRow(self)

    def rename(self, new_name:str):
        new_name = generate_numbered_name(new_name, [row.chat.get_name() for row in list(self.row.get_parent())])
        self.row.label.set_label(new_name)
        self.row.label.set_tooltip_text(new_name)
        self.set_name(new_name)
        SQL.insert_or_update_chat(self)

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
        self.stop_message()
        list_box = self.row.get_parent()
        list_box.remove(self.row)
        self.get_parent().remove(self)
        SQL.delete_chat(self)
        if len(list(list_box)) == 0:
            list_box.new_chat()
        if not list_box.get_current_chat() or list_box.get_current_chat() == self:
            list_box.select_row(list_box.get_row_at_index(0))

    def prompt_delete(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Delete Chat?'),
            body = _("Are you sure you want to delete '{}'?").format(self.get_name()),
            callback = lambda: self.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

    def duplicate(self):
        new_chat_name = _("Copy of {}".format(self.get_name()))
        new_chat_id = generate_uuid()
        new_chat = self.row.get_parent().prepend_chat(new_chat_name, new_chat_id)
        SQL.duplicate_chat(self, new_chat)
        new_chat.load_messages()

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

    def on_export_successful(self, file, result):
        file.replace_contents_finish(result)
        window.show_toast(_("Chat exported successfully"), window.main_overlay)

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
        for message_element in list(self.container):
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
        SQL.export_db(self, os.path.join(cache_dir, 'export.db'))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.db")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.db'): self.on_export_chat(file_dialog, result, temp_path))

    def export_json(self, include_metadata:bool):
        logger.info("Exporting chat (JSON)")
        with open(os.path.join(cache_dir, 'export.json'), 'w') as f:
            f.write(json.dumps({self.get_name() if include_metadata else 'messages': self.convert_to_json(include_metadata)}, indent=4))
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
            parent = self.get_root(),
            heading = _("Export Chat"),
            body = _("Select a method to export the chat"),
            callback = lambda option, options=options: options[option](),
            items = options.keys()
        )

    def update_profile_pictures(self):
        for msg in list(self.container):
            msg.update_profile_picture()

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
        container.append(self.label)
        container.append(self.spinner)
        container.append(self.indicator)
        super().__init__(
            css_classes = ['chat_row'],
            height_request = 45,
            child = container
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


class ChatList(Gtk.ListBox):
    __gtype_name__ = 'AlpacaChatList'

    def __init__(self):
        super().__init__(
            selection_mode=1,
            css_classes=["navigation-sidebar"]
        )
        self.connect("row-selected", lambda listbox, row: self.chat_changed(row))

    def get_current_chat(self) -> Chat:
        row = self.get_selected_row()
        if row:
            return self.get_selected_row().chat

    def send_tab_to_top(self, tab:ChatRow):
        self.unselect_all()
        self.remove(tab)
        self.prepend(tab)
        self.select_row(tab)

    def append_chat(self, chat_name:str, chat_id:str) -> Chat:
        chat_name = chat_name.strip()
        if chat_name:
            chat_name = generate_numbered_name(chat_name, [row.chat.get_name() for row in list(self)])
            chat = Chat(
                chat_id=chat_id,
                name=chat_name
            )
            self.append(chat.row)
            window.chat_stack.add_child(chat)
            return chat

    def prepend_chat(self, chat_name:str, chat_id:str) -> Chat:
        chat_name = chat_name.strip()
        if chat_name:
            chat_name = generate_numbered_name(chat_name, [row.chat.get_name() for row in list(self) ])
            chat = Chat(
                chat_id=chat_id,
                name=chat_name
            )
            self.prepend(chat.row)
            chat.set_visible_child_name('welcome-screen')
            window.chat_stack.add_child(chat)
            self.select_row(chat.row)
            return chat

    def new_chat(self, chat_title:str=_("New Chat")):
        chat_title = chat_title.strip()
        if chat_title:
            chat = self.prepend_chat(chat_title, generate_uuid())
            SQL.insert_or_update_chat(chat)
            return chat

    def on_chat_imported(self, file):
        if file:
            if os.path.isfile(os.path.join(cache_dir, 'import.db')):
                os.remove(os.path.join(cache_dir, 'import.db'))
            file.copy(Gio.File.new_for_path(os.path.join(cache_dir, 'import.db')), Gio.FileCopyFlags.OVERWRITE, None, None, None, None)
            for chat in SQL.import_chat(os.path.join(cache_dir, 'import.db'), [tab.chat.get_name() for tab in list(self)]):
                new_chat = self.prepend_chat(chat[1], chat[0])
            window.show_toast(_("Chat imported successfully"), window.main_overlay)

    def find_model_index(self, model_name:str):
        if len(list(window.model_dropdown.get_model())) == 0:
            return None
        detected_models = [i for i, future_row in enumerate(list(window.model_dropdown.get_model())) if future_row.model.get_name() == model_name]
        if len(detected_models) > 0:
            return detected_models[0]

    def chat_changed(self, future_row):
        if future_row:
            current_row = next((t for t in list(self) if t.chat == window.chat_stack.get_visible_child()), future_row)
            if list(self).index(future_row) != list(self).index(current_row) or future_row.chat.get_visible_child_name() != 'content':
                # Empty Search
                if window.searchentry_messages.get_text() != '':
                    window.searchentry_messages.set_text('')
                    window.message_search_changed(window.searchentry_messages, window.chat_stack.get_visible_child())
                window.message_searchbar.set_search_mode(False)

                load_chat_thread = None
                # Load future_row if not loaded already
                if len(list(future_row.chat.container)) == 0:
                    load_chat_thread = threading.Thread(target=future_row.chat.load_messages)
                    load_chat_thread.start()

                # Unload current_row
                if not current_row.chat.busy and current_row.chat.get_visible_child_name() == 'content' and len(list(current_row.chat.container)) > 0:
                    threading.Thread(target=current_row.chat.unload_messages).start()

                # Select transition type and change chat
                window.chat_stack.set_transition_type(4 if list(self).index(future_row) > list(self).index(current_row) else 5)
                window.chat_stack.set_visible_child(future_row.chat)

                # Sync stop/send button to chat's state
                window.switch_send_stop_button(not future_row.chat.busy)
                if load_chat_thread:
                    load_chat_thread.join()
                # Select the correct model for the chat
                model_to_use_index = self.find_model_index(window.get_current_instance().get_default_model())
                if len(list(future_row.chat.container)) > 0:
                    message_model = self.find_model_index(list(future_row.chat.container)[-1].get_model())
                    if message_model:
                        model_to_use_index = message_model

                if model_to_use_index is None:
                    model_to_use_index = 0

                window.model_dropdown.set_selected(model_to_use_index)

                # If it has the "new message" indicator, hide it
                if future_row.indicator.get_visible():
                    future_row.indicator.set_visible(False)
