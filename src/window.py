# window.py
#
# Copyright 2024 Jeffser
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
import json, requests, threading, os, re, base64, sys, gettext, locale, webbrowser, subprocess, uuid, shutil, tarfile, tempfile
from time import sleep
from io import BytesIO
from PIL import Image
from datetime import datetime
from .available_models import available_models
from . import dialogs, local_instance, connection_handler, update_history

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    config_dir = os.getenv("XDG_CONFIG_HOME")
    data_dir = os.getenv("XDG_DATA_HOME")
    app_dir = os.getenv("FLATPAK_DEST")
    cache_dir = os.getenv("XDG_CACHE_HOME")

    __gtype_name__ = 'AlpacaWindow'

    localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')

    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain('com.jeffser.Alpaca', localedir)
    gettext.textdomain('com.jeffser.Alpaca')
    _ = gettext.gettext

    #Variables
    run_on_background = False
    remote_url = ""
    run_remote = False
    model_tweaks = {"temperature": 0.7, "seed": 0, "keep_alive": 5}
    local_models = []
    pulling_models = {}
    chats = {"chats": {_("New Chat"): {"messages": {}}}, "selected_chat": "New Chat"}
    attachments = {}

    #Override elements
    override_HSA_OVERRIDE_GFX_VERSION = Gtk.Template.Child()
    override_CUDA_VISIBLE_DEVICES = Gtk.Template.Child()
    override_HIP_VISIBLE_DEVICES = Gtk.Template.Child()

    #Elements
    create_model_base = Gtk.Template.Child()
    create_model_name = Gtk.Template.Child()
    create_model_system = Gtk.Template.Child()
    create_model_template = Gtk.Template.Child()
    create_model_dialog = Gtk.Template.Child()
    temperature_spin = Gtk.Template.Child()
    seed_spin = Gtk.Template.Child()
    keep_alive_spin = Gtk.Template.Child()
    preferences_dialog = Gtk.Template.Child()
    shortcut_window : Gtk.ShortcutsWindow  = Gtk.Template.Child()
    bot_message : Gtk.TextBuffer = None
    bot_message_box : Gtk.Box = None
    bot_message_view : Gtk.TextView = None
    file_preview_dialog = Gtk.Template.Child()
    file_preview_text_view = Gtk.Template.Child()
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
    stop_button = Gtk.Template.Child()
    chats_menu_button = Gtk.Template.Child()
    attachment_container = Gtk.Template.Child()
    attachment_box = Gtk.Template.Child()
    file_filter_image = Gtk.Template.Child()
    file_filter_tar = Gtk.Template.Child()
    file_filter_gguf = Gtk.Template.Child()
    file_filter_text = Gtk.Template.Child()
    model_drop_down = Gtk.Template.Child()
    model_string_list = Gtk.Template.Child()

    manage_models_dialog = Gtk.Template.Child()
    pulling_model_list_box = Gtk.Template.Child()
    local_model_list_box = Gtk.Template.Child()
    available_model_list_box = Gtk.Template.Child()

    chat_list_box = Gtk.Template.Child()
    add_chat_button = Gtk.Template.Child()

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
            _("There was an error with the local Ollama instance, so it has been reset"),
            _("Image recognition is only available on specific models")
        ],
        "info": [
            _("Please select a model before chatting"),
            _("Chat cannot be cleared while receiving a message"),
            _("That tag is already being pulled"),
            _("That tag has been pulled already"),
            _("Code copied to the clipboard"),
            _("Message copied to the clipboard")
        ],
        "good": [
            _("Model deleted successfully"),
            _("Model pulled successfully"),
            _("Chat exported successfully"),
            _("Chat imported successfully")
        ]
    }

    style_manager = Adw.StyleManager()

    @Gtk.Template.Callback()
    def verify_if_image_can_be_used(self, pspec=None, user_data=None):
        if self.model_drop_down.get_selected_item() == None: return True
        selected = self.model_drop_down.get_selected_item().get_string().split(":")[0]
        if selected in ['llava', 'bakllava', 'moondream', 'llava-llama3']:
            for name, content in self.attachments.items():
                if content['type'] == 'image':
                    content['button'].set_css_classes(["flat"])
            return True
        else:
            for name, content in self.attachments.items():
                if content['type'] == 'image':
                    content['button'].set_css_classes(["flat", "error"])
            return False

    @Gtk.Template.Callback()
    def stop_message(self, button=None):
        if self.loading_spinner: self.chat_container.remove(self.loading_spinner)
        self.toggle_ui_sensitive(True)
        self.switch_send_stop_button()
        self.bot_message = None
        self.bot_message_box = None
        self.bot_message_view = None

    @Gtk.Template.Callback()
    def send_message(self, button=None):
        if self.bot_message: return
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False): return
        current_model = self.model_drop_down.get_selected_item()
        if current_model is None:
            self.show_toast("info", 0, self.main_overlay)
            return
        id = self.generate_uuid()

        attached_images = []
        attached_files = {}
        can_use_images = self.verify_if_image_can_be_used()
        for name, content in self.attachments.items():
            if content["type"] == 'image' and can_use_images: attached_images.append(name)
            else: attached_files[name] = content['type']
            if not os.path.exists(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id)):
                os.makedirs(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id))
            shutil.copy(content['path'], os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id, name))
            content["button"].get_parent().remove(content["button"])
        self.attachments = {}
        self.attachment_box.set_visible(False)

            #{"path": file_path, "type": file_type, "content": content}

        formated_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")

        self.chats["chats"][self.chats["selected_chat"]]["messages"][id] = {
            "role": "user",
            "model": "User",
            "date": formated_datetime,
            "content": self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        }
        if len(attached_images) > 0:
            self.chats["chats"][self.chats["selected_chat"]]["messages"][id]['images'] = attached_images
        if len(attached_files.keys()) > 0:
            self.chats["chats"][self.chats["selected_chat"]]["messages"][id]['files'] = attached_files
        data = {
            "model": current_model.get_string(),
            "messages": self.convert_history_to_ollama(),
            "options": {"temperature": self.model_tweaks["temperature"], "seed": self.model_tweaks["seed"]},
            "keep_alive": f"{self.model_tweaks['keep_alive']}m"
        }
        self.switch_send_stop_button()
        self.toggle_ui_sensitive(False)

        #self.attachments[name] = {"path": file_path, "type": file_type, "content": content}
        self.show_message(self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False), False, f"\n\n<small>{formated_datetime}</small>", attached_images, attached_files, id=id)
        self.message_text_view.get_buffer().set_text("", 0)
        self.loading_spinner = Gtk.Spinner(spinning=True, margin_top=12, margin_bottom=12, hexpand=True)
        self.chat_container.append(self.loading_spinner)
        bot_id=self.generate_uuid()
        self.show_message("", True, id=bot_id)

        thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model'], bot_id))
        thread.start()

    @Gtk.Template.Callback()
    def manage_models_button_activate(self, button=None):
        self.update_list_local_models()
        self.manage_models_dialog.present(self)

    @Gtk.Template.Callback()
    def welcome_carousel_page_changed(self, carousel, index):
        if index == 0: self.welcome_previous_button.set_sensitive(False)
        else: self.welcome_previous_button.set_sensitive(True)
        if index == carousel.get_n_pages()-1: self.welcome_next_button.set_label(_("Close"))
        else: self.welcome_next_button.set_label(_("Next"))

    @Gtk.Template.Callback()
    def welcome_previous_button_activate(self, button):
        self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()-1), True)

    @Gtk.Template.Callback()
    def welcome_next_button_activate(self, button):
        if button.get_label() == "Next": self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()+1), True)
        else:
            self.welcome_dialog.force_close()
            if not self.verify_connection():
                self.connection_error()

    @Gtk.Template.Callback()
    def chat_changed(self, listbox, row):
        if row and row.get_name() != self.chats["selected_chat"]:
            self.chats["selected_chat"] = row.get_name()
            self.load_history_into_chat()
            if len(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys()) > 0:
                for i in range(self.model_string_list.get_n_items()):
                    if self.model_string_list.get_string(i) == self.chats["chats"][self.chats["selected_chat"]]["messages"][list(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys())[-1]]["model"]:
                        self.model_drop_down.set_selected(i)
                        break

    @Gtk.Template.Callback()
    def change_remote_url(self, entry):
        self.remote_url = entry.get_text()
        if self.run_remote:
            connection_handler.url = self.remote_url
            if self.verify_connection() == False:
                entry.set_css_classes(["error"])
                self.show_toast("error", 1, self.preferences_dialog)

    @Gtk.Template.Callback()
    def pull_featured_model(self, button):
        action_row = button.get_parent().get_parent().get_parent()
        button.get_parent().remove(button)
        model = f"{action_row.get_title().lower()}:latest"
        action_row.set_subtitle(_("Pulling in the background..."))
        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        action_row.add_suffix(spinner)
        action_row.set_sensitive(False)
        self.pull_model(model)

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        if self.get_hide_on_close():
            print("Hiding app...")
        else:
            print("Closing app...")
            local_instance.stop()

    @Gtk.Template.Callback()
    def model_spin_changed(self, spin):
        value = spin.get_value()
        if spin.get_name() != "temperature": value = round(value)
        else: value = round(value, 1)
        if self.model_tweaks[spin.get_name()] is not None and self.model_tweaks[spin.get_name()] != value:
            self.model_tweaks[spin.get_name()] = value
            self.save_server_config()

    @Gtk.Template.Callback()
    def create_model_start(self, button):
        base = self.create_model_base.get_subtitle()
        name = self.create_model_name.get_text()
        system = self.create_model_system.get_text()
        template = self.create_model_template.get_text()
        if "/" in base:
            modelfile = f"FROM {base}\nSYSTEM {system}\nTEMPLATE {template}"
        else:
            modelfile = f"FROM {base}\nSYSTEM {system}"
        self.pulling_model_list_box.set_visible(True)
        model_row = Adw.ActionRow(
            title = name
        )
        thread = threading.Thread(target=self.pull_model_process, kwargs={"model": name, "modelfile": modelfile})
        overlay = Gtk.Overlay()
        progress_bar = Gtk.ProgressBar(
            valign = 2,
            show_text = False,
            margin_start = 10,
            margin_end = 10,
            css_classes = ["osd", "horizontal", "bottom"]
        )
        button = Gtk.Button(
            icon_name = "media-playback-stop-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["error"]
        )
        button.connect("clicked", lambda button, model_name=name : dialogs.stop_pull_model(self, model_name))
        model_row.add_suffix(button)
        self.pulling_models[name] = {"row": model_row, "progress_bar": progress_bar, "overlay": overlay}
        overlay.set_child(model_row)
        overlay.add_overlay(progress_bar)
        self.pulling_model_list_box.append(overlay)
        self.create_model_dialog.close()
        self.manage_models_dialog.present(self)
        thread.start()

    @Gtk.Template.Callback()
    def override_changed(self, entry):
        name = entry.get_name()
        value = entry.get_text()
        if (not value and name not in local_instance.overrides) or (value and value in local_instance.overrides and local_instance.overrides[name] == value): return
        if not value: del local_instance.overrides[name]
        else: local_instance.overrides[name] = value
        self.save_server_config()
        if not self.run_remote: local_instance.reset()

    @Gtk.Template.Callback()
    def link_button_handler(self, button):
        webbrowser.open(button.get_name())

    def check_alphanumeric(self, editable, text, length, position):
        new_text = ''.join([char for char in text if char.isalnum() or char in ['-', '_']])
        if new_text != text: editable.stop_emission_by_name("insert-text")

    def create_model(self, model:str, file:bool):
        name = ""
        system = ""
        template = ""
        if not file:
            response = connection_handler.simple_post(f"{connection_handler.url}/api/show", json.dumps({"name": model}))
            if 'text' in response:
                data = json.loads(response['text'])

                for line in data['modelfile'].split('\n'):
                    if line.startswith('SYSTEM'):
                        system = line[len('SYSTEM'):].strip()
                    elif line.startswith('TEMPLATE'):
                        template = line[len('TEMPLATE'):].strip()
                self.create_model_template.set_sensitive(False)
                name = model.split(':')[0]
        else:
            self.create_model_template.set_sensitive(True)
            template = '"""{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>\n{{ .Response }}<|eot_id|>"""'
            name = model.split("/")[-1].split(".")[0]
        self.create_model_base.set_subtitle(model)
        self.create_model_name.set_text(name)
        self.create_model_system.set_text(system)
        self.create_model_template.set_text(template)
        self.manage_models_dialog.close()
        self.create_model_dialog.present(self)


    def show_toast(self, message_type:str, message_id:int, overlay):
        if message_type not in self.toast_messages or message_id > len(self.toast_messages[message_type] or message_id < 0):
            message_type = "error"
            message_id = 0
        toast = Adw.Toast(
            title=self.toast_messages[message_type][message_id],
            timeout=2
        )
        overlay.add_toast(toast)

    def show_notification(self, title:str, body:str, only_when_unfocus:bool, icon:Gio.ThemedIcon=None):
        if not only_when_unfocus or (only_when_unfocus and self.is_active()==False):
            notification = Gio.Notification.new(title)
            notification.set_body(body)
            if icon: notification.set_icon(icon)
            self.get_application().send_notification(None, notification)

    def delete_message(self, message_element):
        id = message_element.get_name()
        del self.chats["chats"][self.chats["selected_chat"]]["messages"][id]
        self.chat_container.remove(message_element)
        if os.path.exists(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id)):
            shutil.rmtree(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id))
        self.save_history()

    def copy_message(self, message_element):
        id = message_element.get_name()
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.chats["chats"][self.chats["selected_chat"]]["messages"][id]["content"])
        self.show_toast("info", 5, self.main_overlay)

    def preview_file(self, file_path, file_type):
        content = self.get_content_of_file(file_path, file_type)
        if content:
            buffer = self.file_preview_text_view.get_buffer()
            buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
            buffer.insert(buffer.get_start_iter(), content, len(content))
            self.file_preview_dialog.set_title(os.path.basename(file_path))
            self.file_preview_dialog.present(self)

    def convert_history_to_ollama(self):
        messages = []
        for id, message in self.chats["chats"][self.chats["selected_chat"]]["messages"].items():
            new_message = message.copy()
            if 'files' in message and len(message['files']) > 0:
                del new_message['files']
                new_message['content'] = ''
                for name, file_type in message['files'].items():
                    file_path = os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id, name)
                    file_data = self.get_content_of_file(file_path, file_type)
                    if file_data: new_message['content'] += f"```[{name}]\n{file_data}\n```"
                new_message['content'] += message['content']
            if 'images' in message and len(message['images']) > 0:
                new_message['images'] = []
                for name in message['images']:
                    file_path = os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id, name)
                    image_data = self.get_content_of_file(file_path, 'image')
                    if image_data: new_message['images'].append(image_data)
            messages.append(new_message)
        return messages


    def show_message(self, msg:str, bot:bool, footer:str=None, images:list=None, files:dict=None, id:str=None):
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

        )
        copy_button = Gtk.Button(
            icon_name = "edit-copy-symbolic",
            css_classes = ["flat", "circular", "delete-message-button"],
        )

        button_container = Gtk.Box(
            orientation=0,
            spacing=6,
            margin_end=6,
            margin_bottom=6,
            valign="end",
            halign="end"
        )

        message_box = Gtk.Box(
            orientation=1,
            halign='fill',
            css_classes=[None if bot else "card"],
            margin_start=0 if bot else 50,
        )
        message_text.set_valign(Gtk.Align.CENTER)

        if images and len(images) > 0:
            image_container = Gtk.Box(
                orientation=0,
                spacing=12
            )
            image_scroller = Gtk.ScrolledWindow(
                margin_top=10,
                margin_start=10,
                margin_end=10,
                hexpand=True,
                height_request = 240,
                child=image_container
            )
            for image in images:
                raw_data = self.get_content_of_file(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id, image), "image")
                if raw_data:
                    image_data = base64.b64decode(raw_data)
                    loader = GdkPixbuf.PixbufLoader.new()
                    loader.write(image_data)
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    image = Gtk.Image.new_from_paintable(texture)
                    image.set_size_request(240, 240)
                    image.set_hexpand(False)
                    image.set_css_classes(["flat"])
                    image_container.append(image)
            message_box.append(image_scroller)

        if files and len(files) > 0:
            file_container = Gtk.Box(
                orientation=0,
                spacing=12
            )
            file_scroller = Gtk.ScrolledWindow(
                margin_top=10,
                margin_start=10,
                margin_end=10,
                hexpand=True,
                child=file_container
            )
            for name, file_type in files.items():
                shown_name='.'.join(name.split(".")[:-1])[:20] + (name[20:] and '..') + f".{name.split('.')[-1]}"

                button_content = Adw.ButtonContent(
                    label=shown_name,
                    icon_name="document-text-symbolic"
                )
                button = Gtk.Button(
                    vexpand=False,
                    valign=3,
                    name=name,
                    css_classes=["flat"],
                    tooltip_text=name,
                    child=button_content
                )
                button.connect("clicked", lambda button, file_path=os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id, name), file_type=file_type: self.preview_file(file_path, file_type))
                file_container.append(button)
            message_box.append(file_scroller)

        message_box.append(message_text)
        overlay = Gtk.Overlay(css_classes=["message"], name=id)
        overlay.set_child(message_box)

        delete_button.connect("clicked", lambda button, element=overlay: self.delete_message(element))
        copy_button.connect("clicked", lambda button, element=overlay: self.copy_message(element))
        button_container.append(delete_button)
        button_container.append(copy_button)
        overlay.add_overlay(button_container)
        self.chat_container.append(overlay)

        if bot:
            self.bot_message = message_buffer
            self.bot_message_view = message_text
            self.bot_message_box = message_box

    def update_list_local_models(self):
        self.local_models = []
        response = connection_handler.simple_get(f"{connection_handler.url}/api/tags")
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
                button.connect("clicked", lambda button=button, model_name=model["name"]: dialogs.delete_model(self, model_name))
                model_row.add_suffix(button)
                self.local_model_list_box.append(model_row)

                self.model_string_list.append(model["name"])
                self.local_models.append(model["name"])
            self.model_drop_down.set_selected(0)
            self.verify_if_image_can_be_used()
            return
        else:
            self.connection_error()

    def save_server_config(self):
        with open(os.path.join(self.config_dir, "server.json"), "w+") as f:
            json.dump({'remote_url': self.remote_url, 'run_remote': self.run_remote, 'local_port': local_instance.port, 'run_on_background': self.run_on_background, 'model_tweaks': self.model_tweaks, 'ollama_overrides': local_instance.overrides}, f, indent=6)

    def verify_connection(self):
        response = connection_handler.simple_get(connection_handler.url)
        if response['status'] == 'ok':
            if "Ollama is running" in response['text']:
                self.save_server_config()
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
        vadjustment = self.chat_window.get_vadjustment()
        vadjustment.set_value(vadjustment.get_upper())
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

    def update_bot_message(self, data, id):
        if self.bot_message is None:
            self.save_history()
            sys.exit()
        vadjustment = self.chat_window.get_vadjustment()
        if (id in self.chats["chats"][self.chats["selected_chat"]]["messages"] and self.chats["chats"][self.chats["selected_chat"]]["messages"][id]['role'] == "user") or vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
            GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
        if data['done']:
            formated_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")
            text = f"\n<small>{data['model']}\t|\t{formated_datetime}</small>"
            GLib.idle_add(self.bot_message.insert_markup, self.bot_message.get_end_iter(), text, len(text))
            self.save_history()
        else:
            if id not in self.chats["chats"][self.chats["selected_chat"]]["messages"]:
                GLib.idle_add(self.chat_container.remove, self.loading_spinner)
                self.loading_spinner = None
                self.chats["chats"][self.chats["selected_chat"]]["messages"][id] = {
                    "role": "assistant",
                    "model": data['model'],
                    "date": datetime.now().strftime("%Y/%m/%d %H:%M"),
                    "content": ''
                }
            GLib.idle_add(self.bot_message.insert, self.bot_message.get_end_iter(), data['message']['content'])
            self.chats["chats"][self.chats["selected_chat"]]["messages"][id]['content'] += data['message']['content']

    def toggle_ui_sensitive(self, status):
        for element in [self.chat_list_box, self.add_chat_button, self.chats_menu_button]:
            element.set_sensitive(status)

    def switch_send_stop_button(self):
        self.stop_button.set_visible(self.send_button.get_visible())
        self.send_button.set_visible(not self.send_button.get_visible())

    def run_message(self, messages, model, id):
        response = connection_handler.stream_post(f"{connection_handler.url}/api/chat", data=json.dumps({"model": model, "messages": messages}), callback=lambda data, id=id: self.update_bot_message(data, id))
        GLib.idle_add(self.add_code_blocks)
        GLib.idle_add(self.switch_send_stop_button)
        GLib.idle_add(self.toggle_ui_sensitive, True)
        if self.loading_spinner:
            GLib.idle_add(self.chat_container.remove, self.loading_spinner)
            self.loading_spinner = None
        if response['status'] == 'error':
            GLib.idle_add(self.connection_error)

    def pull_model_update(self, data, model_name):
        if model_name in list(self.pulling_models.keys()):
            GLib.idle_add(self.pulling_models[model_name]['row'].set_subtitle, data['status'])
            if 'completed' in data and 'total' in data: GLib.idle_add(self.pulling_models[model_name]['progress_bar'].set_fraction, (data['completed'] / data['total']))
            else: GLib.idle_add(self.pulling_models[model_name]['progress_bar'].pulse)
        else:
            if len(list(self.pulling_models.keys())) == 0:
                GLib.idle_add(self.pulling_model_list_box.set_visible, False)

    def pull_model_process(self, model, modelfile):
        response = {}
        if modelfile:
            data = {"name": model, "modelfile": modelfile}
            response = connection_handler.stream_post(f"{connection_handler.url}/api/create", data=json.dumps(data), callback=lambda data, model_name=model: self.pull_model_update(data, model_name))
        else:
            data = {"name": model}
            response = connection_handler.stream_post(f"{connection_handler.url}/api/pull", data=json.dumps(data), callback=lambda data, model_name=model: self.pull_model_update(data, model_name))
        GLib.idle_add(self.update_list_local_models)

        if response['status'] == 'ok':
            GLib.idle_add(self.show_notification, _("Task Complete"), _("Model '{}' pulled successfully.").format(model), True, Gio.ThemedIcon.new("emblem-ok-symbolic"))
            GLib.idle_add(self.show_toast, "good", 1, self.manage_models_overlay)
            GLib.idle_add(self.pulling_models[model]['overlay'].get_parent().get_parent().remove, self.pulling_models[model]['overlay'].get_parent())
            del self.pulling_models[model]
        else:
            GLib.idle_add(self.show_notification, _("Pull Model Error"), _("Failed to pull model '{}' due to network error.").format(model), True, Gio.ThemedIcon.new("dialog-error-symbolic"))
            GLib.idle_add(self.pulling_models[model]['overlay'].get_parent().get_parent().remove, self.pulling_models[model]['overlay'].get_parent())
            del self.pulling_models[model]
            GLib.idle_add(self.manage_models_dialog.close)
            GLib.idle_add(self.connection_error)
        if len(list(self.pulling_models.keys())) == 0:
            GLib.idle_add(self.pulling_model_list_box.set_visible, False)

    def pull_model(self, model):
        if model in list(self.pulling_models.keys()):
            self.show_toast("info", 2, self.manage_models_overlay)
            return
        if model in self.local_models:
            self.show_toast("info", 3, self.manage_models_overlay)
            return
        self.pulling_model_list_box.set_visible(True)
        model_row = Adw.ActionRow(
            title = model
        )
        thread = threading.Thread(target=self.pull_model_process, kwargs={"model": model, "modelfile": None})
        overlay = Gtk.Overlay()
        progress_bar = Gtk.ProgressBar(
            valign = 2,
            show_text = False,
            margin_start = 10,
            margin_end = 10,
            css_classes = ["osd", "horizontal", "bottom"]
        )
        button = Gtk.Button(
            icon_name = "media-playback-stop-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["error"]
        )
        button.connect("clicked", lambda button, model_name=model : dialogs.stop_pull_model(self, model_name))
        model_row.add_suffix(button)
        self.pulling_models[model] = {"row": model_row, "progress_bar": progress_bar, "overlay": overlay}
        overlay.set_child(model_row)
        overlay.add_overlay(progress_bar)
        self.pulling_model_list_box.append(overlay)
        thread.start()

    def update_list_available_models(self):
        self.available_model_list_box.remove_all()
        for name, model_info in available_models.items():
            model = Adw.ActionRow(
                title = name,
                subtitle = "Image recognition" if model_info["image"] else None
            )
            link_button = Gtk.Button(
                icon_name = "globe-symbolic",
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
            pull_button.connect("clicked", lambda button=pull_button, model_name=name: dialogs.pull_model(self, model_name))
            model.add_suffix(link_button)
            model.add_suffix(pull_button)
            self.available_model_list_box.append(model)

    def save_history(self):
        with open(os.path.join(self.data_dir, "chats", "chats.json"), "w+") as f:
            json.dump(self.chats, f, indent=4)

    def load_history_into_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        for key, message in self.chats['chats'][self.chats["selected_chat"]]['messages'].items():
            if message:
                if message['role'] == 'user':
                    self.show_message(message['content'], False, f"\n\n<small>{message['date']}</small>", message['images'] if 'images' in message else None, message['files'] if 'files' in message else None, id=key)
                else:
                    self.show_message(message['content'], True, f"\n\n<small>{message['model']}\t|\t{message['date']}</small>", id=key)
                    self.add_code_blocks()
                    self.bot_message = None

    def load_history(self):
        if os.path.exists(os.path.join(self.data_dir, "chats", "chats.json")):
            try:
                with open(os.path.join(self.data_dir, "chats", "chats.json"), "r") as f:
                    self.chats = json.load(f)
                    if "selected_chat" not in self.chats or self.chats["selected_chat"] not in self.chats["chats"]: self.chats["selected_chat"] = list(self.chats["chats"].keys())[0]
                    if len(list(self.chats["chats"].keys())) == 0: self.chats["chats"][_("New Chat")] = {"messages": {}}
            except Exception as e:
                self.chats = {"chats": {_("New Chat"): {"messages": {}}}, "selected_chat": _("New Chat")}
            self.load_history_into_chat()

    def generate_numbered_name(self, chat_name:str, compare_list:list) -> str:
        if chat_name in compare_list:
            for i in range(len(compare_list)):
                if "." in chat_name:
                    if f"{'.'.join(chat_name.split('.')[:-1])} {i+1}.{chat_name.split('.')[-1]}" not in compare_list:
                        chat_name = f"{'.'.join(chat_name.split('.')[:-1])} {i+1}.{chat_name.split('.')[-1]}"
                        break
                else:
                    if  f"{chat_name} {i+1}" not in compare_list:
                        chat_name = f"{chat_name} {i+1}"
                        break
        return chat_name

    def generate_uuid(self) -> str:
        return f"{datetime.today().strftime('%Y%m%d%H%M%S%f')}{uuid.uuid4().hex}"

    def clear_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        self.chats["chats"][self.chats["selected_chat"]]["messages"] = []
        self.save_history()

    def delete_chat(self, chat_name):
        del self.chats['chats'][chat_name]
        if os.path.exists(os.path.join(self.data_dir, "chats", self.chats['selected_chat'])):
            shutil.rmtree(os.path.join(self.data_dir, "chats", self.chats['selected_chat']))
        self.save_history()
        self.update_chat_list()
        if len(self.chats['chats'])==0:
            self.new_chat()

    def rename_chat(self, old_chat_name, new_chat_name, label_element):
        new_chat_name = self.generate_numbered_name(new_chat_name, self.chats["chats"].keys())
        self.chats["chats"][new_chat_name] = self.chats["chats"][old_chat_name]
        del self.chats["chats"][old_chat_name]
        if os.path.exists(os.path.join(self.data_dir, "chats", old_chat_name)):
            shutil.move(os.path.join(self.data_dir, "chats", old_chat_name), os.path.join(self.data_dir, "chats", new_chat_name))
        label_element.set_label(new_chat_name)
        label_element.get_parent().set_name(new_chat_name)
        self.save_history()

    def new_chat(self):
        chat_name = self.generate_numbered_name(_("New Chat"), self.chats["chats"].keys())
        self.chats["chats"][chat_name] = {"messages": {}}
        self.save_history()
        self.new_chat_element(chat_name, True)

    def stop_pull_model(self, model_name):
        self.pulling_models[model_name]['overlay'].get_parent().get_parent().remove(self.pulling_models[model_name]['overlay'].get_parent())
        del self.pulling_models[model_name]

    def delete_model(self, model_name):
        response = connection_handler.simple_delete(f"{connection_handler.url}/api/delete", data={"name": model_name})
        self.update_list_local_models()
        if response['status'] == 'ok':
            self.show_toast("good", 0, self.manage_models_overlay)
        else:
            self.manage_models_dialog.close()
            self.connection_error()

    def new_chat_element(self, chat_name:str, select:bool):
        chat_content = Gtk.Box(
            spacing=6
        )
        chat_row = Gtk.ListBoxRow(
            css_classes = ["chat_row"],
            height_request = 45,
            child = chat_content,
            name = chat_name
        )
        chat_label = Gtk.Label(
            label=chat_name,
            hexpand=True,
            halign=0,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            xalign=0
        )

        button_delete = Gtk.Button(
            icon_name = "user-trash-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["error", "flat"]
        )
        button_delete.connect("clicked", lambda button, chat_name=chat_name: dialogs.delete_chat(self, chat_name))
        button_rename = Gtk.Button(
            icon_name = "document-edit-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["accent", "flat"]
        )
        chat_content.set_name(chat_name)
        button_rename.connect("clicked", lambda button, label_element=chat_label: dialogs.rename_chat(self, label_element))
        chat_content.append(chat_label)
        chat_content.append(button_delete)
        chat_content.append(button_rename)
        self.chat_list_box.append(chat_row)
        if select: self.chat_list_box.select_row(chat_row)

    def update_chat_list(self):
        self.chat_list_box.remove_all()
        for name, content in self.chats['chats'].items():
            self.new_chat_element(name, self.chats["selected_chat"] == name)

    def show_preferences_dialog(self):
        self.preferences_dialog.present(self)

    def connect_remote(self, url):
        connection_handler.url = url
        self.remote_url = connection_handler.url
        self.remote_connection_entry.set_text(self.remote_url)
        if self.verify_connection() == False: self.connection_error()

    def connect_local(self):
        self.run_remote = False
        connection_handler.url = f"http://127.0.0.1:{local_instance.port}"
        local_instance.start()
        if self.verify_connection() == False: self.connection_error()
        else: self.remote_connection_switch.set_active(False)

    def connection_error(self):
        if self.run_remote:
            dialogs.reconnect_remote(self, connection_handler.url)
        else:
            local_instance.reset()
            self.show_toast("error", 7, self.main_overlay)

    def connection_switched(self):
        new_value = self.remote_connection_switch.get_active()
        if new_value != self.run_remote:
            self.run_remote = new_value
            if self.run_remote:
                connection_handler.url = self.remote_url
                if self.verify_connection() == False: self.connection_error()
                else: local_instance.stop()
            else:
                connection_handler.url = f"http://127.0.0.1:{local_instance.port}"
                local_instance.start()
                if self.verify_connection() == False: self.connection_error()
            self.update_list_available_models()

    def on_replace_contents(self, file, result):
        file.replace_contents_finish(result)
        self.show_toast("good", 2, self.main_overlay)

    def on_export_current_chat(self, file_dialog, result):
        file = file_dialog.save_finish(result)
        if not file: return
        json_data = json.dumps({self.chats["selected_chat"]: self.chats["chats"][self.chats["selected_chat"]]}, indent=4).encode("UTF-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = os.path.join(temp_dir, "data.json")
            with open(json_path, "wb") as json_file:
                json_file.write(json_data)

            tar_path = os.path.join(temp_dir, f"{self.chats['selected_chat']}")
            with tarfile.open(tar_path, "w") as tar:
                tar.add(json_path, arcname="data.json")
                directory = os.path.join(self.data_dir, "chats", self.chats['selected_chat'])
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

    def export_current_chat(self):
        file_dialog = Gtk.FileDialog(initial_name=f"{self.chats['selected_chat']}.tar")
        file_dialog.save(parent=self, cancellable=None, callback=self.on_export_current_chat)

    def on_chat_imported(self, file_dialog, result):
        file = file_dialog.open_finish(result)
        if not file: return
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
                        with open(json_filepath, "r") as json_file:
                            data = json.load(json_file)
                        for chat_name, chat_content in data.items():
                            new_chat_name = self.generate_numbered_name(chat_name, list(self.chats['chats'].keys()))
                            self.chats['chats'][new_chat_name] = chat_content
                            src_path = os.path.join(temp_dir, chat_name)
                            if os.path.exists(src_path) and os.path.isdir(src_path):
                                dest_path = os.path.join(self.data_dir, "chats", new_chat_name)
                                shutil.copytree(src_path, dest_path)


        self.update_chat_list()
        self.save_history()
        self.show_toast("good", 3, self.main_overlay)

    def import_chat(self):
        file_dialog = Gtk.FileDialog(default_filter=self.file_filter_tar)
        file_dialog.open(self, None, self.on_chat_imported)

    def switch_run_on_background(self):
        self.run_on_background = self.background_switch.get_active()
        self.set_hide_on_close(self.run_on_background)
        self.verify_connection()

    def get_content_of_file(self, file_path, file_type):
        if not os.path.exists(file_path): return None
        if file_type == 'image':
            try:
                with Image.open(file_path) as img:
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
                    return base64.b64encode(image_data).decode("utf-8")
            except Exception as e:
                self.show_toast("error", 5, self.main_overlay)
        elif file_type == 'plain_text':
            with open(file_path, 'r') as f:
                return f.read()

    def remove_attached_file(self, button):
        del self.attachments[button.get_name()]
        button.get_parent().remove(button)
        if len(self.attachments) == 0: self.attachment_box.set_visible(False)

    def attach_file(self, file_path, file_type):
        name = self.generate_numbered_name(os.path.basename(file_path), self.attachments.keys())
        content = self.get_content_of_file(file_path, file_type)
        if content:
            shown_name='.'.join(name.split(".")[:-1])[:20] + (name[20:] and '..') + f".{name.split('.')[-1]}"

            button_content = Adw.ButtonContent(
                label=shown_name,
                icon_name={"image": "image-x-generic-symbolic", "plain_text": "document-text-symbolic"}[file_type]
            )
            button = Gtk.Button(
                vexpand=True,
                valign=3,
                name=name,
                css_classes=["flat"],
                tooltip_text=name,
                child=button_content
            )

            self.attachments[name] = {"path": file_path, "type": file_type, "content": content, "button": button}
            button.connect("clicked", lambda button: dialogs.remove_attached_file(self, button))
            self.attachment_container.append(button)
            self.attachment_box.set_visible(True)


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        if os.path.exists(os.path.join(self.config_dir, "chats.json")) and not os.path.exists(os.path.join(self.data_dir, "chats", "chats.json")):
            update_history.update(self)
        elif not os.path.exists(os.path.join(self.data_dir, "chats", "chats.json")):
            self.save_history()
        self.set_help_overlay(self.shortcut_window)
        self.get_application().set_accels_for_action("win.show-help-overlay", ['<primary>slash'])
        self.get_application().create_action('new_chat', lambda *_: self.new_chat(), ['<primary>n'])
        self.get_application().create_action('clear', lambda *_: dialogs.clear_chat(self), ['<primary>e'])
        self.get_application().create_action('send', lambda *_: self.send_message(self), ['Return'])
        self.get_application().create_action('export_current_chat', lambda *_: self.export_current_chat())
        self.get_application().create_action('import_chat', lambda *_: self.import_chat())
        self.get_application().create_action('create_model_from_existing', lambda *_: dialogs.create_model_from_existing(self))
        self.get_application().create_action('create_model_from_file', lambda *_: dialogs.create_model_from_file(self))
        self.get_application().create_action('attach_image', lambda *_: dialogs.attach_file(self, self.file_filter_image, "image"))
        self.get_application().create_action('attach_plain_text', lambda *_: dialogs.attach_file(self, self.file_filter_text, "plain_text"))
        self.add_chat_button.connect("clicked", lambda button : self.new_chat())

        self.create_model_name.get_delegate().connect("insert-text", self.check_alphanumeric)
        self.remote_connection_entry.connect("entry-activated", lambda entry : entry.set_css_classes([]))
        self.remote_connection_switch.connect("notify", lambda pspec, user_data : self.connection_switched())
        self.background_switch.connect("notify", lambda pspec, user_data : self.switch_run_on_background())
        if os.path.exists(os.path.join(self.config_dir, "server.json")):
            with open(os.path.join(self.config_dir, "server.json"), "r") as f:
                data = json.load(f)
                self.run_remote = data['run_remote']
                local_instance.port = data['local_port']
                self.remote_url = data['remote_url']
                self.run_on_background = data['run_on_background']
                #Model Tweaks
                if "model_tweaks" in data: self.model_tweaks = data['model_tweaks']
                self.temperature_spin.set_value(self.model_tweaks['temperature'])
                self.seed_spin.set_value(self.model_tweaks['seed'])
                self.keep_alive_spin.set_value(self.model_tweaks['keep_alive'])
                #Overrides
                if "ollama_overrides" in data: local_instance.overrides = data['ollama_overrides']
                for element in [
                        self.override_HSA_OVERRIDE_GFX_VERSION,
                        self.override_CUDA_VISIBLE_DEVICES,
                        self.override_HIP_VISIBLE_DEVICES]:
                    override = element.get_name()
                    if override in local_instance.overrides:
                        element.set_text(local_instance.overrides[override])


                self.background_switch.set_active(self.run_on_background)
                self.set_hide_on_close(self.run_on_background)
                self.remote_connection_entry.set_text(self.remote_url)
                if self.run_remote:
                    connection_handler.url = data['remote_url']
                    self.remote_connection_switch.set_active(True)
                else:
                    self.remote_connection_switch.set_active(False)
                    connection_handler.url = f"http://127.0.0.1:{local_instance.port}"
                    local_instance.start()
        else:
            local_instance.start()
            connection_handler.url = f"http://127.0.0.1:{local_instance.port}"
            self.welcome_dialog.present(self)
        if self.verify_connection() is False: self.connection_error()
        self.update_list_available_models()
        self.load_history()
        self.update_chat_list()
