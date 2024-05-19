# window.py
#
# Copyright 2024 Unknown
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import gi
gi.require_version('GtkSource', '5')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, GdkPixbuf
import json, requests, threading, os, re, base64, sys
from io import BytesIO
from PIL import Image
from datetime import datetime
from .connection_handler import simple_get, simple_delete, stream_post, stream_post_fake
from .available_models import available_models

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    config_dir = os.path.join(os.getenv("XDG_CONFIG_HOME"), "/", os.path.expanduser("~/.var/app/com.jeffser.Alpaca/config"))
    __gtype_name__ = 'AlpacaWindow'
    #Variables
    ollama_url = None
    local_models = []
    pulling_models = {}
    chats = {"chats": {"New Chat": {"messages": []}}, "selected_chat": "New Chat"}
    attached_image = {"path": None, "base64": None}
    first_time_setup = False

    #Elements
    shortcut_window : Gtk.ShortcutsWindow  = Gtk.Template.Child()
    bot_message : Gtk.TextBuffer = None
    bot_message_box : Gtk.Box = None
    bot_message_view : Gtk.TextView = None
    connection_dialog = Gtk.Template.Child()
    connection_carousel = Gtk.Template.Child()
    connection_previous_button = Gtk.Template.Child()
    connection_next_button = Gtk.Template.Child()
    connection_url_entry = Gtk.Template.Child()
    main_overlay = Gtk.Template.Child()
    manage_models_overlay = Gtk.Template.Child()
    connection_overlay = Gtk.Template.Child()
    chat_container = Gtk.Template.Child()
    chat_window = Gtk.Template.Child()
    message_text_view = Gtk.Template.Child()
    send_button = Gtk.Template.Child()
    image_button = Gtk.Template.Child()
    file_filter_image = Gtk.Template.Child()
    model_drop_down = Gtk.Template.Child()
    model_string_list = Gtk.Template.Child()

    manage_models_button = Gtk.Template.Child()
    manage_models_dialog = Gtk.Template.Child()
    pulling_model_list_box = Gtk.Template.Child()
    local_model_list_box = Gtk.Template.Child()
    available_model_list_box = Gtk.Template.Child()

    chat_list_box = Gtk.Template.Child()
    add_chat_button = Gtk.Template.Child()

    loading_spinner = None

    toast_messages = {
        "error": [
            "An error occurred",
            "Failed to connect to server",
            "Could not list local models",
            "Could not delete model",
            "Could not pull model",
            "Cannot open image",
            "Cannot delete chat because it's the only one left"
        ],
        "info": [
            "Please select a model before chatting",
            "Chat cannot be cleared while receiving a message"
        ],
        "good": [
            "Model deleted successfully",
            "Model pulled successfully"
        ]
    }

    def show_toast(self, message_type:str, message_id:int, overlay):
        if message_type not in self.toast_messages or message_id > len(self.toast_messages[message_type] or message_id < 0):
            message_type = "error"
            message_id = 0
        toast = Adw.Toast(
            title=self.toast_messages[message_type][message_id],
            timeout=2
        )
        overlay.add_toast(toast)

    def show_notification(self, title:str, body:str, only_when_focus:bool, icon:Gio.ThemedIcon=None):
        if only_when_focus==False or self.is_active()==False:
            notification = Gio.Notification.new(title)
            notification.set_body(body)
            if icon: notification.set_icon(icon)
            self.get_application().send_notification(None, notification)

    def show_message(self, msg:str, bot:bool, footer:str=None, image_base64:str=None):
        message_text = Gtk.TextView(
            editable=False,
            focusable=True,
            wrap_mode= Gtk.WrapMode.WORD,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            hexpand=True,
            css_classes=["flat"]
        )
        message_buffer = message_text.get_buffer()
        message_buffer.insert(message_buffer.get_end_iter(), msg)
        if footer is not None: message_buffer.insert_markup(message_buffer.get_end_iter(), footer, len(footer))

        message_box = Gtk.Box(
            orientation=1,
            css_classes=[None if bot else "card"]
        )
        message_text.set_valign(Gtk.Align.CENTER)
        self.chat_container.append(message_box)

        if image_base64 is not None:
            image_data = base64.b64decode(image_base64)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()

            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)

            image = Gtk.Image.new_from_paintable(texture)
            image.set_size_request(240, 240)
            image.set_margin_top(10)
            image.set_margin_start(10)
            image.set_margin_end(10)
            image.set_hexpand(False)
            image.set_css_classes(["flat"])
            message_box.append(image)

        message_box.append(message_text)

        if bot:
            self.bot_message = message_buffer
            self.bot_message_view = message_text
            self.bot_message_box = message_box

    def verify_if_image_can_be_used(self, pspec=None, user_data=None):
        if self.model_drop_down.get_selected_item() == None: return True
        selected = self.model_drop_down.get_selected_item().get_string().split(":")[0]
        if selected in ['llava']:
            self.image_button.set_sensitive(True)
            return True
        else:
            self.image_button.set_sensitive(False)
            self.image_button.set_css_classes([])
            self.image_button.get_child().set_icon_name("image-x-generic-symbolic")
            self.attached_image = {"path": None, "base64": None}
            return False

    def update_list_local_models(self):
        self.local_models = []
        response = simple_get(self.ollama_url + "/api/tags")
        for i in range(self.model_string_list.get_n_items() -1, -1, -1):
            self.model_string_list.remove(i)
        if response['status'] == 'ok':
            self.local_model_list_box.remove_all()
            for model in json.loads(response['text'])['models']:
                model_row = Adw.ActionRow(
                    title = model["name"].split(":")[0],
                    subtitle = model["name"].split(":")[1]
                )
                button = Gtk.Button(
                    icon_name = "user-trash-symbolic",
                    vexpand = False,
                    valign = 3,
                    css_classes = ["error"]
                )
                button.connect("clicked", lambda button=button, model_name=model["name"]: self.model_delete_button_activate(model_name))
                model_row.add_suffix(button)
                self.local_model_list_box.append(model_row)

                self.model_string_list.append(model["name"])
                self.local_models.append(model["name"])
            self.model_drop_down.set_selected(0)
            self.verify_if_image_can_be_used()
            return
        else:
            self.show_connection_dialog(True)
            self.show_toast("error", 2, self.connection_overlay)

    def verify_connection(self):
        response = simple_get(self.ollama_url)
        if response['status'] == 'ok':
            if "Ollama is running" in response['text']:
                with open(os.path.join(self.config_dir, "server.conf"), "w+") as f: f.write(self.ollama_url)
                #self.message_text_view.grab_focus_without_selecting()
                self.update_list_local_models()
                return True
        return False

    def add_code_blocks(self):
        text = self.bot_message.get_text(self.bot_message.get_start_iter(), self.bot_message.get_end_iter(), True)
        GLib.idle_add(self.bot_message_view.get_parent().remove, self.bot_message_view)
        # Define a regular expression pattern to match code blocks
        code_block_pattern = re.compile(r'```(\w+)\n(.*?)\n```', re.DOTALL)
        parts = []
        pos = 0
        for match in code_block_pattern.finditer(text):
            start, end = match.span()
            if pos < start:
                normal_text = text[pos:start]
                parts.append({"type": "normal", "text": normal_text.strip()})
            language = match.group(1)
            code_text = match.group(2)
            parts.append({"type": "code", "text": code_text, "language": language})
            pos = end
        # Extract any remaining normal text after the last code block
        if pos < len(text):
            normal_text = text[pos:]
            if normal_text.strip():
                parts.append({"type": "normal", "text": normal_text.strip()})
        bold_pattern = re.compile(r'\*\*(.*?)\*\*') #"**text**"
        code_pattern = re.compile(r'`(.*?)`') #"`text`"
        h1_pattern = re.compile(r'^#\s(.*)$') #"# text"
        h2_pattern = re.compile(r'^##\s(.*)$') #"## text"
        markup_pattern = re.compile(r'<(b|u|tt|span.*)>(.*?)<\/(b|u|tt|span)>') #heh butt span, I'm so funny
        for part in parts:
            if part['type'] == 'normal':
                message_text = Gtk.TextView(
                    editable=False,
                    focusable=True,
                    wrap_mode= Gtk.WrapMode.WORD,
                    margin_top=12,
                    margin_bottom=12,
                    margin_start=12,
                    margin_end=12,
                    hexpand=True,
                    css_classes=["flat"]
                )
                message_buffer = message_text.get_buffer()

                footer = None
                if part['text'].split("\n")[-1] == parts[-1]['text'].split("\n")[-1]:
                    footer = "\n\n<small>" + part['text'].split('\n')[-1] + "</small>"
                    part['text'] = '\n'.join(part['text'].split("\n")[:-1])

                part['text'] = part['text'].replace("\n* ", "\n• ")
                #part['text'] = GLib.markup_escape_text(part['text'])
                part['text'] = code_pattern.sub(r'<tt>\1</tt>', part['text'])
                part['text'] = bold_pattern.sub(r'<b>\1</b>', part['text'])
                part['text'] = h1_pattern.sub(r'<span size="x-large">\1</span>', part['text'])
                part['text'] = h2_pattern.sub(r'<span size="large">\1</span>', part['text'])

                position = 0
                for match in markup_pattern.finditer(part['text']):
                    start, end = match.span()
                    if position < start:
                        message_buffer.insert(message_buffer.get_end_iter(), part['text'][position:start])
                    message_buffer.insert_markup(message_buffer.get_end_iter(), match.group(0), len(match.group(0)))
                    position = end

                if position < len(part['text']):
                    message_buffer.insert(message_buffer.get_end_iter(), part['text'][position:])

                if footer: message_buffer.insert_markup(message_buffer.get_end_iter(), footer, len(footer))

                self.bot_message_box.append(message_text)
            else:
                language = GtkSource.LanguageManager.get_default().get_language(part['language'])
                buffer = GtkSource.Buffer.new_with_language(language)
                buffer.set_text(part['text'])
                buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('classic-dark'))
                source_view = GtkSource.View(
                    auto_indent=True, indent_width=4, buffer=buffer, show_line_numbers=True
                )
                source_view.set_editable(False)
                source_view.get_style_context().add_class("card")
                self.bot_message_box.append(source_view)
        self.bot_message = None
        self.bot_message_box = None

    def update_bot_message(self, data):
        vadjustment = self.chat_window.get_vadjustment()
        if vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
            GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
        if data['done']:
            formated_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")
            text = f"\n<small>{data['model']}\t|\t{formated_datetime}</small>"
            GLib.idle_add(self.bot_message.insert_markup, self.bot_message.get_end_iter(), text, len(text))
            self.save_history()
        else:
            if self.chats["chats"][self.chats["selected_chat"]]["messages"][-1]['role'] == "user":
                GLib.idle_add(self.chat_container.remove, self.loading_spinner)
                self.loading_spinner = None
                self.chats["chats"][self.chats["selected_chat"]]["messages"].append({
                    "role": "assistant",
                    "model": data['model'],
                    "date": datetime.now().strftime("%Y/%m/%d %H:%M"),
                    "content": ''
                })
            GLib.idle_add(self.bot_message.insert, self.bot_message.get_end_iter(), data['message']['content'])
            self.chats["chats"][self.chats["selected_chat"]]["messages"][-1]['content'] += data['message']['content']

    def run_message(self, messages, model):
        response = stream_post(f"{self.ollama_url}/api/chat", data=json.dumps({"model": model, "messages": messages}), callback=self.update_bot_message)
        GLib.idle_add(self.add_code_blocks)
        GLib.idle_add(self.send_button.set_sensitive, True)
        GLib.idle_add(self.image_button.set_sensitive, True)
        GLib.idle_add(self.image_button.set_css_classes, [])
        GLib.idle_add(self.image_button.get_child().set_icon_name, "image-x-generic-symbolic")
        self.attached_image = {"path": None, "base64": None}
        GLib.idle_add(self.message_text_view.set_sensitive,  True)
        if response['status'] == 'error':
            GLib.idle_add(self.show_toast, 'error', 1, self.connection_overlay)
            GLib.idle_add(self.show_connection_dialog, True)

    def send_message(self, button=None):
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False): return
        current_model = self.model_drop_down.get_selected_item()
        if current_model is None:
            self.show_toast("info", 0, self.main_overlay)
            return
        formated_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")
        self.chats["chats"][self.chats["selected_chat"]]["messages"].append({
            "role": "user",
            "model": "User",
            "date": formated_datetime,
            "content": self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        })
        data = {
            "model": current_model.get_string(),
            "messages": self.chats["chats"][self.chats["selected_chat"]]["messages"]
        }
        if self.verify_if_image_can_be_used() and self.attached_image["base64"] is not None:
            data["messages"][-1]["images"] = [self.attached_image["base64"]]
        self.message_text_view.set_sensitive(False)
        self.send_button.set_sensitive(False)
        self.image_button.set_sensitive(False)
        self.show_message(self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False), False, f"\n\n<small>{formated_datetime}</small>", self.attached_image["base64"])
        self.message_text_view.get_buffer().set_text("", 0)
        self.show_message("", True)
        self.loading_spinner = Gtk.Spinner(spinning=True, margin_top=12, margin_bottom=12, hexpand=True)
        self.chat_container.append(self.loading_spinner)
        thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model']))
        thread.start()

    def delete_model(self, dialog, task, model_name):
        if dialog.choose_finish(task) == "delete":
            response = simple_delete(self.ollama_url + "/api/delete", data={"name": model_name})
            self.update_list_local_models()
            if response['status'] == 'ok':
                self.show_toast("good", 0, self.manage_models_overlay)
            else:
                self.show_toast("error", 3, self.connection_overlay)
                self.manage_models_dialog.close()
                self.show_connection_dialog(True)

    def pull_model_update(self, data, model_name):
        if model_name in list(self.pulling_models.keys()):
            GLib.idle_add(self.pulling_models[model_name].set_subtitle, data['status'] + (f" | {round(data['completed'] / data['total'] * 100, 2)}%" if 'completed' in data and 'total' in data else ""))
        else:
            sys.exit()

    def pull_model(self, model_name, tag):
        data = {"name":f"{model_name}:{tag}"}
        response = stream_post(f"{self.ollama_url}/api/pull", data=json.dumps(data), callback=lambda data, model_name=f"{model_name}:{tag}": self.pull_model_update(data, model_name))
        GLib.idle_add(self.update_list_local_models)
        if response['status'] == 'ok':
            GLib.idle_add(self.show_notification, "Task Complete", f"Model '{model_name}:{tag}' pulled successfully.", True, Gio.ThemedIcon.new("emblem-ok-symbolic"))
            GLib.idle_add(self.show_toast, "good", 1, self.manage_models_overlay)
            GLib.idle_add(self.pulling_models[f"{model_name}:{tag}"].get_parent().remove, self.pulling_models[f"{model_name}:{tag}"])
            del self.pulling_models[f"{model_name}:{tag}"]

        else:
            GLib.idle_add(self.show_notification, "Pull Model Error", f"Failed to pull model '{model_name}:{tag}' due to network error.", True, Gio.ThemedIcon.new("dialog-error-symbolic"))
            GLib.idle_add(self.show_toast, "error", 4, self.connection_overlay)
            GLib.idle_add(self.manage_models_dialog.close)
            GLib.idle_add(self.show_connection_dialog, True)

    def stop_pull_model(self, dialog, task, model_name):
        if dialog.choose_finish(task) == "stop":
            GLib.idle_add(self.pulling_models[model_name].get_parent().remove, self.pulling_models[model_name])
            del self.pulling_models[model_name]

    def stop_pull_model_dialog(self, model_name):
        dialog = Adw.AlertDialog(
            heading="Stop Model",
            body=f"Are you sure you want to stop pulling '{model_name}'?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("stop", "Stop")
        dialog.set_response_appearance("stop", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(
            parent = self.manage_models_dialog,
            cancellable = None,
            callback = lambda dialog, task, model_name = model_name: self.stop_pull_model(dialog, task, model_name)
        )

    def pull_model_start(self, dialog, task, model_name, tag_drop_down):
        if dialog.choose_finish(task) == "pull":
            tag = tag_drop_down.get_selected_item().get_string()
            if f"{model_name}:{tag}" in list(self.pulling_models.keys()): return ##TODO add message: 'already being pulled'
            if f"{model_name}:{tag}" in self.local_models: return ##TODO add message 'already pulled'
            #self.pull_model_status_page.set_description(f"{model_name}:{tag}")
            model_row = Adw.ActionRow(
                title = f"{model_name}:{tag}",
                subtitle = ""
            )
            thread = threading.Thread(target=self.pull_model, args=(model_name, tag))
            self.pulling_models[f"{model_name}:{tag}"] = model_row
            button = Gtk.Button(
                icon_name = "media-playback-stop-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["error"]
            )
            button.connect("clicked", lambda button, model_name=f"{model_name}:{tag}" : self.stop_pull_model_dialog(model_name))
            model_row.add_suffix(button)
            self.pulling_model_list_box.append(model_row)
            thread.start()

    def model_delete_button_activate(self, model_name):
        dialog = Adw.AlertDialog(
            heading="Delete Model",
            body=f"Are you sure you want to delete '{model_name}'?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(
            parent = self.manage_models_dialog,
            cancellable = None,
            callback = lambda dialog, task, model_name = model_name: self.delete_model(dialog, task, model_name)
        )

    def model_pull_button_activate(self, model_name):
        tag_list = Gtk.StringList()
        for tag in available_models[model_name]['tags']:
            tag_list.append(tag)
        tag_drop_down = Gtk.DropDown(
            enable_search=True,
            model=tag_list
        )
        dialog = Adw.AlertDialog(
            heading="Pull Model",
            body=f"Please select a tag to pull '{model_name}'",
            extra_child=tag_drop_down,
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("pull", "Pull")
        dialog.set_response_appearance("pull", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self.manage_models_dialog,
            cancellable = None,
            callback = lambda dialog, task, model_name = model_name, tag_drop_down = tag_drop_down: self.pull_model_start(dialog, task, model_name, tag_drop_down)
        )

    def update_list_available_models(self):
        self.available_model_list_box.remove_all()
        for name, model_info in available_models.items():
            model = Adw.ActionRow(
                title = name,
                subtitle = model_info['description'],
            )
            button = Gtk.Button(
                icon_name = "folder-download-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["accent"]
            )
            button.connect("clicked", lambda button=button, model_name=name: self.model_pull_button_activate(model_name))
            model.add_suffix(button)
            self.available_model_list_box.append(model)

    def manage_models_button_activate(self, button=None):
        self.update_list_local_models()
        self.manage_models_dialog.present(self)

    def connection_carousel_page_changed(self, carousel, index):
        if index == 0: self.connection_previous_button.set_sensitive(False)
        else: self.connection_previous_button.set_sensitive(True)
        if index == carousel.get_n_pages()-1: self.connection_next_button.set_label("Connect")
        else: self.connection_next_button.set_label("Next")

    def connection_previous_button_activate(self, button):
        self.connection_carousel.scroll_to(self.connection_carousel.get_nth_page(self.connection_carousel.get_position()-1), True)

    def connection_next_button_activate(self, button):
        if button.get_label() == "Next": self.connection_carousel.scroll_to(self.connection_carousel.get_nth_page(self.connection_carousel.get_position()+1), True)
        else:
            self.ollama_url = self.connection_url_entry.get_text()
            if self.verify_connection():
                self.connection_dialog.force_close()
            else:
                self.show_connection_dialog(True)
                self.show_toast("error", 1, self.connection_overlay)

    def show_connection_dialog(self, error:bool=False):
        self.connection_carousel.scroll_to(self.connection_carousel.get_nth_page(self.connection_carousel.get_n_pages()-1),False)
        if self.ollama_url is not None: self.connection_url_entry.set_text(self.ollama_url)
        if error: self.connection_url_entry.set_css_classes(["error"])
        else: self.connection_url_entry.set_css_classes([])
        self.connection_dialog.present(self)

    def clear_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        self.chats["chats"][self.chats["selected_chat"]]["messages"] = []

    def clear_chat_dialog_response(self, dialog, task):
        if dialog.choose_finish(task) == "empty":
            self.clear_chat()
            self.save_history()

    def clear_chat_dialog(self):
        if self.bot_message is not None:
            self.show_toast("info", 1, self.main_overlay)
            return
        dialog = Adw.AlertDialog(
            heading=f"Clear Chat",
            body=f"Are you sure you want to clear the chat?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("empty", "Empty")
        dialog.set_response_appearance("empty", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = self.clear_chat_dialog_response
        )

    def save_history(self):
        with open(os.path.join(self.config_dir, "chats.json"), "w+") as f:
            json.dump(self.chats, f, indent=4)

    def load_history_into_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        for message in self.chats['chats'][self.chats["selected_chat"]]['messages']:
            if message['role'] == 'user':
                self.show_message(message['content'], False, f"\n\n<small>{message['date']}</small>", message['images'][0] if 'images' in message and len(message['images']) > 0 else None)
            else:
                self.show_message(message['content'], True, f"\n\n<small>{message['model']}\t|\t{message['date']}</small>")
                self.add_code_blocks()
                self.bot_message = None

    def load_history(self):
        if os.path.exists(os.path.join(self.config_dir, "chats.json")):
            self.clear_chat()
            try:
                with open(os.path.join(self.config_dir, "chats.json"), "r") as f:
                    self.chats = json.load(f)
                    if "selected_chat" not in self.chats or self.chats["selected_chat"] not in self.chats["chats"]: self.chats["selected_chat"] = list(self.chats["chats"].keys())[0]
                    if len(list(self.chats["chats"].keys())) == 0: self.chats["chats"]["New chat"] = {"messages": []}
            except Exception as e:
                self.chats = {"chats": {"New chat": {"messages": []}}, "selected_chat": "New chat"}
            self.load_history_into_chat()

    def closing_connection_dialog_response(self, dialog, task):
        result = dialog.choose_finish(task)
        if result == "cancel": return
        if result == "save":
            self.ollama_url = self.connection_url_entry.get_text()
        elif result == "discard" and self.ollama_url is None: self.destroy()
        self.connection_dialog.force_close()
        if self.ollama_url is None or self.verify_connection() == False:
            self.show_connection_dialog(True)
            self.show_toast("error", 1, self.connection_overlay)


    def closing_connection_dialog(self, dialog):
        if self.ollama_url is None or self.first_time_setup: self.destroy()
        if self.ollama_url == self.connection_url_entry.get_text():
            self.connection_dialog.force_close()
            if self.ollama_url is None or self.verify_connection() == False:
                self.show_connection_dialog(True)
                self.show_toast("error", 1, self.connection_overlay)
            else: self.first_time_setup = False
            return
        dialog = Adw.AlertDialog(
            heading=f"Save Changes?",
            body=f"Do you want to save the URL change?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = self.closing_connection_dialog_response
        )

    def load_image(self, file_dialog, result):
        try: file = file_dialog.open_finish(result)
        except: return
        try:
            self.attached_image["path"] = file.get_path()
            '''with open(self.attached_image["path"], "rb") as image_file:
                self.attached_image["base64"] = base64.b64encode(image_file.read()).decode("utf-8")'''
            with Image.open(self.attached_image["path"]) as img:
                width, height = img.size
                max_size = 240
                if width > height:
                    new_width = max_size
                    new_height = int((max_size / width) * height)
                else:
                    new_height = max_size
                    new_width = int((max_size / height) * width)
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                with BytesIO() as output:
                    resized_img.save(output, format="JPEG")
                    image_data = output.getvalue()
                self.attached_image["base64"] = base64.b64encode(image_data).decode("utf-8")

            self.image_button.set_css_classes(["destructive-action"])
            self.image_button.get_child().set_icon_name("edit-delete-symbolic")
        except Exception as e:
            self.show_toast("error", 5, self.main_overlay)

    def remove_image(self, dialog, task):
        if dialog.choose_finish(task) == 'remove':
            self.image_button.set_css_classes([])
            self.image_button.get_child().set_icon_name("image-x-generic-symbolic")
            self.attached_image = {"path": None, "base64": None}

    def open_image(self, button):
        if "destructive-action" in button.get_css_classes():
            dialog = Adw.AlertDialog(
                heading=f"Remove Image?",
                body=f"Are you sure you want to remove image?",
                close_response="cancel"
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("remove", "Remove")
            dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.choose(
                parent = self,
                cancellable = None,
                callback = self.remove_image
            )
        else:
            file_dialog = Gtk.FileDialog(default_filter=self.file_filter_image)
            file_dialog.open(self, None, self.load_image)

    def chat_delete(self, dialog, task, chat_name):
        if dialog.choose_finish(task) == "delete":
            del self.chats['chats'][chat_name]
            self.save_history()
            self.update_chat_list()

    def chat_delete_dialog(self, chat_name):
        if len(self.chats['chats'])==1:
            self.show_toast("error", 6, self.main_overlay)
            return
        dialog = Adw.AlertDialog(
            heading=f"Delete Chat",
            body=f"Are you sure you want to delete '{chat_name}'?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = lambda dialog, task, chat_name=chat_name: self.chat_delete(dialog, task, chat_name)
        )
    def chat_rename(self, dialog=None, task=None, old_chat_name:str="", entry=None):
        if not entry: return
        new_chat_name = entry.get_text()
        if old_chat_name == new_chat_name: return
        if new_chat_name and (not task or dialog.choose_finish(task) == "rename"):
            dialog.force_close()
            if new_chat_name in self.chats["chats"]: self.chat_rename_dialog(old_chat_name, f"The name '{new_chat_name}' is already in use", True)
            else:
                self.chats["chats"][new_chat_name] = self.chats["chats"][old_chat_name]
                del self.chats["chats"][old_chat_name]
                self.save_history()
                self.update_chat_list()


    def chat_rename_dialog(self, chat_name:str, body:str, error:bool=False):
        entry = Gtk.Entry(
            css_classes = ["error"] if error else None
        )
        dialog = Adw.AlertDialog(
            heading=f"Rename Chat",
            body=body,
            extra_child=entry,
            close_response="cancel"
        )
        entry.connect("activate", lambda entry, dialog=dialog, old_chat_name=chat_name: self.chat_rename(dialog=dialog, old_chat_name=old_chat_name, entry=entry))
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = lambda dialog, task, old_chat_name=chat_name, entry=entry: self.chat_rename(dialog=dialog, task=task, old_chat_name=old_chat_name, entry=entry)
        )

    def chat_new(self, dialog=None, task=None, entry=None):
        if not entry: return
        chat_name = entry.get_text()
        if chat_name and (not task or dialog.choose_finish(task) == "create"):
            dialog.force_close()
            if chat_name in self.chats["chats"]: self.chat_new_dialog(f"The name '{chat_name}' is already in use", True)
            else:
                self.chats["chats"][chat_name] = {"messages": []}
                self.chats["selected_chat"] = chat_name
                self.save_history()
                self.update_chat_list()
                self.load_history_into_chat()

    def chat_new_dialog(self, body:str, error:bool=False):
        entry = Gtk.Entry(
            css_classes = ["error"] if error else None
        )
        dialog = Adw.AlertDialog(
            heading=f"Create Chat",
            body=body,
            extra_child=entry,
            close_response="cancel"
        )
        entry.connect("activate", lambda entry, dialog=dialog: self.chat_new(dialog=dialog, entry=entry))
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = lambda dialog, task, entry=entry: self.chat_new(dialog=dialog, task=task, entry=entry)
        )

    def update_chat_list(self):
        self.chat_list_box.remove_all()
        for name, content in self.chats['chats'].items():
            chat = Adw.ActionRow(
                title = name,
                margin_top = 6,
                margin_start = 6,
                margin_end = 6,
                css_classes = ["card"]
            )
            button_delete = Gtk.Button(
                icon_name = "user-trash-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["error", "flat"]
            )
            button_delete.connect("clicked", lambda button, chat_name=name: self.chat_delete_dialog(chat_name=chat_name))
            button_rename = Gtk.Button(
                icon_name = "document-edit-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["accent", "flat"]
            )
            button_rename.connect("clicked", lambda button, chat_name=name: self.chat_rename_dialog(chat_name=chat_name, body=f"Renaming '{chat_name}'", error=False))

            chat.add_suffix(button_delete)
            chat.add_suffix(button_rename)
            self.chat_list_box.append(chat)
            if name==self.chats["selected_chat"]: self.chat_list_box.select_row(chat)

    def chat_changed(self, listbox, row):
        if row and row.get_title() != self.chats["selected_chat"]:
            self.chats["selected_chat"] = row.get_title()
            self.load_history_into_chat()
            if len(self.chats["chats"][self.chats["selected_chat"]]["messages"]) > 0:
                for i in range(self.model_string_list.get_n_items()):
                    if self.model_string_list.get_string(i) == self.chats["chats"][self.chats["selected_chat"]]["messages"][-1]["model"]:
                        self.model_drop_down.set_selected(i)
                        break

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()

        self.set_help_overlay(self.shortcut_window)
        self.get_application().set_accels_for_action("win.show-help-overlay", ['<primary>slash'])
        self.get_application().create_action('send', lambda *_: self.send_message(self), ['<primary>Return'])

        self.manage_models_button.connect("clicked", self.manage_models_button_activate)
        self.send_button.connect("clicked", self.send_message)
        self.image_button.connect("clicked", self.open_image)
        self.add_chat_button.connect("clicked", lambda button : self.chat_new_dialog("Enter name for new chat", False))
        self.set_default_widget(self.send_button)
        self.model_drop_down.connect("notify", self.verify_if_image_can_be_used)
        self.chat_list_box.connect("row-selected", self.chat_changed)
        #self.message_text_view.set_activates_default(self.send_button)
        self.connection_carousel.connect("page-changed", self.connection_carousel_page_changed)
        self.connection_previous_button.connect("clicked", self.connection_previous_button_activate)
        self.connection_next_button.connect("clicked", self.connection_next_button_activate)
        self.connection_url_entry.connect("changed", lambda entry: entry.set_css_classes([]))
        self.connection_dialog.connect("close-attempt", self.closing_connection_dialog)
        self.load_history()
        if os.path.exists(os.path.join(self.config_dir, "server.conf")):
            with open(os.path.join(self.config_dir, "server.conf"), "r") as f:
                self.ollama_url = f.read()
            if self.verify_connection() is False: self.show_connection_dialog(True)
        else:
            self.first_time_setup = True
            self.connection_dialog.present(self)
        self.update_list_available_models()
        self.update_chat_list()
