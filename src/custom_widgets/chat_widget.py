#chat_widget.py
"""
Handles the chat widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk
import logging, os, datetime, re, shutil, random, tempfile, tarfile, json
from ..internal import config_dir, data_dir, cache_dir, source_dir
from .message_widget import message

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

class chat(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaChat'

    def __init__(self, name:str):
        self.container = Gtk.Box(
            orientation=1,
            hexpand=True,
            vexpand=True,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12
        )
        self.clamp = Adw.Clamp(
            maximum_size=1000,
            tightening_threshold=800,
            child=self.container
        )
        super().__init__(
            child=self.clamp,
            propagate_natural_height=True,
            kinetic_scrolling=True,
            vexpand=True,
            hexpand=True,
            css_classes=["undershoot-bottom"],
            name=name
        )
        self.messages = {}
        self.welcome_screen = None
        self.regenerate_button = None
        self.busy = False

    def stop_message(self):
        self.busy = False
        window.switch_send_stop_button(True)

    def clear_chat(self):
        if self.busy:
            self.stop_message()
        self.message = {}
        self.stop_message()
        for widget in list(self.container):
            self.container.remove(widget)

    def add_message(self, message_id:str, model:str=None):
        msg = message(message_id, model)
        self.messages[message_id] = msg
        self.container.append(msg)

    def send_sample_prompt(self, prompt):
        buffer = window.message_text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), prompt, len(prompt.encode('utf-8')))
        window.send_message()

    def show_welcome_screen(self, show_prompts:bool):
        if self.welcome_screen:
            self.container.remove(self.welcome_screen)
            self.welcome_screen = None
        self.clear_chat()
        button_container = Gtk.Box(
            orientation=1,
            spacing=10,
            halign=3
        )
        if show_prompts:
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
            button.connect('clicked', lambda *_ : window.manage_models_dialog.present(window))
            button_container.append(button)

        self.welcome_screen = Adw.StatusPage(
            icon_name="com.jeffser.Alpaca",
            title="Alpaca",
            description=_("Try one of these prompts") if show_prompts else _("It looks like you don't have any models downloaded yet. Download models to get started!"),
            child=button_container,
            vexpand=True
        )

        self.container.append(self.welcome_screen)

    def load_chat_messages(self, messages:dict):
        if len(messages.keys()) > 0:
            if self.welcome_screen:
                self.container.remove(self.welcome_screen)
                self.welcome_screen = None
            for message_id, message_data in messages.items():
                if message_data['content']:
                    self.add_message(message_id, message_data['model'] if message_data['role'] == 'assistant' else None)
                    message_element = self.messages[message_id]
                    if 'images' in message_data:
                        images=[]
                        for image in message_data['images']:
                            images.append(os.path.join(data_dir, "chats", self.get_name(), message_id, image))
                        message_element.add_images(images)
                    if 'files' in message_data:
                        files={}
                        for file_name, file_type in message_data['files'].items():
                            files[os.path.join(data_dir, "chats", self.get_name(), message_id, file_name)] = file_type
                        message_element.add_attachments(files)
                    message_element.set_text(message_data['content'])
                    message_element.add_footer(datetime.datetime.strptime(message_data['date'] + (":00" if message_data['date'].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S'))
        else:
            self.show_welcome_screen(len(window.model_selector.get_model_list()) > 0)

    def messages_to_dict(self) -> dict:
        messages_dict = {}
        for message_id, message_element in self.messages.items():
            if message_element.text and message_element.dt:
                messages_dict[message_id] = {
                    'role': 'assistant' if message_element.bot else 'user',
                    'model': message_element.model,
                    'date': message_element.dt.strftime("%Y/%m/%d %H:%M:%S"),
                    'content': message_element.text
                }

                if message_element.image_c:
                    images = []
                    for file in message_element.image_c.files:
                        images.append(file.image_name)
                    messages_dict[message_id]['images'] = images

                if message_element.attachment_c:
                    files = {}
                    for file in message_element.attachment_c.files:
                        files[file.file_name] = file.file_type
                    messages_dict[message_id]['files'] = files
        return messages_dict

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
        self.regenerate_button.connect('clicked', lambda *_: msg.action_buttons.regenerate_message())
        self.container.append(self.regenerate_button)

class chat_tab(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaChatTab'

    def __init__(self, chat_window:chat):
        self.chat_window=chat_window
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
        super().__init__(
            css_classes = ["chat_row"],
            height_request = 45,
            child = self.label
        )

        self.gesture = Gtk.GestureClick(button=3)
        self.gesture.connect("released", window.chat_click_handler)
        self.add_controller(self.gesture)

class chat_list(Gtk.ListBox):
    __gtype_name__ = 'AlpacaChatList'

    def __init__(self):
        super().__init__(
            selection_mode=1,
            css_classes=["navigation-sidebar"]
        )
        self.connect("row-selected", lambda listbox, row: self.chat_changed(row))
        self.tab_list = []

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

    def append_chat(self, chat_name:str) -> chat:
        chat_name = window.generate_numbered_name(chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
        chat_window = chat(chat_name)
        tab = chat_tab(chat_window)
        self.append(tab)
        self.tab_list.append(tab)
        window.chat_stack.add_child(chat_window)
        return chat_window

    def prepend_chat(self, chat_name:str) -> chat:
        chat_name = window.generate_numbered_name(chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
        chat_window = chat(chat_name)
        tab = chat_tab(chat_window)
        self.prepend(tab)
        self.tab_list.insert(0, tab)
        chat_window.show_welcome_screen(len(window.model_selector.get_model_list()) > 0)
        window.chat_stack.add_child(chat_window)
        window.chat_list_box.select_row(tab)
        return chat_window

    def new_chat(self):
        window.save_history(self.prepend_chat(_("New Chat")))

    def delete_chat(self, chat_name:str):
        chat_tab = None
        for c in self.tab_list:
            if c.chat_window.get_name() == chat_name:
                chat_tab = c
        if chat_tab:
            chat_tab.chat_window.stop_message()
            window.chat_stack.remove(chat_tab.chat_window)
            self.tab_list.remove(chat_tab)
            self.remove(chat_tab)
            if os.path.exists(os.path.join(data_dir, "chats", chat_name)):
                shutil.rmtree(os.path.join(data_dir, "chats", chat_name))
            if len(self.tab_list) == 0:
                self.new_chat()
            if not self.get_current_chat() or self.get_current_chat() == chat_tab.chat_window:
                self.select_row(self.get_row_at_index(0))
        window.save_history()

    def rename_chat(self, old_chat_name:str, new_chat_name:str):
        tab = self.get_tab_by_name(old_chat_name)
        if tab:
            new_chat_name = window.generate_numbered_name(new_chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
            tab.get_child().set_label(new_chat_name)
            tab.get_child().set_tooltip_text(new_chat_name)
            tab.chat_window.set_name(new_chat_name)

    def duplicate_chat(self, chat_name:str):
        new_chat_name = window.generate_numbered_name(_("Copy of {}").format(chat_name), [tab.chat_window.get_name() for tab in self.tab_list])
        try:
            shutil.copytree(os.path.join(data_dir, "chats", chat_name), os.path.join(data_dir, "chats", new_chat_name))
        except Exception as e:
            logger.error(e)
        self.prepend_chat(new_chat_name)
        self.get_tab_by_name(new_chat_name).chat_window.load_chat_messages(self.get_tab_by_name(chat_name).chat_window.messages_to_dict())

    def on_replace_contents(self, file, result):
        file.replace_contents_finish(result)
        window.show_toast(_("Chat exported successfully"), window.main_overlay)

    def on_export_chat(self, file_dialog, result, chat_name):
        file = file_dialog.save_finish(result)
        if not file:
            return
        json_data = json.dumps({chat_name: self.get_chat_by_name(chat_name).messages_to_dict()}, indent=4).encode("UTF-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = os.path.join(temp_dir, "data.json")
            with open(json_path, "wb") as json_file:
                json_file.write(json_data)

            tar_path = os.path.join(temp_dir, chat_name)
            with tarfile.open(tar_path, "w") as tar:
                tar.add(json_path, arcname="data.json")
                directory = os.path.join(data_dir, "chats", chat_name)
                if os.path.exists(directory) and os.path.isdir(directory):
                    tar.add(directory, arcname=os.path.basename(directory))

            with open(tar_path, "rb") as tar:
                tar_content = tar.read()

            file.replace_contents_async(
                tar_content,
                etag=None,
                make_backup=False,
                flags=Gio.FileCreateFlags.NONE,
                cancellable=None,
                callback=self.on_replace_contents
            )

    def export_chat(self, chat_name:str):
        logger.info("Exporting chat")
        file_dialog = Gtk.FileDialog(initial_name=f"{chat_name}.tar")
        file_dialog.save(parent=window, cancellable=None, callback=lambda file_dialog, result, chat_name=chat_name: self.on_export_chat(file_dialog, result, chat_name))

    def on_chat_imported(self, file_dialog, result):
        file = file_dialog.open_finish(result)
        if not file:
            return
        stream = file.read(None)
        data_stream = Gio.DataInputStream.new(stream)
        tar_content = data_stream.read_bytes(1024 * 1024, None)

        with tempfile.TemporaryDirectory() as temp_dir:
            tar_filename = os.path.join(temp_dir, "imported_chat.tar")

            with open(tar_filename, "wb") as tar_file:
                tar_file.write(tar_content.get_data())

            with tarfile.open(tar_filename, "r") as tar:
                tar.extractall(path=temp_dir)
                chat_name = None
                chat_content = None
                for member in tar.getmembers():
                    if member.name == "data.json":
                        json_filepath = os.path.join(temp_dir, member.name)
                        with open(json_filepath, "r", encoding="utf-8") as json_file:
                            data = json.load(json_file)
                        for chat_name, chat_content in data.items():
                            new_chat_name = window.generate_numbered_name(chat_name, [tab.chat_window.get_name() for tab in self.tab_list])
                            src_path = os.path.join(temp_dir, chat_name)
                            dest_path = os.path.join(data_dir, "chats", new_chat_name)
                            if os.path.exists(src_path) and os.path.isdir(src_path) and not os.path.exists(dest_path):
                                shutil.copytree(src_path, dest_path)

                            self.prepend_chat(new_chat_name)
                            self.get_chat_by_name(new_chat_name).load_chat_messages(chat_content['messages'])
        window.show_toast(_("Chat imported successfully"), window.main_overlay)

    def import_chat(self):
        logger.info("Importing chat")
        file_dialog = Gtk.FileDialog(default_filter=window.file_filter_tar)
        file_dialog.open(window, None, self.on_chat_imported)

    def chat_changed(self, row):
        if row:
            current_tab_i = next((i for i, t in enumerate(self.tab_list) if t.chat_window == window.chat_stack.get_visible_child()), -1)
            if self.tab_list.index(row) != current_tab_i:
                window.chat_stack.set_transition_type(4 if self.tab_list.index(row) > current_tab_i else 5)
                window.chat_stack.set_visible_child(row.chat_window)
                window.switch_send_stop_button(not row.chat_window.busy)
                if len(row.chat_window.messages) > 0:
                    last_model_used = row.chat_window.messages[list(row.chat_window.messages)[-1]].model
                    window.model_selector.change_model(last_model_used)

