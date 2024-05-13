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
from gi.repository import Adw, Gtk, GLib
import json, requests, threading
from datetime import datetime
from .connection_handler import simple_get, simple_delete, stream_post, stream_post_fake
from .available_models import available_models

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AlpacaWindow'

    #Variables
    ollama_url = None
    local_models = []
    messages_history = []

    #Elements
    bot_message : Gtk.TextBuffer = None
    overlay = Gtk.Template.Child()
    chat_container = Gtk.Template.Child()
    message_entry = Gtk.Template.Child()
    send_button = Gtk.Template.Child()
    model_drop_down = Gtk.Template.Child()
    model_string_list = Gtk.Template.Child()

    manage_models_button = Gtk.Template.Child()
    manage_models_dialog = Gtk.Template.Child()
    model_list_box = Gtk.Template.Child()

    pull_model_dialog = Gtk.Template.Child()
    pull_model_status_page = Gtk.Template.Child()
    pull_model_progress_bar = Gtk.Template.Child()

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
            wrap_mode= Gtk.WrapMode.WORD,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            css_classes=["flat"]
        )
        message_buffer = message_text.get_buffer()
        message_buffer.insert(message_buffer.get_end_iter(), msg)
        message_box = Adw.Bin(
            child=message_text,
            css_classes=["card" if bot else None]
        )
        message_text.set_valign(Gtk.Align.CENTER)
        self.chat_container.append(message_box)
        if bot: self.bot_message = message_buffer

    def update_list_local_models(self):
        self.local_models = []
        response = simple_get(self.ollama_url + "/api/tags")
        if response['status'] == 'ok':
            for model in json.loads(response['text'])['models']:
                self.model_string_list.append(model["name"])
                self.local_models.append(model["name"])
            self.model_drop_down.set_selected(0)
            return
        #IF IT CONTINUES THEN THERE WAS EN ERROR
        self.show_toast(response['text'])
        self.show_connection_dialog()

    def dialog_response(self, dialog, task):
        self.ollama_url = dialog.get_extra_child().get_text()
        if dialog.choose_finish(task) == "login":
            response = simple_get(self.ollama_url)
            if response['status'] == 'ok':
                if "Ollama is running" in response['text']:
                    self.message_entry.grab_focus_without_selecting()
                    self.update_list_local_models()
                    return
                else:
                    response = {"status": "error", "text": f"Unexpected response from {self.ollama_url} : {response['text']}"}
            #IF IT CONTINUES THEN THERE WAS EN ERROR
            self.show_toast(response['text'])
            self.show_connection_dialog()
        else:
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

        entry = Gtk.Entry(text="http://localhost:11434") #FOR TESTING PURPOSES
        dialog.set_extra_child(entry)

        dialog.choose(parent = self, cancellable = None, callback = self.dialog_response)

    def update_bot_message(self, data):
        if data['done']:
            try:
                api_datetime = data['created_at']
                api_datetime = api_datetime[:-4] + api_datetime[-1]
                formated_datetime = datetime.strptime(api_datetime, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y/%m/%d %H:%M")
                text = f"\n\n<small>{data['model']}\t|\t{formated_datetime}</small>"
                GLib.idle_add(self.bot_message.insert_markup, self.bot_message.get_end_iter(), text, len(text))
            except Exception as e: print(e)
            self.bot_message = None
        else:
            if self.bot_message is None:
                GLib.idle_add(self.show_message, data['message']['content'], True)
                self.messages_history.append({
                    "role": "assistant",
                    "content": data['message']['content']
                })
            else:
                GLib.idle_add(self.bot_message.insert_at_cursor, data['message']['content'], len(data['message']['content']))
                self.messages_history[-1]['content'] += data['message']['content']
            #else: GLib.idle_add(self.bot_message.insert, self.bot_message.get_end_iter(), data['message']['content'])

    def send_message(self):
        current_model = self.model_drop_down.get_selected_item()
        if current_model is None:
            GLib.idle_add(self.show_toast, "Please pull a model")
            return
        self.messages_history.append({
            "role": "user",
            "content": self.message_entry.get_text()
        })
        data = {
            "model": current_model.get_string(),
            "messages": self.messages_history
        }
        GLib.idle_add(self.message_entry.set_sensitive, False)
        GLib.idle_add(self.send_button.set_sensitive, False)
        GLib.idle_add(self.show_message, self.message_entry.get_text(), False)
        GLib.idle_add(self.message_entry.get_buffer().set_text, "", 0)
        response = stream_post(f"{self.ollama_url}/api/chat", data=json.dumps(data), callback=self.update_bot_message)
        GLib.idle_add(self.send_button.set_sensitive, True)
        GLib.idle_add(self.message_entry.set_sensitive, True)
        if response['status'] == 'error':
            self.show_toast(f"{response['text']}")
            self.show_connection_dialog()

    def send_button_activate(self, button):
        if not self.message_entry.get_text(): return
        thread = threading.Thread(target=self.send_message)
        thread.start()

    def delete_model(self, dialog, task, model_name, button):
        if dialog.choose_finish(task) == "delete":
            response = simple_delete(self.ollama_url + "/api/delete", data={"name": model_name})
            print(response)
            if response['status'] == 'ok':
                button.set_icon_name("folder-download-symbolic")
                button.set_css_classes(["accent", "pull"])
                self.show_toast(f"Model '{model_name}' deleted successfully")
                for i in range(self.model_string_list.get_n_items()):
                    if self.model_string_list.get_string(i) == model_name:
                        self.model_string_list.remove(i)
                        self.model_drop_down.set_selected(0)
                        break
            elif response['status_code'] == '404':
                self.show_toast(f"Delete request failed: Model was not found")
            else:
                self.show_toast(response['text'])
                self.manage_models_dialog.close()
                self.show_connection_dialog()

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
                GLib.idle_add(self.show_toast, f"Model '{model_name}' pulled successfully")
            else:
                GLib.idle_add(self.show_toast, response['text'])
                GLib.idle_add(self.manage_models_dialog.close)
                GLib.idle_add(self.show_connection_dialog)


    def pull_model_start(self, dialog, task, model_name, button):
        self.pull_model_status_page.set_description(model_name)
        thread = threading.Thread(target=self.pull_model, args=(dialog, task, model_name, button))
        thread.start()

    def model_action_button_activate(self, button, model_name):
        action = list(set(button.get_css_classes()) & set(["delete", "pull"]))[0]
        print(f"action: {action}")
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
            model_name += ":latest"
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


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.manage_models_button.connect("clicked", self.manage_models_button_activate)
        self.send_button.connect("clicked", self.send_button_activate)
        self.set_default_widget(self.send_button)
        self.message_entry.set_activates_default(self.send_button)
        self.message_entry.set_text("Hi") #FOR TESTING PURPOSES
        self.show_connection_dialog()



