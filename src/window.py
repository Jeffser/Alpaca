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
import json, requests, threading, os, re, base64
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
    #In the future I will at multiple chats, for now I'll save it like this so that past chats don't break in the future
    current_chat_id="0"
    chats = {"chats": {"0": {"messages": []}}}
    attached_image = {"path": None, "base64": None}

    #Elements
    bot_message : Gtk.TextBuffer = None
    bot_message_box : Gtk.Box = None
    bot_message_view : Gtk.TextView = None
    connection_dialog = Gtk.Template.Child()
    connection_carousel = Gtk.Template.Child()
    connection_previous_button = Gtk.Template.Child()
    connection_next_button = Gtk.Template.Child()
    connection_url_entry = Gtk.Template.Child()
    main_overlay = Gtk.Template.Child()
    pull_overlay = Gtk.Template.Child()
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
    model_list_box = Gtk.Template.Child()

    pull_model_dialog = Gtk.Template.Child()
    pull_model_status_page = Gtk.Template.Child()
    pull_model_progress_bar = Gtk.Template.Child()

    toast_messages = {
        "error": [
            "An error occurred",
            "Failed to connect to server",
            "Could not list local models",
            "Could not delete model",
            "Could not pull model",
            "Cannot open image"
        ],
        "info": [
            "Please select a model before chatting",
            "Conversation cannot be cleared while receiving a message"
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

    def show_message(self, msg:str, bot:bool, footer:str=None, image_base64:str=None):
        message_text = Gtk.TextView(
            editable=False,
            focusable=False,
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
            image.set_size_request(360, 360)
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
            for model in json.loads(response['text'])['models']:
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
        for part in parts:
            if part['type'] == 'normal':
                message_text = Gtk.TextView(
                    editable=False,
                    focusable=False,
                    wrap_mode= Gtk.WrapMode.WORD,
                    margin_top=12,
                    margin_bottom=12,
                    margin_start=12,
                    margin_end=12,
                    hexpand=True,
                    css_classes=["flat"]
                )
                message_buffer = message_text.get_buffer()
                message_buffer.insert(message_buffer.get_end_iter(), part['text'])
                self.bot_message_box.append(message_text)
            else:
                language = GtkSource.LanguageManager.get_default().get_language(part['language'])
                buffer = GtkSource.Buffer.new_with_language(language)
                buffer.set_text(part['text'])
                buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('classic-dark'))
                source_view = GtkSource.View(
                    auto_indent=True, indent_width=4, buffer=buffer, show_line_numbers=True
                )
                source_view.get_style_context().add_class("card")
                self.bot_message_box.append(source_view)
        self.bot_message = None
        self.bot_message_box = None

    def update_bot_message(self, data):
        if data['done']:
            formated_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")
            text = f"\n<small>{data['model']}\t|\t{formated_datetime}</small>"
            GLib.idle_add(self.bot_message.insert_markup, self.bot_message.get_end_iter(), text, len(text))
            vadjustment = self.chat_window.get_vadjustment()
            GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
            self.save_history()
        else:
            if self.chats["chats"][self.current_chat_id]["messages"][-1]['role'] == "user":
                self.chats["chats"][self.current_chat_id]["messages"].append({
                    "role": "assistant",
                    "model": data['model'],
                    "date": datetime.now().strftime("%Y/%m/%d %H:%M"),
                    "content": ''
                })
            GLib.idle_add(self.bot_message.insert, self.bot_message.get_end_iter(), data['message']['content'])
            self.chats["chats"][self.current_chat_id]["messages"][-1]['content'] += data['message']['content']

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

    def send_message(self, button):
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False): return
        current_model = self.model_drop_down.get_selected_item()
        if current_model is None:
            self.show_toast("info", 0, self.main_overlay)
            return
        formated_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")
        self.chats["chats"][self.current_chat_id]["messages"].append({
            "role": "user",
            "model": "User",
            "date": formated_datetime,
            "content": self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        })
        data = {
            "model": current_model.get_string(),
            "messages": self.chats["chats"][self.current_chat_id]["messages"]
        }
        if self.verify_if_image_can_be_used() and self.attached_image["base64"] is not None:
            data["messages"][-1]["images"] = [self.attached_image["base64"]]
        self.message_text_view.set_sensitive(False)
        self.send_button.set_sensitive(False)
        self.image_button.set_sensitive(False)
        self.show_message(self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False), False, f"\n\n<small>{formated_datetime}</small>", self.attached_image["base64"])
        self.message_text_view.get_buffer().set_text("", 0)
        self.show_message("", True)
        thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model']))
        thread.start()

    def delete_model(self, dialog, task, model_name, button):
        if dialog.choose_finish(task) == "delete":
            response = simple_delete(self.ollama_url + "/api/delete", data={"name": model_name})
            if response['status'] == 'ok':
                button.set_icon_name("folder-download-symbolic")
                button.set_css_classes(["accent", "pull"])
                self.show_toast("good", 0, self.manage_models_overlay)
                for i in range(self.model_string_list.get_n_items()):
                    if self.model_string_list.get_string(i) == model_name:
                        self.model_string_list.remove(i)
                        self.model_drop_down.set_selected(0)
                        break
            else:
                self.show_toast("error", 3, self.connection_overlay)
                self.manage_models_dialog.close()
                self.show_connection_dialog(True)

    def pull_model_update(self, data):
        try:
            GLib.idle_add(self.pull_model_progress_bar.set_text, data['status'])
            if 'completed' in data:
                if 'total' in data: GLib.idle_add(self.pull_model_progress_bar.set_fraction, data['completed'] / data['total'])
                else: GLib.idle_add(self.pull_model_progress_bar.set_fraction, 1.0)
            else:
                GLib.idle_add(self.pull_model_progress_bar.set_fraction, 0.0)
        except Exception as e: print(e)

    def pull_model(self, dialog, task, model_name, button):
        if dialog.choose_finish(task) == "pull":
            data = {"name":model_name}
            GLib.idle_add(self.pull_model_dialog.present, self.manage_models_dialog)
            response = stream_post(f"{self.ollama_url}/api/pull", data=json.dumps(data), callback=self.pull_model_update)

            GLib.idle_add(self.pull_model_dialog.force_close)
            if response['status'] == 'ok':
                GLib.idle_add(button.set_icon_name, "user-trash-symbolic")
                GLib.idle_add(button.set_css_classes, ["error", "delete"])
                GLib.idle_add(self.model_string_list.append, model_name)
                GLib.idle_add(self.show_toast, "good", 1, self.manage_models_overlay)
            else:
                GLib.idle_add(self.show_toast, "error", 4, self.connection_overlay)
                GLib.idle_add(self.manage_models_dialog.close)
                GLib.idle_add(self.show_connection_dialog, True)


    def pull_model_start(self, dialog, task, model_name, button):
        self.pull_model_status_page.set_description(model_name)
        thread = threading.Thread(target=self.pull_model, args=(dialog, task, model_name, button))
        thread.start()

    def model_action_button_activate(self, button, model_name):
        action = list(set(button.get_css_classes()) & set(["delete", "pull"]))[0]
        dialog = Adw.AlertDialog(
            heading=f"{action.capitalize()} Model",
            body=f"Are you sure you want to {action} '{model_name}'?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response(action, action.capitalize())
        dialog.set_response_appearance(action, Adw.ResponseAppearance.DESTRUCTIVE if action == "delete" else Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self.manage_models_dialog,
            cancellable = None,
            callback = lambda dialog, task, model_name = model_name, button = button:
                self.delete_model(dialog, task, model_name, button) if action == "delete" else self.pull_model_start(dialog, task, model_name,button)
        )

    def update_list_available_models(self):
        self.model_list_box.remove_all()
        for model_name, model_description in available_models.items():
            model = Adw.ActionRow(
                title = model_name,
                subtitle = model_description,
            )
            if ":" not in model_name: model_name += ":latest"
            button = Gtk.Button(
                icon_name = "folder-download-symbolic" if model_name not in self.local_models else "user-trash-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["accent", "pull"] if model_name not in self.local_models else ["error", "delete"])
            button.connect("clicked", lambda button=button, model_name=model_name: self.model_action_button_activate(button, model_name))
            model.add_suffix(button)
            self.model_list_box.append(model)

    def manage_models_button_activate(self, button):
        self.manage_models_dialog.present(self)
        self.update_list_available_models()


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

    def clear_conversation(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        self.chats["chats"][self.current_chat_id]["messages"] = []

    def clear_conversation_dialog_response(self, dialog, task):
        if dialog.choose_finish(task) == "empty":
            self.clear_conversation()
            self.save_history()

    def clear_conversation_dialog(self):
        if self.bot_message is not None:
            self.show_toast("info", 1, self.main_overlay)
            return
        dialog = Adw.AlertDialog(
            heading=f"Clear Conversation",
            body=f"Are you sure you want to clear the conversation?",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("empty", "Empty")
        dialog.set_response_appearance("empty", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = self.clear_conversation_dialog_response
        )

    def save_history(self):
        with open(os.path.join(self.config_dir, "chats.json"), "w+") as f:
            json.dump(self.chats, f, indent=4)

    def load_history(self):
        if os.path.exists(os.path.join(self.config_dir, "chats.json")):
            self.clear_conversation()
            try:
                with open(os.path.join(self.config_dir, "chats.json"), "r") as f:
                    self.chats = json.load(f)
            except Exception as e:
                self.chats = {"chats": {"0": {"messages": []}}}
            for message in self.chats['chats'][self.current_chat_id]['messages']:
                if message['role'] == 'user':
                    self.show_message(message['content'], False, f"\n\n<small>{message['date']}</small>", message['images'][0] if 'images' in message and len(message['images']) > 0 else None)
                else:
                    self.show_message(message['content'], True, f"\n\n<small>{message['model']}\t|\t{message['date']}</small>")
                    self.add_code_blocks()
                    self.bot_message = None

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
        if self.ollama_url is None: self.destroy()
        if self.ollama_url == self.connection_url_entry.get_text():
            self.connection_dialog.force_close()
            if self.ollama_url is None or self.verify_connection() == False:
                self.show_connection_dialog(True)
                self.show_toast("error", 1, self.connection_overlay)
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
            print(e)
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        self.manage_models_button.connect("clicked", self.manage_models_button_activate)
        self.send_button.connect("clicked", self.send_message)
        self.image_button.connect("clicked", self.open_image)
        self.set_default_widget(self.send_button)
        self.model_drop_down.connect("notify", self.verify_if_image_can_be_used)
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
        else: self.connection_dialog.present(self)




