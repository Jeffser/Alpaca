#chat_widget.py
"""
Handles the chat widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
import logging, os, datetime, shutil, random, json, threading
from ..internal import data_dir, cache_dir
from .message_widget import message
from . import model_manager_widget

logger = logging.getLogger(__name__)

window = None

possible_prompts = [
    "What can you do?",
    "Give me a pancake recipe",
    "Why is the sky blue?",
    "Can you tell me a joke?",
    "Give me a healthy breakfast recipe",
    "How to make a pizza",
    "Can you write a poem?",
    "Can you write a story?",
    "What is GNU-Linux?",
    "Which is the best Linux distro?",
    "Why is Pluto not a planet?",
    "What is a black-hole?",
    "Tell me how to stay fit",
    "Write a conversation between sun and Earth",
    "Why is the grass green?",
    "Write an Haïku about AI",
    "What is the meaning of life?",
    "Explain quantum physics in simple terms",
    "Explain the theory of relativity",
    "Explain how photosynthesis works",
    "Recommend a film about nature",
    "What is nostalgia?"
]

class chat(Gtk.Stack):
    __gtype_name__ = 'AlpacaChat'

    def __init__(self, name:str, chat_id=str, quick_chat:bool=False):
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
        self.add_named(self.scrolledwindow, 'content')
        button_container = Gtk.Box(
            orientation=1,
            spacing=10,
            halign=3
        )
        if len(list(window.local_model_flowbox)) > 0:
            for prompt in random.sample(possible_prompts, 3):
                prompt_button = Gtk.Button(
                    label=prompt,
                    tooltip_text=_("Send prompt: '{}'").format(prompt)
                )
                prompt_button.connect('clicked', lambda *_, prompt=prompt : self.send_sample_prompt(prompt))
                button_container.append(prompt_button)
        else:
            button = Gtk.Button(
                label=_("Open Model Manager"),
                tooltip_text=_("Open Model Manager"),
                css_classes=["suggested-action", "pill"]
            )
            button.set_action_name('app.model_manager')
            button_container.append(button)

        self.welcome_screen = Adw.StatusPage(
            icon_name="com.jeffser.Alpaca",
            title="Alpaca",
            description=_("Try one of these prompts") if len(list(window.local_model_flowbox)) > 0 else _("It looks like you don't have any models downloaded yet. Download models to get started!"),
            child=button_container,
            vexpand=True
        )
        list(self.welcome_screen)[0].add_css_class('undershoot-bottom')
        self.add_named(self.welcome_screen, 'welcome-screen')

        self.messages = {}
        self.welcome_screen = None
        self.regenerate_button = None
        self.busy = False
        self.chat_id = chat_id
        self.quick_chat = quick_chat
        #self.get_vadjustment().connect('notify::page-size', lambda va, *_: va.set_value(va.get_upper() - va.get_page_size()) if va.get_value() == 0 else None)
        ##TODO Figure out how to do this with the search thing

    def stop_message(self):
        self.busy = False
        window.switch_send_stop_button(True)

    def clear_chat(self):
        if self.busy:
            self.stop_message()
        self.messages = {}
        self.stop_message()
        for widget in list(self.container):
            self.container.remove(widget)
        self.set_visible_child_name('welcome-screen')

    def add_message(self, message_id:str, dt:datetime.datetime, model:str=None, system:bool=None):
        msg = message(message_id, dt, model, system)
        self.messages[message_id] = msg
        self.container.append(msg)
        return msg

    def send_sample_prompt(self, prompt):
        buffer = window.message_text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), prompt, len(prompt.encode('utf-8')))
        window.send_message()

    def load_chat_messages(self):
        messages = window.sql_instance.get_messages(self)
        for message in messages:
            message_element = self.add_message(message[0], datetime.datetime.strptime(message[3] + (":00" if message[3].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S'), message[2] if message[1] == 'assistant' else None, message[1] == 'system')
            attachments = window.sql_instance.get_attachments(message_element)
            for attachment in attachments:
                message_element.add_attachment(attachment[2], attachment[1], attachment[3])
            message_element.set_text(message[4])
        self.set_visible_child_name('content' if len(messages) > 0 else 'welcome-screen')

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
        for message_id, message_element in self.messages.items():
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
        window.sql_instance.export_db(self, os.path.join(cache_dir, 'export.db'))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.db")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.db'): self.on_export_chat(file_dialog, result, temp_path))

    def export_json(self, include_metadata:bool):
        logger.info("Exporting chat (JSON)")
        with open(os.path.join(cache_dir, 'export.json'), 'w') as f:
            f.write(json.dumps({self.get_name() if include_metadata else 'messages': self.convert_to_ollama(include_metadata)}, indent=4))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.json")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.json'): self.on_export_chat(file_dialog, result, temp_path))

    def convert_to_ollama(self, include_metadata:bool=False) -> dict:
        messages = []
        for message in self.messages.values():
            if message.text and message.dt:
                message_role = 'user'
                if message.bot:
                    message_role = 'assistant'
                if message.system:
                    message_role = 'system'
                message_data = {
                    'role': message_role,
                    'content': []
                }
                raw_text = ''
                if message.image_c and len(message.image_c.files) > 0:
                    for image in message.image_c.files:
                        message_data['content'].append({
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/jpeg;base64,{image.file_content}'
                            }
                        })
                if message.attachment_c and len(message.attachment_c.files) > 0:
                    for attachment in message.attachment_c.files:
                        message_data['content'].append({
                            'type': 'text',
                            'text': '```{} ({})\n{}\n```\n\n'.format(attachment.get_name(), attachment.file_type, attachment.file_content)
                        })
                message_data['content'].append({
                    'type': 'text',
                    'text': message.text
                })
                if include_metadata:
                    message_data['date'] = message.dt.strftime("%Y/%m/%d %H:%M:%S")
                    message_data['model'] = message.model
                messages.append(message_data)
        return messages

    def show_regenerate_button(self, msg:message):
        if self.regenerate_button:
            self.remove(self.regenerate_button)
        self.regenerate_button = Gtk.Button(
            child=Adw.ButtonContent(
                icon_name='update-symbolic',
                label=_('Regenerate Response')
            ),
            css_classes=["suggested-action"],
            halign=3
        )
        self.regenerate_button.connect('clicked', lambda *_: msg.footer.popup.regenerate_message())
        self.container.append(self.regenerate_button)

class chat_tab(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaChatTab'

    def __init__(self, chat_window:chat):
        self.chat_window=chat_window
        self.spinner = Adw.Spinner(visible=False)
        self.label = Gtk.Label(
            label=self.chat_window.get_name(),
            tooltip_text=self.chat_window.get_name(),
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
            orientation=0,
            spacing=5
        )
        container.append(self.label)
        container.append(self.spinner)
        container.append(self.indicator)
        super().__init__(
            css_classes = ["chat_row"],
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
        chat_row = gesture.get_widget()
        popover = Gtk.PopoverMenu(
            menu_model=window.chat_right_click_menu,
            has_arrow=False,
            halign=1,
            height_request=155
        )
        window.selected_chat_row = chat_row
        position = Gdk.Rectangle()
        position.x = x
        position.y = y
        popover.set_parent(chat_row.get_child())
        popover.set_pointing_to(position)
        popover.popup()

class chat_list(Gtk.ListBox):
    __gtype_name__ = 'AlpacaChatList'

    def __init__(self):
        super().__init__(
            selection_mode=1,
            css_classes=["navigation-sidebar"]
        )
        self.connect("row-selected", lambda listbox, row: self.chat_changed(row, False))
        self.tab_list = []

    def update_profile_pictures(self):
        for tab in self.tab_list:
            for message in tab.chat_window.messages.values():
                message.update_profile_picture()

    def update_welcome_screens(self):
        for tab in self.tab_list:
            if tab.chat_window.welcome_screen:
                tab.chat_window.set_visible_child_name('content' if len(tab.chat_window.messages) > 0 else 'welcome-screen')

    def get_tab_by_name(self, chat_name:str) -> chat_tab:
        for tab in self.tab_list:
            if tab.chat_window.get_name() == chat_name:
                return tab

    def get_chat_by_name(self, chat_name:str) -> chat:
        tab = self.get_tab_by_name(chat_name)
        if tab:
            return tab.chat_window

    def get_current_chat(self) -> chat:
        row = self.get_selected_row()
        if row:
            return self.get_selected_row().chat_window

    def send_tab_to_top(self, tab:chat_tab):
        self.unselect_all()
        self.tab_list.remove(tab)
        self.tab_list.insert(0, tab)
        self.remove(tab)
        self.prepend(tab)
        self.select_row(tab)

    def append_chat(self, chat_name:str, chat_id:str) -> chat:
        chat_name = chat_name.strip()
        if chat_name:
            chat_name = window.generate_numbered_name(chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
            chat_window = chat(chat_name, chat_id)
            tab = chat_tab(chat_window)
            self.append(tab)
            self.tab_list.append(tab)
            window.chat_stack.add_child(chat_window)
            return chat_window

    def prepend_chat(self, chat_name:str, chat_id:str) -> chat:
        chat_name = chat_name.strip()
        if chat_name:
            chat_name = window.generate_numbered_name(chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
            chat_window = chat(chat_name, chat_id)
            tab = chat_tab(chat_window)
            self.prepend(tab)
            self.tab_list.insert(0, tab)
            chat_window.set_visible_child_name('welcome-screen')
            window.chat_stack.add_child(chat_window)
            window.chat_list_box.select_row(tab)
            return chat_window

    def new_chat(self, chat_title:str=_("New Chat")):
        chat_title = chat_title.strip()
        if chat_title:
            chat_window = self.prepend_chat(chat_title, window.generate_uuid())
            window.sql_instance.insert_or_update_chat(chat_window)
            return chat_window

    def delete_chat(self, chat_name:str):
        chat_tab = None
        for c in self.tab_list:
            if c.chat_window.get_name() == chat_name:
                chat_tab = c
        if chat_tab:
            chat_tab.chat_window.stop_message()
            chat_id = chat_tab.chat_window.chat_id
            window.sql_instance.delete_chat(chat_tab.chat_window)
            window.chat_stack.remove(chat_tab.chat_window)
            self.tab_list.remove(chat_tab)
            self.remove(chat_tab)
            if len(self.tab_list) == 0:
                self.new_chat()
            if not self.get_current_chat() or self.get_current_chat() == chat_tab.chat_window:
                self.select_row(self.get_row_at_index(0))

    def rename_chat(self, old_chat_name:str, new_chat_name:str):
        new_chat_name = new_chat_name.strip()
        if not new_chat_name or new_chat_name == old_chat_name:
            return
        tab = self.get_tab_by_name(old_chat_name)
        if tab:
            new_chat_name = window.generate_numbered_name(new_chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
            tab.label.set_label(new_chat_name)
            tab.label.set_tooltip_text(new_chat_name)
            tab.chat_window.set_name(new_chat_name)
            window.sql_instance.insert_or_update_chat(tab.chat_window)

    def duplicate_chat(self, chat_name:str):
        old_chat_window = self.get_chat_by_name(chat_name)
        new_chat_name = window.generate_numbered_name(_("Copy of {}").format(chat_name), [tab.chat_window.get_name() for tab in self.tab_list])
        new_chat_id = window.generate_uuid()
        new_chat = self.prepend_chat(new_chat_name, new_chat_id)
        window.sql_instance.duplicate_chat(old_chat_window, new_chat)
        threading.Thread(target=new_chat.load_chat_messages).start()

    def on_chat_imported(self, file_dialog, result):
        file = file_dialog.open_finish(result)
        if file:
            if os.path.isfile(os.path.join(cache_dir, 'import.db')):
                os.remove(os.path.join(cache_dir, 'import.db'))
            file.copy(Gio.File.new_for_path(os.path.join(cache_dir, 'import.db')), Gio.FileCopyFlags.OVERWRITE, None, None, None, None)
            for chat in window.sql_instance.import_chat(os.path.join(cache_dir, 'import.db'), [tab.chat_window.get_name() for tab in self.tab_list]):
                new_chat = self.prepend_chat(chat[1], chat[0])
                threading.Thread(target=new_chat.load_chat_messages).start()
        window.show_toast(_("Chat imported successfully"), window.main_overlay)

    def import_chat(self):
        logger.info("Importing chat")
        file_dialog = Gtk.FileDialog(default_filter=window.file_filter_db)
        file_dialog.open(window, None, self.on_chat_imported)

    def chat_changed(self, row, force:bool):
        if row:
            current_tab_i = next((i for i, t in enumerate(self.tab_list) if t.chat_window == window.chat_stack.get_visible_child()), -1)
            if self.tab_list.index(row) != current_tab_i or force:
                if window.searchentry_messages.get_text() != '':
                    window.searchentry_messages.set_text('')
                    window.message_search_changed(window.searchentry_messages, window.chat_stack.get_visible_child())
                window.message_searchbar.set_search_mode(False)
                window.chat_stack.set_transition_type(4 if self.tab_list.index(row) > current_tab_i else 5)
                window.chat_stack.set_visible_child(row.chat_window)
                window.switch_send_stop_button(not row.chat_window.busy)

                model_to_use = window.get_current_instance().get_default_model()
                if len(row.chat_window.messages) > 0:
                    model_to_use = row.chat_window.messages[list(row.chat_window.messages)[-1]].model
                detected_models = [i for i, row in enumerate(list(window.model_dropdown.get_model())) if row.model.get_name() == model_to_use]
                if len(detected_models) > 0:
                    window.model_dropdown.set_selected(detected_models[0])

                if row.indicator.get_visible():
                    row.indicator.set_visible(False)
