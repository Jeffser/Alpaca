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
import json, requests, threading, os, re, base64, sys, gettext, locale, webbrowser, subprocess
from time import sleep
from io import BytesIO
from PIL import Image
from datetime import datetime
from .connection_handler import simple_get, simple_delete, stream_post, stream_post_fake
from .available_models import available_models

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    config_dir = os.getenv("XDG_CONFIG_HOME")
    data_dir = os.getenv("XDG_DATA_HOME")
    app_dir = os.getenv("FLATPAK_DEST")

    __gtype_name__ = 'AlpacaWindow'

    localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')

    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain('com.jeffser.Alpaca', localedir)
    gettext.textdomain('com.jeffser.Alpaca')
    _ = gettext.gettext

    #Variables
    run_on_background = False
    ollama_url = ""
    remote_url = ""
    run_remote = False
    local_ollama_port = 11435
    local_ollama_instance = None
    local_models = []
    pulling_models = {}
    current_chat_elements = [] #Used for deleting
    chats = {"chats": {_("New Chat"): {"messages": []}}, "selected_chat": "New Chat"}
    attached_image = {"path": None, "base64": None}
    first_time_setup = False

    #Elements
    preferences_dialog = Gtk.Template.Child()
    shortcut_window : Gtk.ShortcutsWindow  = Gtk.Template.Child()
    bot_message : Gtk.TextBuffer = None
    bot_message_box : Gtk.Box = None
    bot_message_view : Gtk.TextView = None
    welcome_dialog = Gtk.Template.Child()
    welcome_carousel = Gtk.Template.Child()
    welcome_previous_button = Gtk.Template.Child()
    welcome_next_button = Gtk.Template.Child()
    main_overlay = Gtk.Template.Child()
    manage_models_overlay = Gtk.Template.Child()
    chat_container = Gtk.Template.Child()
    chat_window = Gtk.Template.Child()
    message_text_view = Gtk.Template.Child()
    send_button = Gtk.Template.Child()
    image_button = Gtk.Template.Child()
    file_filter_image = Gtk.Template.Child()
    file_filter_json = Gtk.Template.Child()
    model_drop_down = Gtk.Template.Child()
    model_string_list = Gtk.Template.Child()

    manage_models_button = Gtk.Template.Child()
    manage_models_dialog = Gtk.Template.Child()
    pulling_model_list_box = Gtk.Template.Child()
    local_model_list_box = Gtk.Template.Child()
    available_model_list_box = Gtk.Template.Child()

    chat_list_box = Gtk.Template.Child()
    add_chat_button = Gtk.Template.Child()
    export_chat_button = Gtk.Template.Child()
    import_chat_button = Gtk.Template.Child()

    loading_spinner = None

    background_switch = Gtk.Template.Child()
    remote_connection_switch = Gtk.Template.Child()
    remote_connection_entry = Gtk.Template.Child()

    toast_messages = {
        "error": [
            _("An error occurred"),
            _("Failed to connect to server"),
            _("Could not list local models"),
            _("Could not delete model"),
            _("Could not pull model"),
            _("Cannot open image"),
            _("Cannot delete chat because it's the only one left"),
            _("There was an error with the local Ollama instance, so it has been reset")
        ],
        "info": [
            _("Please select a model before chatting"),
            _("Chat cannot be cleared while receiving a message"),
            _("That tag is already being pulled"),
            _("That tag has been pulled already"),
            _("Code copied to the clipboard")
        ],
        "good": [
            _("Model deleted successfully"),
            _("Model pulled successfully"),
            _("Chat exported successfully"),
            _("Chat imported successfully")
        ]
    }

    style_manager = Adw.StyleManager()

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

    def delete_message(self, message_element):
        message_index = self.current_chat_elements.index(message_element)
        del self.chats["chats"][self.chats["selected_chat"]]["messages"][message_index]
        self.chat_container.remove(message_element)
        del self.current_chat_elements[message_index]
        self.save_history()

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
            css_classes=["flat"],
        )
        message_buffer = message_text.get_buffer()
        message_buffer.insert(message_buffer.get_end_iter(), msg)
        if footer is not None: message_buffer.insert_markup(message_buffer.get_end_iter(), footer, len(footer))

        delete_button = Gtk.Button(
            icon_name = "user-trash-symbolic",
            css_classes = ["flat", "circular", "delete-message-button"],
            valign="end",
            halign="end",
            margin_bottom=6,
            margin_end=6
        )

        message_box = Gtk.Box(
            orientation=1,
            halign='fill',
            css_classes=[None if bot else "card"],
            margin_start=0 if bot else 50,
        )
        message_text.set_valign(Gtk.Align.CENTER)

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
        self.current_chat_elements.append(Gtk.Overlay(css_classes=["message"]))
        self.current_chat_elements[-1].set_child(message_box)

        delete_button.connect("clicked", lambda button, element=self.current_chat_elements[-1]: self.delete_message(element))
        self.current_chat_elements[-1].add_overlay(delete_button)
        self.chat_container.append(self.current_chat_elements[-1])

        if bot:
            self.bot_message = message_buffer
            self.bot_message_view = message_text
            self.bot_message_box = message_box

    def verify_if_image_can_be_used(self, pspec=None, user_data=None):
        if self.model_drop_down.get_selected_item() == None: return True
        selected = self.model_drop_down.get_selected_item().get_string().split(":")[0]
        if selected in ['llava', 'bakllava', 'moondream', 'llava-llama3']:
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
            if len(json.loads(response['text'])['models']) == 0:
                self.local_model_list_box.set_visible(False)
            else:
                self.local_model_list_box.set_visible(True)
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
            self.connection_error()

    def verify_connection(self):
        response = simple_get(self.ollama_url)
        if response['status'] == 'ok':
            if "Ollama is running" in response['text']:
                with open(os.path.join(self.config_dir, "server.json"), "w+") as f:
                    json.dump({'remote_url': self.remote_url, 'run_remote': self.run_remote, 'local_port': self.local_ollama_port, 'run_on_background': self.run_on_background}, f)
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
                    hexpand=True,
                    css_classes=["flat"]
                )
                message_buffer = message_text.get_buffer()

                footer = None
                if part['text'].split("\n")[-1] == parts[-1]['text'].split("\n")[-1]:
                    footer = "\n<small>" + part['text'].split('\n')[-1] + "</small>"
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
                if language:
                    buffer = GtkSource.Buffer.new_with_language(language)
                else:
                    buffer = GtkSource.Buffer()
                buffer.set_text(part['text'])
                if self.style_manager.get_dark():
                    source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark')
                else:
                    source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita')
                buffer.set_style_scheme(source_style)
                source_view = GtkSource.View(
                    auto_indent=True, indent_width=4, buffer=buffer, show_line_numbers=True,
                    top_margin=6, bottom_margin=6, left_margin=12, right_margin=12
                )
                source_view.set_editable(False)
                code_block_box = Gtk.Box(css_classes=["card"], orientation=1, overflow=1)
                title_box = Gtk.Box(margin_start=12, margin_top=3, margin_bottom=3, margin_end=3)
                title_box.append(Gtk.Label(label=language.get_name() if language else part['language'], hexpand=True, xalign=0))
                copy_button = Gtk.Button(icon_name="edit-copy-symbolic", css_classes=["flat", "circular"])
                copy_button.connect("clicked", self.on_copy_code_clicked, buffer)
                title_box.append(copy_button)
                code_block_box.append(title_box)
                code_block_box.append(Gtk.Separator())
                code_block_box.append(source_view)
                self.bot_message_box.append(code_block_box)
                self.style_manager.connect("notify::dark", self.on_theme_changed, buffer)
        self.bot_message = None
        self.bot_message_box = None

    def on_theme_changed(self, manager, dark, buffer):
        if manager.get_dark():
            source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark')
        else:
            source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita')
        buffer.set_style_scheme(source_style)

    def on_copy_code_clicked(self, btn, text_buffer):
        clipboard = Gdk.Display().get_default().get_clipboard()
        start = text_buffer.get_start_iter()
        end = text_buffer.get_end_iter()
        text = text_buffer.get_text(start, end, False)
        clipboard.set(text)
        self.show_toast("info", 4, self.main_overlay)

    def update_bot_message(self, data):
        if self.bot_message is None:
            self.save_history()
            sys.exit()
        vadjustment = self.chat_window.get_vadjustment()
        if self.chats["chats"][self.chats["selected_chat"]]["messages"][-1]['role'] == "user" or vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
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
        GLib.idle_add(self.send_button.set_css_classes, ["suggested-action"])
        GLib.idle_add(self.send_button.get_child().set_label, "Send")
        GLib.idle_add(self.send_button.get_child().set_icon_name, "send-to-symbolic")
        GLib.idle_add(self.chat_list_box.set_sensitive, True)
        GLib.idle_add(self.export_chat_button.set_sensitive, True)
        GLib.idle_add(self.import_chat_button.set_sensitive, True)
        GLib.idle_add(self.add_chat_button.set_sensitive, True)
        if self.verify_if_image_can_be_used(): GLib.idle_add(self.image_button.set_sensitive, True)
        GLib.idle_add(self.image_button.set_css_classes, [])
        GLib.idle_add(self.image_button.get_child().set_icon_name, "image-x-generic-symbolic")
        self.attached_image = {"path": None, "base64": None}
        # GLib.idle_add(self.message_text_view.set_sensitive, True)
        if response['status'] == 'error':
            GLib.idle_add(self.connection_error)

    def send_message(self, button=None):
        if button and self.bot_message: #STOP BUTTON
            if self.loading_spinner: self.chat_container.remove(self.loading_spinner)
            if self.verify_if_image_can_be_used(): self.image_button.set_sensitive(True)
            self.image_button.set_css_classes([])
            self.image_button.get_child().set_icon_name("image-x-generic-symbolic")
            self.attached_image = {"path": None, "base64": None}
            self.chat_list_box.set_sensitive(True)
            self.add_chat_button.set_sensitive(True)
            self.export_chat_button.set_sensitive(True)
            self.import_chat_button.set_sensitive(True)
            # self.message_text_view.set_sensitive(True)
            self.send_button.set_css_classes(["suggested-action"])
            self.send_button.get_child().set_label("Send")
            self.send_button.get_child().set_icon_name("send-to-symbolic")
            self.bot_message = None
            self.bot_message_box = None
            self.bot_message_view = None
        else:
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
            # self.message_text_view.set_sensitive(False)
            self.send_button.set_css_classes(["destructive-action"])
            self.send_button.get_child().set_label("Stop")
            self.send_button.get_child().set_icon_name("edit-delete-symbolic")
            self.chat_list_box.set_sensitive(False)
            self.add_chat_button.set_sensitive(False)
            self.export_chat_button.set_sensitive(False)
            self.import_chat_button.set_sensitive(False)
            self.image_button.set_sensitive(False)

            self.show_message(self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False), False, f"\n\n<small>{formated_datetime}</small>", self.attached_image["base64"])
            self.message_text_view.get_buffer().set_text("", 0)
            self.loading_spinner = Gtk.Spinner(spinning=True, margin_top=12, margin_bottom=12, hexpand=True)
            self.chat_container.append(self.loading_spinner)
            self.show_message("", True)

            vadjustment = self.chat_window.get_vadjustment()
            vadjustment.set_value(vadjustment.get_upper())
            thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model']))
            thread.start()

    def delete_model(self, dialog, task, model_name):
        if dialog.choose_finish(task) == "delete":
            response = simple_delete(self.ollama_url + "/api/delete", data={"name": model_name})
            self.update_list_local_models()
            if response['status'] == 'ok':
                self.show_toast("good", 0, self.manage_models_overlay)
            else:
                self.manage_models_dialog.close()
                self.connection_error()

    def pull_model_update(self, data, model_name):
        if model_name in list(self.pulling_models.keys()):
            GLib.idle_add(self.pulling_models[model_name].set_subtitle, data['status'] + (f" | {round(data['completed'] / data['total'] * 100, 2)}%" if 'completed' in data and 'total' in data else ""))
        else:
            if len(list(self.pulling_models.keys())) == 0:
                GLib.idle_add(self.pulling_model_list_box.set_visible, False)
            sys.exit()

    def pull_model(self, model_name, tag):
        data = {"name":f"{model_name}:{tag}"}
        response = stream_post(f"{self.ollama_url}/api/pull", data=json.dumps(data), callback=lambda data, model_name=f"{model_name}:{tag}": self.pull_model_update(data, model_name))
        GLib.idle_add(self.update_list_local_models)

        if response['status'] == 'ok':
            GLib.idle_add(self.show_notification, _("Task Complete"), _("Model '{}' pulled successfully.").format(f"{model_name}:{tag}"), True, Gio.ThemedIcon.new("emblem-ok-symbolic"))
            GLib.idle_add(self.show_toast, "good", 1, self.manage_models_overlay)
            GLib.idle_add(self.pulling_models[f"{model_name}:{tag}"].get_parent().remove, self.pulling_models[f"{model_name}:{tag}"])
            del self.pulling_models[f"{model_name}:{tag}"]
        else:
            GLib.idle_add(self.show_notification, _("Pull Model Error"), _("Failed to pull model '{}' due to network error.").format(f"{model_name}:{tag}"), True, Gio.ThemedIcon.new("dialog-error-symbolic"))
            GLib.idle_add(self.pulling_models[f"{model_name}:{tag}"].get_parent().remove, self.pulling_models[f"{model_name}:{tag}"])
            del self.pulling_models[f"{model_name}:{tag}"]
            GLib.idle_add(self.manage_models_dialog.close)
            GLib.idle_add(self.connection_error)
        if len(list(self.pulling_models.keys())) == 0:
            GLib.idle_add(self.pulling_model_list_box.set_visible, False)

    def stop_pull_model(self, dialog, task, model_name):
        if dialog.choose_finish(task) == "stop":
            GLib.idle_add(self.pulling_models[model_name].get_parent().remove, self.pulling_models[model_name])
            del self.pulling_models[model_name]

    def stop_pull_model_dialog(self, model_name):
        dialog = Adw.AlertDialog(
            heading=_("Stop Model"),
            body=_("Are you sure you want to stop pulling '{}'?").format(model_name),
            close_response="cancel"
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("stop", _("Stop"))
        dialog.set_response_appearance("stop", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.choose(
            parent = self.manage_models_dialog,
            cancellable = None,
            callback = lambda dialog, task, model_name = model_name: self.stop_pull_model(dialog, task, model_name)
        )

    def pull_model_start(self, dialog, task, model_name, tag_drop_down):
        if dialog.choose_finish(task) == "pull":
            tag = tag_drop_down.get_selected_item().get_string()
            if f"{model_name}:{tag}" in list(self.pulling_models.keys()):
                self.show_toast("info", 3, self.manage_models_overlay)
                return
            if f"{model_name}:{tag}" in self.local_models:
                self.show_toast("info", 4, self.manage_models_overlay)
                return
            #self.pull_model_status_page.set_description(f"{model_name}:{tag}")
            self.pulling_model_list_box.set_visible(True)
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
            heading=_("Delete Model"),
            body=_("Are you sure you want to delete '{}'?").format(model_name),
            close_response="cancel"
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
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
            heading=_("Pull Model"),
            body=_("Please select a tag to pull '{}'").format(model_name),
            extra_child=tag_drop_down,
            close_response="cancel"
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("pull", _("Pull"))
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
                subtitle = "Image recognition" if model_info["image"] else None
            )
            link_button = Gtk.Button(
                icon_name = "web-browser-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["success"]
            )
            pull_button = Gtk.Button(
                icon_name = "folder-download-symbolic",
                vexpand = False,
                valign = 3,
                css_classes = ["accent"]
            )
            link_button.connect("clicked", lambda button=link_button, link=model_info["url"]: webbrowser.open(link))
            pull_button.connect("clicked", lambda button=pull_button, model_name=name: self.model_pull_button_activate(model_name))
            model.add_suffix(link_button)
            model.add_suffix(pull_button)
            self.available_model_list_box.append(model)

    def manage_models_button_activate(self, button=None):
        self.update_list_local_models()
        self.manage_models_dialog.present(self)

    def welcome_carousel_page_changed(self, carousel, index):
        if index == 0: self.welcome_previous_button.set_sensitive(False)
        else: self.welcome_previous_button.set_sensitive(True)
        if index == carousel.get_n_pages()-1: self.welcome_next_button.set_label("Connect")
        else: self.welcome_next_button.set_label("Next")

    def welcome_previous_button_activate(self, button):
        self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()-1), True)

    def welcome_next_button_activate(self, button):
        if button.get_label() == "Next": self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()+1), True)
        else:
            self.welcome_dialog.force_close()
            if not self.verify_connection():
                self.connection_error()

    def clear_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        self.chats["chats"][self.chats["selected_chat"]]["messages"] = []

    def clear_chat_dialog_response(self, dialog, task):
        if dialog.choose_finish(task) == "clear":
            self.clear_chat()
            self.save_history()

    def clear_chat_dialog(self):
        if self.bot_message is not None:
            self.show_toast("info", 1, self.main_overlay)
            return
        dialog = Adw.AlertDialog(
            heading=_("Clear Chat"),
            body=_("Are you sure you want to clear the chat?"),
            close_response="cancel"
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("clear", _("Clear"))
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
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
                    if len(list(self.chats["chats"].keys())) == 0: self.chats["chats"]["New Chat"] = {"messages": []}
            except Exception as e:
                self.chats = {"chats": {"New Chat": {"messages": []}}, "selected_chat": "New Chat"}
            self.load_history_into_chat()

    def load_image(self, file_dialog, result):
        try: file = file_dialog.open_finish(result)
        except: return
        try:
            self.attached_image["path"] = file.get_path()
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
                    resized_img.save(output, format="PNG")
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
                heading=_("Remove Image"),
                body=_("Are you sure you want to remove image?"),
                close_response="cancel"
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("remove", _("Remove"))
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
            if len(self.chats['chats'])==0:
                self.chat_new()

    def chat_delete_dialog(self, chat_name):
        dialog = Adw.AlertDialog(
            heading=_("Delete Chat"),
            body=_("Are you sure you want to delete '{}'?").format(chat_name),
            close_response="cancel"
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
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
            heading=_("Rename Chat"),
            body=body,
            extra_child=entry,
            close_response="cancel"
        )
        entry.connect("activate", lambda entry, dialog=dialog, old_chat_name=chat_name: self.chat_rename(dialog=dialog, old_chat_name=old_chat_name, entry=entry))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("rename", _("Rename"))
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = lambda dialog, task, old_chat_name=chat_name, entry=entry: self.chat_rename(dialog=dialog, task=task, old_chat_name=old_chat_name, entry=entry)
        )

    def chat_new(self, dialog=None, task=None, entry=None):
        #if not entry: return
        chat_name = None
        if entry is not None: chat_name = entry.get_text()
        if not chat_name:
            chat_name=_("New Chat")
            if chat_name in self.chats["chats"]:
                for i in range(len(list(self.chats["chats"].keys()))):
                    if chat_name + f" {i+1}" not in self.chats["chats"]:
                        chat_name += f" {i+1}"
                        break
        if not task or dialog.choose_finish(task) == "create":
            if dialog is not None: dialog.force_close()
            if chat_name in self.chats["chats"]: self.chat_new_dialog(_("The name '{}' is already in use").format(chat_name), True)
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
            heading=_("Create Chat"),
            body=body,
            extra_child=entry,
            close_response="cancel"
        )
        entry.connect("activate", lambda entry, dialog=dialog: self.chat_new(dialog=dialog, entry=entry))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create"))
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.choose(
            parent = self,
            cancellable = None,
            callback = lambda dialog, task, entry=entry: self.chat_new(dialog=dialog, task=task, entry=entry)
        )

    def update_chat_list(self):
        self.chat_list_box.remove_all()
        for name, content in self.chats['chats'].items():
            chat_content = Gtk.Box(
                spacing = 6,
            )
            chat_row = Gtk.ListBoxRow(
                css_classes = ["chat_row"],
                height_request = 45,
                child=chat_content,
                name = name
            )
            chat_label = Gtk.Label(
                label=name,
                hexpand=True,
                halign=1
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

            chat_content.append(chat_label)
            chat_content.append(button_delete)
            chat_content.append(button_rename)
            self.chat_list_box.append(chat_row)
            if name==self.chats["selected_chat"]: self.chat_list_box.select_row(chat_row)

    def chat_changed(self, listbox, row):
        if row and row.get_name() != self.chats["selected_chat"]:
            self.chats["selected_chat"] = row.get_name()
            self.load_history_into_chat()
            if len(self.chats["chats"][self.chats["selected_chat"]]["messages"]) > 0:
                for i in range(self.model_string_list.get_n_items()):
                    if self.model_string_list.get_string(i) == self.chats["chats"][self.chats["selected_chat"]]["messages"][-1]["model"]:
                        self.model_drop_down.set_selected(i)
                        break

    def show_preferences_dialog(self):
        self.preferences_dialog.present(self)

    def start_instance(self):
        self.ollama_instance = subprocess.Popen(["/app/bin/ollama", "serve"], env={**os.environ, 'OLLAMA_HOST': f"127.0.0.1:{self.local_ollama_port}", "HOME": self.data_dir}, stderr=subprocess.PIPE, text=True)
        print("Starting Alpaca's Ollama instance...")
        sleep(1)
        while True:
            err = self.ollama_instance.stderr.readline()
            if err == '' and self.ollama_instance.poll() is not None:
                break
            if 'msg="inference compute"' in err: #Ollama outputs a line with this when it finishes loading, yeah
                break
        print("Started Alpaca's Ollama instance")

    def stop_instance(self):
        self.ollama_instance.kill()
        print("Stopped Alpaca's Ollama instance")

    def restart_instance(self):
        if self.ollama_instance is not None: self.stop_instance()
        start_instance(self)

    def reconnect_remote(self, dialog, task=None, entry=None):
        response = dialog.choose_finish(task)
        dialog.force_close()
        if not task or response == "remote":
            self.ollama_url = entry.get_text()
            self.remote_url = self.ollama_url
            self.remote_connection_entry.set_text(self.remote_url)
            if self.verify_connection() == False: self.connection_error()
        elif response == "local":
            self.run_remote = False
            self.ollama_url = f"http://127.0.0.1:{self.local_ollama_port}"
            self.start_instance()
            if self.verify_connection() == False: self.connection_error()
            else: self.remote_connection_switch.set_active(False)
        elif response == "close":
            self.destroy()

    def connection_error(self):
        if self.run_remote:
            entry = Gtk.Entry(
                css_classes = ["error"],
                text = self.ollama_url
            )
            dialog = Adw.AlertDialog(
                heading=_("Connection Error"),
                body=_("The remote instance has disconnected"),
                extra_child=entry
            )
            entry.connect("activate", lambda entry, dialog=dialog: self.reconnect_remote(dialog=dialog, entry=entry))
            dialog.add_response("close", _("Close Alpaca"))
            dialog.add_response("local", _("Use local instance"))
            dialog.add_response("remote", _("Connect"))
            dialog.set_response_appearance("remote", Adw.ResponseAppearance.SUGGESTED)
            dialog.choose(
                parent = self,
                cancellable = None,
                callback = lambda dialog, task, entry=entry: self.reconnect_remote(dialog=dialog, task=task, entry=entry)
            )
        else:
            self.restart_instance()
            self.show_toast("error", 7, self.main_overlay)

    def connection_switched(self):
        new_value = self.remote_connection_switch.get_active()
        if new_value != self.run_remote:
            self.run_remote = new_value
            if self.run_remote:
                self.ollama_url = self.remote_url
                if self.verify_connection() == False: self.connection_error()
                else: self.stop_instance()
            else:
                self.ollama_url = f"http://127.0.0.1:{self.local_ollama_port}"
                self.start_instance()
                if self.verify_connection() == False: self.connection_error()
        self.update_list_available_models()
        self.update_list_local_models()

    def change_remote_url(self, entry):
        self.remote_url = entry.get_text()
        if self.run_remote:
            self.ollama_url = self.remote_url
            if self.verify_connection() == False:
                entry.set_css_classes(["error"])
                self.show_toast("error", 1, self.preferences_dialog)

    def on_replace_contents(self, file, result):
        file.replace_contents_finish(result)
        self.show_toast("good", 2, self.main_overlay)

    def on_export_current_chat(self, file_dialog, result):
        file = file_dialog.save_finish(result)
        data_to_export = {self.chats["selected_chat"]: self.chats["chats"][self.chats["selected_chat"]]}
        file.replace_contents_async(
            json.dumps(data_to_export, indent=4).encode("UTF-8"),
            etag=None,
            make_backup=False,
            flags=Gio.FileCreateFlags.NONE,
            cancellable=None,
            callback=self.on_replace_contents
        )

    def export_current_chat(self):
        file_dialog = Gtk.FileDialog(initial_name=f"{self.chats['selected_chat']}.json")
        file_dialog.save(parent=self, cancellable=None, callback=self.on_export_current_chat)

    def on_chat_imported(self, file_dialog, result):
        file = file_dialog.open_finish(result)
        stream = file.read(None)
        data_stream = Gio.DataInputStream.new(stream)
        data, _ = data_stream.read_until('\0', None)
        data = json.loads(data)
        chat_name = list(data.keys())[0]
        chat_content = data[chat_name]
        self.chats['chats'][chat_name] = chat_content
        self.update_chat_list()
        self.save_history()
        self.show_toast("good", 3, self.main_overlay)

    def import_chat(self):
        file_dialog = Gtk.FileDialog(default_filter=self.file_filter_json)
        file_dialog.open(self, None, self.on_chat_imported)

    def switch_run_on_background(self):
        self.run_on_background = self.background_switch.get_active()
        self.set_hide_on_close(self.run_on_background)
        self.verify_connection()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        self.set_help_overlay(self.shortcut_window)
        self.get_application().set_accels_for_action("win.show-help-overlay", ['<primary>slash'])
        self.get_application().create_action('send', lambda *_: self.send_message(self), ['Return'])
        self.manage_models_button.connect("clicked", self.manage_models_button_activate)
        self.send_button.connect("clicked", self.send_message)
        self.image_button.connect("clicked", self.open_image)
        self.add_chat_button.connect("clicked", lambda button : self.chat_new_dialog("Enter name for new chat", False))
        self.set_default_widget(self.send_button)
        self.model_drop_down.connect("notify", self.verify_if_image_can_be_used)
        self.chat_list_box.connect("row-selected", self.chat_changed)
        self.welcome_carousel.connect("page-changed", self.welcome_carousel_page_changed)
        self.welcome_previous_button.connect("clicked", self.welcome_previous_button_activate)
        self.welcome_next_button.connect("clicked", self.welcome_next_button_activate)

        self.export_chat_button.connect("clicked", lambda button : self.export_current_chat())
        self.import_chat_button.connect("clicked", lambda button : self.import_chat())
        #Preferences
        self.remote_connection_entry.connect("entry-activated", lambda entry : entry.set_css_classes([]))
        self.remote_connection_entry.connect("apply", self.change_remote_url)
        self.remote_connection_switch.connect("notify", lambda pspec, user_data : self.connection_switched())
        self.background_switch.connect("notify", lambda pspec, user_data : self.switch_run_on_background())
        if os.path.exists(os.path.join(self.config_dir, "server.json")):
            with open(os.path.join(self.config_dir, "server.json"), "r") as f:
                data = json.load(f)
                self.run_remote = data['run_remote']
                self.local_ollama_port = data['local_port']
                self.remote_url = data['remote_url']
                self.run_on_background = data['run_on_background']
                self.background_switch.set_active(self.run_on_background)
                self.set_hide_on_close(self.run_on_background)
                self.remote_connection_entry.set_text(self.remote_url)
                if self.run_remote:
                    self.ollama_url = data['remote_url']
                    self.remote_connection_switch.set_active(True)
                else:
                    self.remote_connection_switch.set_active(False)
                    self.ollama_url = f"http://127.0.0.1:{self.local_ollama_port}"
                    self.start_instance()
        else:
            self.start_instance()
            self.ollama_url = f"http://127.0.0.1:{self.local_ollama_port}"
            self.first_time_setup = True
            self.welcome_dialog.present(self)
        if self.verify_connection() is False and self.run_remote == False: self.connection_error()
        self.update_list_available_models()
        self.load_history()
        self.update_chat_list()
