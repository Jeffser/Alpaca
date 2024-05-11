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
gi.require_version("Soup", "3.0")
from gi.repository import Adw, Gtk, Gdk, GLib
import json, requests, threading



@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AlpacaWindow'
    #Variables
    ollama_url = None

    #Elements
    bot_message : Gtk.TextBuffer = None
    overlay = Gtk.Template.Child()
    chat_container = Gtk.Template.Child()
    message_entry = Gtk.Template.Child()
    send_button = Gtk.Template.Child()
    model_drop_down = Gtk.Template.Child()
    model_string_list = Gtk.Template.Child()
    pull_model_button = Gtk.Template.Child()
    pull_dialog = Gtk.Template.Child()

    def show_toast(self, msg:str):
        toast = Adw.Toast(
            title=msg,
            timeout=2
        )
        self.overlay.add_toast(toast)

    def show_message(self, msg:str, bot:bool):
        message_text = Gtk.TextView(
            editable=False,
            focusable=False,
            wrap_mode=Gtk.WrapMode.WORD,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            css_classes=["disabled"]
        )
        message_buffer = message_text.get_buffer()
        message_buffer.set_text(("BOT\n" if bot else "USER\n") + msg)
        message_box = Adw.Bin(
            child=message_text,
            css_classes=["card" if bot else "card"]
        )
        message_text.set_valign(Gtk.Align.CENTER)
        self.chat_container.append(message_box)
        if bot: self.bot_message = message_buffer

    def list_local_models(self):
        for i in range(self.model_string_list.get_n_items()):
            self.model_string_list.remove(i)
        response = requests.get(self.ollama_url + "/api/tags")
        try:
            if response.status_code == 200:
                models = json.loads(response.text)['models']
                for model in models:
                    self.model_string_list.append(model["name"].split(":")[0])
                return
            else:
                self.show_toast(f"Failed to connect to {self.ollama_url}. Status code: {response.status_code}")
        except Exception as e:
            self.show_toast(f"An error occurrerd while trying to connect to the server: {e}")

        self.show_connection_dialog()

    def dialog_response(self, _dialog, task):
        self.ollama_url = _dialog.get_extra_child().get_text()
        if _dialog.choose_finish(task) == "login":
            try:
                response = requests.get(self.ollama_url)
                if response.status_code == 200:
                    if "Ollama is running" in response.text:
                        #self.show_toast(f"Connection established with {self.ollama_url}")
                        self.message_entry.grab_focus_without_selecting()
                        self.list_local_models()
                        return
                    else:
                        self.show_toast(f"Unexpected response from {self.ollama_url} : {response.text}")
                else:
                    self.show_toast(f"Failed to connect to {self.ollama_url}. Status code: {response.status_code}")
            except Exception as e:
                self.show_toast(f"An error occurred while trying to connect to the server: {e}")

            self.show_connection_dialog()
        else:
            print("Exit")
            self.destroy()

    def show_connection_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Login",
            body="Please enter the Ollama instance URL",
            close_response="cancel"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("login", "Login")
        dialog.set_response_appearance("login", Adw.ResponseAppearance.SUGGESTED)

        entry = Gtk.Entry(text="http://localhost:11434")
        dialog.set_extra_child(entry)

        dialog.choose(parent = self, cancellable = None, callback = self.dialog_response)


    def update_bot_message(self, text):
        if self.bot_message is None: self.show_message(text, True)
        else: self.bot_message.insert(self.bot_message.get_end_iter(), text)

    def send_message(self):
        current_model = self.model_drop_down.get_selected_item()
        if current_model is None:
            GLib.idle_add(self.show_toast, "Please select a model")
            return
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "model": current_model.get_string(),
            "messages": [
                {
                    "role": "user",
                    "content": self.message_entry.get_text()
                }
            ]
        }
        GLib.idle_add(self.message_entry.set_sensitive, False)
        GLib.idle_add(self.send_button.set_sensitive, False)
        GLib.idle_add(self.show_message, self.message_entry.get_text(), False)
        response = requests.post(f"{self.ollama_url}/api/chat", headers=headers, data=json.dumps(data), stream=True)
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    try:
                        json_data = json.loads(line_str)
                        if json_data['done']: self.bot_message = None
                        else: GLib.idle_add(self.update_bot_message, json_data['message']['content'])
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")
            GLib.idle_add(self.send_button.set_sensitive, True)
            GLib.idle_add(self.message_entry.set_sensitive, True)
            GLib.idle_add(self.message_entry.get_buffer().set_text, "", 0)
        else:
            self.show_toast(f"Request failed with status code: {response.status_code}")
            self.show_connection_dialog()

    def send_button_activate(self, button):
        if not self.message_entry.get_text(): return
        thread = threading.Thread(target=self.send_message)
        thread.start()

    def pull_model_button_activate(self, button):
        self.pull_dialog.present(self)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pull_model_button.connect("clicked", self.pull_model_button_activate)
        self.send_button.connect("clicked", self.send_button_activate)
        self.set_default_widget(self.send_button)
        self.message_entry.set_activates_default(self.send_button)
        self.message_entry.set_text("Hi")
        self.show_connection_dialog()


