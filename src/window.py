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
import json, requests, threading, os, re, base64, sys, gettext, locale, subprocess, uuid, shutil, tarfile, tempfile, logging
from time import sleep
from io import BytesIO
from PIL import Image
from pypdf import PdfReader
from datetime import datetime
from . import dialogs, local_instance, connection_handler, available_models_descriptions

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

    logger = logging.getLogger(__name__)
    logging.basicConfig(format="%(levelname)s\t[%(filename)s | %(funcName)s] %(message)s")
    logger.setLevel(logging.ERROR)

    #Variables
    editing_message = None
    available_models = None
    run_on_background = False
    remote_url = ""
    remote_bearer_token = ""
    run_remote = False
    model_tweaks = {"temperature": 0.7, "seed": 0, "keep_alive": 5}
    local_models = []
    pulling_models = {}
    chats = {"chats": {_("New Chat"): {"messages": {}}}, "selected_chat": "New Chat", "order": []}
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
    bot_message_button_container : Gtk.TextView = None
    file_preview_dialog = Gtk.Template.Child()
    file_preview_text_view = Gtk.Template.Child()
    file_preview_image = Gtk.Template.Child()
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
    attachment_container = Gtk.Template.Child()
    attachment_box = Gtk.Template.Child()
    file_filter_tar = Gtk.Template.Child()
    file_filter_gguf = Gtk.Template.Child()
    file_filter_attachments = Gtk.Template.Child()
    attachment_button = Gtk.Template.Child()
    model_drop_down = Gtk.Template.Child()
    model_string_list = Gtk.Template.Child()
    chat_right_click_menu = Gtk.Template.Child()
    model_tag_list_box = Gtk.Template.Child()
    navigation_view_manage_models = Gtk.Template.Child()
    file_preview_open_button = Gtk.Template.Child()
    file_preview_remove_button = Gtk.Template.Child()
    secondary_menu_button = Gtk.Template.Child()
    model_searchbar = Gtk.Template.Child()
    no_results_page = Gtk.Template.Child()
    model_link_button = Gtk.Template.Child()

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
    remote_bearer_token_entry = Gtk.Template.Child()

    style_manager = Adw.StyleManager()

    @Gtk.Template.Callback()
    def verify_if_image_can_be_used(self, pspec=None, user_data=None):
        if self.model_drop_down.get_selected_item() == None: return True
        selected = self.model_drop_down.get_selected_item().get_string().split(" (")[0].lower()
        if selected in [key for key, value in self.available_models.items() if value["image"]]:
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
        self.bot_message_button_container = None

    @Gtk.Template.Callback()
    def send_message(self, button=None):
        if self.editing_message:
            self.editing_message["button_container"].set_visible(True)
            self.editing_message["text_view"].set_css_classes(["flat"])
            self.editing_message["text_view"].set_cursor_visible(False)
            self.editing_message["text_view"].set_editable(False)
            buffer = self.editing_message["text_view"].get_buffer()
            text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).rstrip('\n')
            footer = "<small>" + self.editing_message["footer"] + "</small>"
            buffer.insert_markup(buffer.get_end_iter(), footer, len(footer))
            self.chats["chats"][self.chats["selected_chat"]]["messages"][self.editing_message["id"]]["content"] = text
            self.editing_message = None
            self.save_history()
            self.show_toast(_("Message edited successfully"), self.main_overlay)

        if self.bot_message or self.get_focus() not in (self.message_text_view, self.send_button): return
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False): return
        current_chat_row = self.chat_list_box.get_selected_row()
        self.chat_list_box.unselect_all()
        self.chat_list_box.remove(current_chat_row)
        self.chat_list_box.prepend(current_chat_row)
        self.chat_list_box.select_row(self.chat_list_box.get_row_at_index(0))
        self.chats['order'].remove(self.chats['selected_chat'])
        self.chats['order'].insert(0, self.chats['selected_chat'])
        self.save_history()
        current_model = self.model_drop_down.get_selected_item().get_string()
        current_model = current_model.replace(' (', ':')[:-1].lower()
        if current_model is None:
            self.show_toast(_("Please select a model before chatting"), self.main_overlay)
            return
        id = self.generate_uuid()

        attached_images = []
        attached_files = {}
        can_use_images = self.verify_if_image_can_be_used()
        for name, content in self.attachments.items():
            if content["type"] == 'image' and can_use_images: attached_images.append(name)
            else:
                attached_files[name] = content['type']
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
            "model": current_model,
            "messages": self.convert_history_to_ollama(),
            "options": {"temperature": self.model_tweaks["temperature"], "seed": self.model_tweaks["seed"]},
            "keep_alive": f"{self.model_tweaks['keep_alive']}m"
        }
        self.switch_send_stop_button()
        self.toggle_ui_sensitive(False)

        #self.attachments[name] = {"path": file_path, "type": file_type, "content": content}
        raw_message = self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        self.show_message(raw_message, False, f"\n\n<small>{formated_datetime}</small>", attached_images, attached_files, id=id)
        self.message_text_view.get_buffer().set_text("", 0)
        self.loading_spinner = Gtk.Spinner(spinning=True, margin_top=12, margin_bottom=12, hexpand=True)
        self.chat_container.append(self.loading_spinner)
        bot_id=self.generate_uuid()
        self.show_message("", True, id=bot_id)

        thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model'], bot_id))
        thread.start()
        if len(data['messages']) == 1:
            message_data = data["messages"][0].copy()
            message_data['content'] = raw_message
            generate_title_thread = threading.Thread(target=self.generate_chat_title, args=(message_data, self.chat_list_box.get_selected_row().get_child()))
            generate_title_thread.start()

    @Gtk.Template.Callback()
    def manage_models_button_activate(self, button=None):
        self.update_list_local_models()
        self.manage_models_dialog.present(self)

    @Gtk.Template.Callback()
    def welcome_carousel_page_changed(self, carousel, index):
        if index == 0: self.welcome_previous_button.set_sensitive(False)
        else: self.welcome_previous_button.set_sensitive(True)
        if index == carousel.get_n_pages()-1:
            self.welcome_next_button.set_label(_("Close"))
            self.welcome_next_button.set_tooltip_text(_("Close"))
        else:
            self.welcome_next_button.set_label(_("Next"))
            self.welcome_next_button.set_tooltip_text(_("Next"))

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
        if row and row.get_child().get_name() != self.chats["selected_chat"]:
            self.chats["selected_chat"] = row.get_child().get_name()
            self.load_history_into_chat()
            if len(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys()) > 0:
                for i in range(self.model_string_list.get_n_items()):
                    if self.model_string_list.get_string(i) == self.chats["chats"][self.chats["selected_chat"]]["messages"][list(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys())[-1]]["model"]:
                        self.model_drop_down.set_selected(i)
                        break
            self.save_history()

    @Gtk.Template.Callback()
    def change_remote_url(self, entry):
        self.remote_url = entry.get_text()
        if self.run_remote:
            connection_handler.url = self.remote_url
            if self.verify_connection() == False:
                entry.set_css_classes(["error"])
                self.show_toast(_("Failed to connect to server"), self.preferences_dialog)

    @Gtk.Template.Callback()
    def change_remote_bearer_token(self, entry):
        self.remote_bearer_token = entry.get_text()
        self.save_server_config()
        return
        if self.remote_url and self.run_remote:
            connection_handler.url = self.remote_url
            if self.verify_connection() == False:
                entry.set_css_classes(["error"])
                self.show_toast(_("Failed to connect to server"), self.preferences_dialog)

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
            css_classes = ["error"],
            tooltip_text = _("Stop Creating '{}'").format(name)
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
        os.system(f'xdg-open "{button.get_name()}"'.replace("{selected_chat}", self.chats["selected_chat"]))

    @Gtk.Template.Callback()
    def model_search_toggle(self, button):
        self.model_searchbar.set_search_mode(button.get_active())
        self.pulling_model_list_box.set_visible(not button.get_active() and len(self.pulling_models) > 0)
        self.local_model_list_box.set_visible(not button.get_active())

    @Gtk.Template.Callback()
    def model_search_changed(self, entry):
        results = 0
        for i, key in enumerate(self.available_models.keys()):
            row = self.available_model_list_box.get_row_at_index(i)
            row.set_visible(re.search(entry.get_text(), '{} {} {}'.format(row.get_title(), (_("image") if self.available_models[key]['image'] else " "), row.get_subtitle()), re.IGNORECASE))
            if row.get_visible(): results += 1
        if entry.get_text() and results == 0:
            self.available_model_list_box.set_visible(False)
            self.no_results_page.set_visible(True)
        else:
            self.available_model_list_box.set_visible(True)
            self.no_results_page.set_visible(False)


    def check_alphanumeric(self, editable, text, length, position):
        new_text = ''.join([char for char in text if char.isalnum() or char in ['-', '_']])
        if new_text != text: editable.stop_emission_by_name("insert-text")

    def create_model(self, model:str, file:bool):
        name = ""
        system = ""
        template = ""
        if not file:
            response = connection_handler.simple_post(f"{connection_handler.url}/api/show", json.dumps({"name": model}))
            if response.status_code == 200:
                data = json.loads(response.text)

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


    def show_toast(self, message:str, overlay):
        toast = Adw.Toast(
            title=message,
            timeout=2
        )
        overlay.add_toast(toast)

    def show_notification(self, title:str, body:str, icon:Gio.ThemedIcon=None):
        if not self.is_active():
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
        self.show_toast(_("Message copied to the clipboard"), self.main_overlay)

    def edit_message(self, message_element, text_view, button_container):
        if self.editing_message: self.send_message()

        button_container.set_visible(False)
        id = message_element.get_name()

        text_buffer = text_view.get_buffer()
        end_iter = text_buffer.get_end_iter()
        start_iter = end_iter.copy()
        start_iter.backward_line()
        start_iter.backward_char()
        footer = text_buffer.get_text(start_iter, end_iter, False)
        text_buffer.delete(start_iter, end_iter)

        text_view.set_editable(True)
        text_view.set_css_classes(["view", "editing_message_textview"])
        text_view.set_cursor_visible(True)

        self.editing_message = {"text_view": text_view, "id": id, "button_container": button_container, "footer": footer}

    def preview_file(self, file_path, file_type, presend_name):
        file_path = file_path.replace("{selected_chat}", self.chats["selected_chat"])
        content = self.get_content_of_file(file_path, file_type)
        if presend_name:
            self.file_preview_remove_button.set_visible(True)
            self.file_preview_remove_button.set_name(presend_name)
        else:
            self.file_preview_remove_button.set_visible(False)
        if content:
            if file_type == 'image':
                self.file_preview_image.set_visible(True)
                self.file_preview_text_view.set_visible(False)
                image_data = base64.b64decode(content)
                loader = GdkPixbuf.PixbufLoader.new()
                loader.write(image_data)
                loader.close()
                pixbuf = loader.get_pixbuf()
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self.file_preview_image.set_from_paintable(texture)
                self.file_preview_image.set_size_request(240, 240)
                self.file_preview_dialog.set_title(os.path.basename(file_path))
                self.file_preview_open_button.set_name(file_path)
            else:
                self.file_preview_image.set_visible(False)
                self.file_preview_text_view.set_visible(True)
                buffer = self.file_preview_text_view.get_buffer()
                buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
                buffer.insert(buffer.get_start_iter(), content, len(content))
                if file_type == 'youtube':
                    self.file_preview_dialog.set_title(content.split('\n')[0])
                    self.file_preview_open_button.set_name(content.split('\n')[2])
                elif file_type == 'website':
                    self.file_preview_open_button.set_name(content.split('\n')[0])
                else:
                    self.file_preview_dialog.set_title(os.path.basename(file_path))
                    self.file_preview_open_button.set_name(file_path)
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

    def generate_chat_title(self, message, label_element):
        prompt = f"""
Generate a title following these rules:
    - The title should be based on the prompt at the end
    - Keep it in the same language as the prompt
    - The title needs to be less than 30 characters
    - Use only alphanumeric characters and spaces
    - Just write the title, NOTHING ELSE

```PROMPT
{message['content']}
```"""
        current_model = self.model_drop_down.get_selected_item().get_string()
        current_model = current_model.replace(' (', ':')[:-1].lower()
        data = {"model": current_model, "prompt": prompt, "stream": False}
        if 'images' in message: data["images"] = message['images']
        response = connection_handler.simple_post(f"{connection_handler.url}/api/generate", data=json.dumps(data))
        new_chat_name = json.loads(response.text)["response"].strip().removeprefix("Title: ").removeprefix("title: ").strip('\'"').title()
        new_chat_name = new_chat_name[:50] + (new_chat_name[50:] and '...')
        self.rename_chat(label_element.get_name(), new_chat_name, label_element)

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
            cursor_visible=False,
            css_classes=["flat"],
        )
        message_buffer = message_text.get_buffer()
        message_buffer.insert(message_buffer.get_end_iter(), msg)
        if footer is not None: message_buffer.insert_markup(message_buffer.get_end_iter(), footer, len(footer))

        delete_button = Gtk.Button(
            icon_name = "user-trash-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Remove Message")
        )
        copy_button = Gtk.Button(
            icon_name = "edit-copy-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Copy Message")
        )
        edit_button = Gtk.Button(
            icon_name = "edit-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Edit Message")
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
            css_classes=[None if bot else "card"]
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
                path = os.path.join(self.data_dir, "chats", self.chats['selected_chat'], id, image)
                try:
                    if not os.path.isfile(path):
                        raise FileNotFoundError("'{}' was not found or is a directory".format(path))
                    image_element = Gtk.Image.new_from_file(path)
                    image_element.set_size_request(240, 240)
                    button = Gtk.Button(
                        child=image_element,
                        css_classes=["flat", "chat_image_button"],
                        name=os.path.join(self.data_dir, "chats", "{selected_chat}", id, image),
                        tooltip_text=os.path.basename(path)
                    )
                    button.connect("clicked", lambda button, file_path=path: self.preview_file(file_path, 'image', None))
                except Exception as e:
                    self.logger.error(e)
                    image_texture = Gtk.Image.new_from_icon_name("image-missing-symbolic")
                    image_texture.set_icon_size(2)
                    image_texture.set_vexpand(True)
                    image_texture.set_pixel_size(120)
                    image_label = Gtk.Label(
                        label=_("Missing Image"),
                    )
                    image_box = Gtk.Box(
                        spacing=10,
                        orientation=1,
                        margin_top=10,
                        margin_bottom=10,
                        margin_start=10,
                        margin_end=10
                    )
                    image_box.append(image_texture)
                    image_box.append(image_label)
                    image_box.set_size_request(220, 220)
                    button = Gtk.Button(
                        child=image_box,
                        css_classes=["flat", "chat_image_button"],
                        tooltip_text=_("Missing image")
                    )
                    button.connect("clicked", lambda button : self.show_toast(_("Missing image"), self.main_overlay))
                image_container.append(button)
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
                button_content = Adw.ButtonContent(
                    label=name,
                    icon_name={
                        "plain_text": "document-text-symbolic",
                        "pdf": "document-text-symbolic",
                        "youtube": "play-symbolic",
                        "website": "globe-symbolic"
                    }[file_type]
                )
                button = Gtk.Button(
                    vexpand=False,
                    valign=3,
                    name=name,
                    css_classes=["flat"],
                    tooltip_text=name,
                    child=button_content
                )
                file_path = os.path.join(self.data_dir, "chats", "{selected_chat}", id, name)
                button.connect("clicked", lambda button, file_path=file_path, file_type=file_type: self.preview_file(file_path, file_type, None))
                file_container.append(button)
            message_box.append(file_scroller)

        message_box.append(message_text)
        overlay = Gtk.Overlay(css_classes=["message"], name=id)
        overlay.set_child(message_box)

        delete_button.connect("clicked", lambda button, element=overlay: self.delete_message(element))
        copy_button.connect("clicked", lambda button, element=overlay: self.copy_message(element))
        edit_button.connect("clicked", lambda button, element=overlay, textview=message_text, button_container=button_container: self.edit_message(element, textview, button_container))
        button_container.append(delete_button)
        button_container.append(copy_button)
        if not bot: button_container.append(edit_button)
        overlay.add_overlay(button_container)
        self.chat_container.append(overlay)

        if bot:
            self.bot_message = message_buffer
            self.bot_message_view = message_text
            self.bot_message_box = message_box
            self.bot_message_button_container = button_container

    def update_list_local_models(self):
        self.local_models = []
        response = connection_handler.simple_get(f"{connection_handler.url}/api/tags")
        for i in range(self.model_string_list.get_n_items() -1, -1, -1):
            self.model_string_list.remove(i)
        if response.status_code == 200:
            self.local_model_list_box.remove_all()
            if len(json.loads(response.text)['models']) == 0:
                self.local_model_list_box.set_visible(False)
            else:
                self.local_model_list_box.set_visible(True)
            for model in json.loads(response.text)['models']:
                model_row = Adw.ActionRow(
                    title = "<b>{}</b>".format(model["name"].split(":")[0].replace("-", " ").title()),
                    subtitle = model["name"].split(":")[1]
                )
                button = Gtk.Button(
                    icon_name = "user-trash-symbolic",
                    vexpand = False,
                    valign = 3,
                    css_classes = ["error", "circular"],
                    tooltip_text = _("Remove '{} ({})'").format(model["name"].split(":")[0].replace('-', ' ').title(), model["name"].split(":")[1])
                )
                button.connect("clicked", lambda button=button, model_name=model["name"]: dialogs.delete_model(self, model_name))
                model_row.add_suffix(button)
                self.local_model_list_box.append(model_row)

                self.model_string_list.append(f"{model['name'].split(':')[0].replace('-', ' ').title()} ({model['name'].split(':')[1]})")
                self.local_models.append(model["name"])
            self.model_drop_down.set_selected(0)
            self.verify_if_image_can_be_used()
            return
        else:
            self.connection_error()

    def save_server_config(self):
        with open(os.path.join(self.config_dir, "server.json"), "w+") as f:
            json.dump({'remote_url': self.remote_url, 'remote_bearer_token': self.remote_bearer_token, 'run_remote': self.run_remote, 'local_port': local_instance.port, 'run_on_background': self.run_on_background, 'model_tweaks': self.model_tweaks, 'ollama_overrides': local_instance.overrides}, f, indent=6)

    def verify_connection(self):
        response = connection_handler.simple_get(connection_handler.url)
        if response.status_code == 200:
            if "Ollama is running" in response.text:
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
                copy_button = Gtk.Button(icon_name="edit-copy-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Copy Message"))
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
        self.show_toast(_("Code copied to the clipboard"), self.main_overlay)

    def update_bot_message(self, data, id):
        if self.bot_message is None:
            self.save_history()
            sys.exit()
        vadjustment = self.chat_window.get_vadjustment()
        if id not in self.chats["chats"][self.chats["selected_chat"]]["messages"] or vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
            GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
        if data['done']:
            date = datetime.strptime(self.chats["chats"][self.chats["selected_chat"]]["messages"][id]["date"], '%Y/%m/%d %H:%M:%S')
            formated_date = GLib.DateTime.new(GLib.DateTime.new_now_local().get_timezone(), date.year, date.month, date.day, date.hour, date.minute, date.second).format("%c")
            text = f"\n\n<small>{data['model'].split(':')[0].replace('-', ' ').title()} ({data['model'].split(':')[1]})\t\t{formated_date}</small>"
            GLib.idle_add(self.bot_message.insert_markup, self.bot_message.get_end_iter(), text, len(text))
            self.save_history()
            GLib.idle_add(self.bot_message_button_container.set_visible, True)
            #Notification
            first_paragraph = self.bot_message.get_text(self.bot_message.get_start_iter(), self.bot_message.get_end_iter(), False).split("\n")[0]
            GLib.idle_add(self.show_notification, self.chats["selected_chat"], first_paragraph[:100] + (first_paragraph[100:] and '...'), Gio.ThemedIcon.new("chat-message-new-symbolic"))
        else:
            if id not in self.chats["chats"][self.chats["selected_chat"]]["messages"]:
                GLib.idle_add(self.chat_container.remove, self.loading_spinner)
                self.loading_spinner = None
                self.chats["chats"][self.chats["selected_chat"]]["messages"][id] = {
                    "role": "assistant",
                    "model": data['model'],
                    "date": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                    "content": ''
                }
            GLib.idle_add(self.bot_message.insert, self.bot_message.get_end_iter(), data['message']['content'])
            self.chats["chats"][self.chats["selected_chat"]]["messages"][id]['content'] += data['message']['content']

    def toggle_ui_sensitive(self, status):
        for element in [self.chat_list_box, self.add_chat_button, self.secondary_menu_button]:
            element.set_sensitive(status)

    def switch_send_stop_button(self):
        self.stop_button.set_visible(self.send_button.get_visible())
        self.send_button.set_visible(not self.send_button.get_visible())

    def run_message(self, messages, model, id):
        self.bot_message_button_container.set_visible(False)
        response = connection_handler.stream_post(f"{connection_handler.url}/api/chat", data=json.dumps({"model": model, "messages": messages}), callback=lambda data, id=id: self.update_bot_message(data, id))
        GLib.idle_add(self.add_code_blocks)
        GLib.idle_add(self.switch_send_stop_button)
        GLib.idle_add(self.toggle_ui_sensitive, True)
        if self.loading_spinner:
            GLib.idle_add(self.chat_container.remove, self.loading_spinner)
            self.loading_spinner = None
        if response.status_code != 200:
            GLib.idle_add(self.connection_error)

    def pull_model_update(self, data, model_name):
        if model_name in list(self.pulling_models.keys()):
            if 'completed' in data and 'total' in data:
                GLib.idle_add(self.pulling_models[model_name]['row'].set_subtitle, '<tt>{}%</tt>\t{}'.format(round(data['completed'] / data['total'] * 100, 2), data['status'].capitalize()))
                GLib.idle_add(self.pulling_models[model_name]['progress_bar'].set_fraction, (data['completed'] / data['total']))
            else:
                GLib.idle_add(self.pulling_models[model_name]['row'].set_subtitle, '{}'.format(data['status'].capitalize()))
                GLib.idle_add(self.pulling_models[model_name]['progress_bar'].pulse)
        else:
            if len(list(self.pulling_models.keys())) == 0:
                GLib.idle_add(self.pulling_model_list_box.set_visible, False)

    def pull_model_process(self, model, modelfile):
        if modelfile:
            data = {"name": model, "modelfile": modelfile}
            response = connection_handler.stream_post(f"{connection_handler.url}/api/create", data=json.dumps(data), callback=lambda data, model_name=model: self.pull_model_update(data, model_name))
        else:
            data = {"name": model}
            response = connection_handler.stream_post(f"{connection_handler.url}/api/pull", data=json.dumps(data), callback=lambda data, model_name=model: self.pull_model_update(data, model_name))
        GLib.idle_add(self.update_list_local_models)

        if response.status_code == 200:
            GLib.idle_add(self.show_notification, _("Task Complete"), _("Model '{}' pulled successfully.").format(model), Gio.ThemedIcon.new("emblem-ok-symbolic"))
            GLib.idle_add(self.show_toast, "good", 1, self.manage_models_overlay)
            GLib.idle_add(self.pulling_models[model]['overlay'].get_parent().get_parent().remove, self.pulling_models[model]['overlay'].get_parent())
            del self.pulling_models[model]
        else:
            GLib.idle_add(self.show_notification, _("Pull Model Error"), _("Failed to pull model '{}' due to network error.").format(model), Gio.ThemedIcon.new("dialog-error-symbolic"))
            GLib.idle_add(self.pulling_models[model]['overlay'].get_parent().get_parent().remove, self.pulling_models[model]['overlay'].get_parent())
            del self.pulling_models[model]
            GLib.idle_add(self.manage_models_dialog.close)
            GLib.idle_add(self.connection_error)
        if len(list(self.pulling_models.keys())) == 0:
            GLib.idle_add(self.pulling_model_list_box.set_visible, False)

    def pull_model(self, model):
        if model in list(self.pulling_models.keys()) or model in self.local_models:
            return
        self.pulling_model_list_box.set_visible(True)
        #self.pulling_model_list_box.connect('row_selected', lambda list_box, row: dialogs.stop_pull_model(self, row.get_name()) if row else None) #It isn't working for some reason
        model_row = Adw.ActionRow(
            title = "<b>{}</b> <small>{}</small>".format(model.split(":")[0].replace("-", " ").title(), model.split(":")[1]),
            name = model
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
            css_classes = ["error", "circular"],
            tooltip_text = _("Stop Pulling '{} ({})'").format(model.split(':')[0].replace('-', ' ').title(), model.split(':')[1])
        )
        button.connect("clicked", lambda button, model_name=model : dialogs.stop_pull_model(self, model_name))
        model_row.add_suffix(button)
        self.pulling_models[model] = {"row": model_row, "progress_bar": progress_bar, "overlay": overlay}
        overlay.set_child(model_row)
        overlay.add_overlay(progress_bar)
        self.pulling_model_list_box.append(overlay)
        thread.start()

    def confirm_pull_model(self, model_name):
        self.navigation_view_manage_models.pop()
        self.model_tag_list_box.unselect_all()
        self.pull_model(model_name)

    def list_available_model_tags(self, model_name):
        self.navigation_view_manage_models.push_by_tag('model_tags_page')
        self.navigation_view_manage_models.find_page('model_tags_page').set_title(model_name.capitalize())
        self.model_link_button.set_name(self.available_models[model_name]['url'])
        self.model_link_button.set_tooltip_text(self.available_models[model_name]['url'])
        self.available_model_list_box.unselect_all()
        self.model_tag_list_box.connect('row_selected', lambda list_box, row: self.confirm_pull_model(row.get_name()) if row else None)
        self.model_tag_list_box.remove_all()
        tags = self.available_models[model_name]['tags']
        for tag_data in tags:
            if f"{model_name}:{tag_data[0]}" not in self.local_models:
                tag_row = Adw.ActionRow(
                    title = tag_data[0],
                    subtitle = tag_data[1],
                    name = f"{model_name}:{tag_data[0]}"
                )
                tag_row.add_suffix(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
                self.model_tag_list_box.append(tag_row)

    def update_list_available_models(self):
        self.available_model_list_box.connect('row_selected', lambda list_box, row: self.list_available_model_tags(row.get_name()) if row else None)
        self.available_model_list_box.remove_all()
        for name, model_info in self.available_models.items():
            model = Adw.ActionRow(
                title = "<b>{}</b> <small>by {}</small>".format(name.replace("-", " ").title(), model_info['author']),
                subtitle = available_models_descriptions.descriptions[name] + ("\n\n<b>{}</b>".format(_("Image Recognition")) if model_info['image'] else ""),
                name = name
            )
            if model_info["image"]:
                image_icon = Gtk.Image.new_from_icon_name("image-x-generic-symbolic")
                image_icon.set_margin_start(5)
                #model.add_suffix(image_icon)
            next_icon = Gtk.Image.new_from_icon_name("go-next")
            next_icon.set_margin_start(5)
            model.add_suffix(next_icon)
            self.available_model_list_box.append(model)

    def save_history(self):
        with open(os.path.join(self.data_dir, "chats", "chats.json"), "w+") as f:
            json.dump(self.chats, f, indent=4)

    def load_history_into_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        for key, message in self.chats['chats'][self.chats["selected_chat"]]['messages'].items():
            if message:
                date = datetime.strptime(message['date'] + (":00" if message['date'].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S')
                formated_date = GLib.DateTime.new(GLib.DateTime.new_now_local().get_timezone(), date.year, date.month, date.day, date.hour, date.minute, date.second).format("%c")
                if message['role'] == 'user':
                    self.show_message(message['content'], False, f"\n\n<small>{formated_date}</small>", message['images'] if 'images' in message else None, message['files'] if 'files' in message else None, id=key)
                else:
                    self.show_message(message['content'], True, f"\n\n<small>{message['model'].split(':')[0].replace('-', ' ').title()} ({message['model'].split(':')[1]})\n{formated_date}</small>", id=key)
                    self.add_code_blocks()
                    self.bot_message = None

    def load_history(self):
        if os.path.exists(os.path.join(self.data_dir, "chats", "chats.json")):
            try:
                with open(os.path.join(self.data_dir, "chats", "chats.json"), "r") as f:
                    self.chats = json.load(f)
                    if len(list(self.chats["chats"].keys())) == 0: self.chats["chats"][_("New Chat")] = {"messages": {}}
                    if "selected_chat" not in self.chats or self.chats["selected_chat"] not in self.chats["chats"]: self.chats["selected_chat"] = list(self.chats["chats"].keys())[0]
                    if "order" not in self.chats:
                        self.chats["order"] = []
                        for chat_name in self.chats["chats"].keys():
                            self.chats["order"].append(chat_name)
            except Exception as e:
                self.logger.error(e)
                self.chats = {"chats": {}, "selected_chat": None, "order": []}
                self.new_chat()
        else:
            self.chats = {"chats": {}, "selected_chat": None, "order": []}
            self.new_chat()
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
        self.chats['order'].remove(chat_name)
        if os.path.exists(os.path.join(self.data_dir, "chats", self.chats['selected_chat'])):
            shutil.rmtree(os.path.join(self.data_dir, "chats", self.chats['selected_chat']))
        self.save_history()
        self.update_chat_list()
        if len(self.chats['chats'])==0:
            self.new_chat()
        if self.chats['selected_chat'] == chat_name:
            self.chat_list_box.select_row(self.chat_list_box.get_row_at_index(0))

    def rename_chat(self, old_chat_name, new_chat_name, label_element):
        new_chat_name = self.generate_numbered_name(new_chat_name, self.chats["chats"].keys())
        if self.chats["selected_chat"] == old_chat_name: self.chats["selected_chat"] = new_chat_name
        self.chats["chats"][new_chat_name] = self.chats["chats"][old_chat_name]
        self.chats["order"][self.chats["order"].index(old_chat_name)] = new_chat_name
        del self.chats["chats"][old_chat_name]
        if os.path.exists(os.path.join(self.data_dir, "chats", old_chat_name)):
            shutil.move(os.path.join(self.data_dir, "chats", old_chat_name), os.path.join(self.data_dir, "chats", new_chat_name))
        label_element.set_tooltip_text(new_chat_name)
        label_element.set_label(new_chat_name)
        label_element.set_name(new_chat_name)
        self.save_history()

    def new_chat(self):
        chat_name = self.generate_numbered_name(_("New Chat"), self.chats["chats"].keys())
        self.chats["chats"][chat_name] = {"messages": {}}
        self.chats["order"].insert(0, chat_name)
        self.save_history()
        self.new_chat_element(chat_name, True, False)

    def stop_pull_model(self, model_name):
        self.pulling_models[model_name]['overlay'].get_parent().get_parent().remove(self.pulling_models[model_name]['overlay'].get_parent())
        del self.pulling_models[model_name]

    def delete_model(self, model_name):
        response = connection_handler.simple_delete(f"{connection_handler.url}/api/delete", data={"name": model_name})
        self.update_list_local_models()
        if response.status_code == 200:
            self.show_toast(_("Model deleted successfully"), self.manage_models_overlay)
        else:
            self.manage_models_dialog.close()
            self.connection_error()

    def chat_click_handler(self, gesture, n_press, x, y):
        chat_row = gesture.get_widget()
        popover = Gtk.PopoverMenu(
            menu_model=self.chat_right_click_menu,
            has_arrow=False,
            halign=1,
        )
        self.selected_chat_row = chat_row
        position = Gdk.Rectangle()
        position.x = x
        position.y = y
        popover.set_parent(chat_row.get_child())
        popover.set_pointing_to(position)
        popover.popup()

    def new_chat_element(self, chat_name:str, select:bool, append:bool):
        chat_label = Gtk.Label(
            label=chat_name,
            tooltip_text=chat_name,
            name=chat_name,
            hexpand=True,
            halign=0,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            xalign=0
        )
        chat_row = Gtk.ListBoxRow(
            css_classes = ["chat_row"],
            height_request = 45,
            child = chat_label
        )

        gesture = Gtk.GestureClick(button=3)
        gesture.connect("released", self.chat_click_handler)
        chat_row.add_controller(gesture)

        if append: self.chat_list_box.append(chat_row)
        else: self.chat_list_box.prepend(chat_row)
        if select: self.chat_list_box.select_row(chat_row)

    def update_chat_list(self):
        self.chat_list_box.remove_all()
        for name in self.chats['order']:
            if name in self.chats['chats'].keys():
                self.new_chat_element(name, self.chats["selected_chat"] == name, True)

    def show_preferences_dialog(self):
        self.preferences_dialog.present(self)

    def connect_remote(self, url):
        connection_handler.url = url
        self.remote_url = connection_handler.url
        self.remote_connection_entry.set_text(self.remote_url)
        if self.verify_connection() == False: self.connection_error()

    def connect_local(self):
        self.run_remote = False
        connection_handler.bearer_token = None
        connection_handler.url = f"http://127.0.0.1:{local_instance.port}"
        local_instance.start()
        if self.verify_connection() == False: self.connection_error()
        else: self.remote_connection_switch.set_active(False)

    def connection_error(self):
        if self.run_remote:
            dialogs.reconnect_remote(self, connection_handler.url)
        else:
            local_instance.reset()
            self.show_toast(_("There was an error with the local Ollama instance, so it has been reset"), self.main_overlay)

    def connection_switched(self):
        new_value = self.remote_connection_switch.get_active()
        if new_value != self.run_remote:
            self.run_remote = new_value
            if self.run_remote:
                connection_handler.bearer_token = self.remote_bearer_token
                connection_handler.url = self.remote_url
                if self.verify_connection() == False: self.connection_error()
                else: local_instance.stop()
            else:
                connection_handler.bearer_token = None
                connection_handler.url = f"http://127.0.0.1:{local_instance.port}"
                local_instance.start()
                if self.verify_connection() == False: self.connection_error()

    def on_replace_contents(self, file, result):
        file.replace_contents_finish(result)
        self.show_toast(_("Chat exported successfully"), self.main_overlay)

    def on_export_chat(self, file_dialog, result, chat_name):
        file = file_dialog.save_finish(result)
        if not file: return
        json_data = json.dumps({chat_name: self.chats["chats"][chat_name]}, indent=4).encode("UTF-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = os.path.join(temp_dir, "data.json")
            with open(json_path, "wb") as json_file:
                json_file.write(json_data)

            tar_path = os.path.join(temp_dir, chat_name)
            with tarfile.open(tar_path, "w") as tar:
                tar.add(json_path, arcname="data.json")
                directory = os.path.join(self.data_dir, "chats", chat_name)
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

    def export_chat(self, chat_name):
        file_dialog = Gtk.FileDialog(initial_name=f"{chat_name}.tar")
        file_dialog.save(parent=self, cancellable=None, callback=lambda file_dialog, result, chat_name=chat_name: self.on_export_chat(file_dialog, result, chat_name))

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
        self.show_toast(_("Chat imported successfully"), self.main_overlay)

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
                self.logger.error(e)
                self.show_toast(_("Cannot open image"), self.main_overlay)
        elif file_type == 'plain_text' or file_type == 'youtube' or file_type == 'website':
            with open(file_path, 'r') as f:
                return f.read()
        elif file_type == 'pdf':
            reader = PdfReader(file_path)
            if len(reader.pages) == 0: return None
            text = ""
            for i, page in enumerate(reader.pages):
                text += f"\n- Page {i}\n{page.extract_text(extraction_mode='layout', layout_mode_space_vertically=False)}\n"
            return text

    def remove_attached_file(self, name):
        button = self.attachments[name]['button']
        button.get_parent().remove(button)
        del self.attachments[name]
        if len(self.attachments) == 0: self.attachment_box.set_visible(False)

    def attach_file(self, file_path, file_type):
        file_name = self.generate_numbered_name(os.path.basename(file_path), self.attachments.keys())
        content = self.get_content_of_file(file_path, file_type)
        if content:
            button_content = Adw.ButtonContent(
                label=file_name,
                icon_name={
                    "image": "image-x-generic-symbolic",
                    "plain_text": "document-text-symbolic",
                    "pdf": "document-text-symbolic",
                    "youtube": "play-symbolic",
                    "website": "globe-symbolic"
                }[file_type]
            )
            button = Gtk.Button(
                vexpand=True,
                valign=3,
                name=file_name,
                css_classes=["flat"],
                tooltip_text=file_name,
                child=button_content
            )
            self.attachments[file_name] = {"path": file_path, "type": file_type, "content": content, "button": button}
            #button.connect("clicked", lambda button: dialogs.remove_attached_file(self, button))
            button.connect("clicked", lambda button : self.preview_file(file_path, file_type, file_name))
            self.attachment_container.append(button)
            self.attachment_box.set_visible(True)

    def chat_actions(self, action, user_data):
        chat_row = self.selected_chat_row
        chat_name = chat_row.get_child().get_name()
        action_name = action.get_name()
        if action_name == 'delete_chat':
            dialogs.delete_chat(self, chat_name)
        elif action_name in ('rename_chat', 'rename_current_chat'):
            dialogs.rename_chat(self, chat_name, chat_row.get_child())
        elif action_name in ('export_chat', 'export_current_chat'):
            self.export_chat(chat_name)

    def current_chat_actions(self, action, user_data):
        self.selected_chat_row = self.chat_list_box.get_selected_row()
        self.chat_actions(action, user_data)

    def cb_text_received(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            #Check if text is a Youtube URL
            youtube_regex = re.compile(
                r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
                r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
            url_regex = re.compile(
                r'http[s]?://'
                r'(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|'
                r'(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                r'(?:\\:[0-9]{1,5})?'
                r'(?:/[^\\s]*)?'
            )
            if youtube_regex.match(text):
                try:
                    dialogs.youtube_caption(self, text)
                except Exception as e:
                    self.logger.error(e)
                    self.show_toast(_("This video is not available"), self.main_overlay)
            elif url_regex.match(text):
                dialogs.attach_website(self, text)
        except Exception as e:
            self.logger.error(e)

    def cb_image_received(self, clipboard, result):
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                if self.verify_if_image_can_be_used():
                    pixbuf = Gdk.pixbuf_get_from_texture(texture)
                    if not os.path.exists(os.path.join(self.cache_dir, 'tmp/images/')):
                        os.makedirs(os.path.join(self.cache_dir, 'tmp/images/'))
                    image_name = self.generate_numbered_name('image.png', os.listdir(os.path.join(self.cache_dir, os.path.join(self.cache_dir, 'tmp/images'))))
                    pixbuf.savev(os.path.join(self.cache_dir, 'tmp/images/{}'.format(image_name)), "png", [], [])
                    self.attach_file(os.path.join(self.cache_dir, 'tmp/images/{}'.format(image_name)), 'image')
                else:
                    self.show_toast(_("Image recognition is only available on specific models"), self.main_overlay)
        except Exception as e: 'huh'

    def on_clipboard_paste(self, textview):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self.cb_text_received)
        clipboard.read_texture_async(None, self.cb_image_received)


    def on_model_dropdown_setup(self, factory, list_item):
        label = Gtk.Label()
        label.set_ellipsize(2)
        label.set_xalign(0)
        list_item.set_child(label)

    def on_model_dropdown_bind(self, factory, list_item):
        label = list_item.get_child()
        item = list_item.get_item()
        label.set_text(item.get_string())
        label.set_tooltip_text(item.get_string())

    def setup_model_dropdown(self):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.on_model_dropdown_setup)
        factory.connect("bind", self.on_model_dropdown_bind)
        self.model_drop_down.set_factory(factory)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        with open('/app/share/Alpaca/alpaca/available_models.json', 'r') as f:
            self.available_models = json.load(f)
        if not os.path.exists(os.path.join(self.data_dir, "chats")):
            os.makedirs(os.path.join(self.data_dir, "chats"))
        self.set_help_overlay(self.shortcut_window)
        self.get_application().set_accels_for_action("win.show-help-overlay", ['<primary>slash'])
        self.get_application().create_action('new_chat', lambda *_: self.new_chat(), ['<primary>n'])
        self.get_application().create_action('clear', lambda *_: dialogs.clear_chat(self), ['<primary>e'])
        self.get_application().create_action('send', lambda *_: self.send_message(self), ['Return'])
        self.get_application().create_action('import_chat', lambda *_: self.import_chat(), ['<primary>i'])
        self.get_application().create_action('create_model_from_existing', lambda *_: dialogs.create_model_from_existing(self))
        self.get_application().create_action('create_model_from_file', lambda *_: dialogs.create_model_from_file(self))
        self.get_application().create_action('delete_chat', self.chat_actions)
        self.get_application().create_action('rename_chat', self.chat_actions)
        self.get_application().create_action('rename_current_chat', self.current_chat_actions)
        self.get_application().create_action('export_chat', self.chat_actions)
        self.get_application().create_action('export_current_chat', self.current_chat_actions)
        self.message_text_view.connect("paste-clipboard", self.on_clipboard_paste)
        self.file_preview_remove_button.connect('clicked', lambda button : dialogs.remove_attached_file(self, button.get_name()))
        self.add_chat_button.connect("clicked", lambda button : self.new_chat())
        self.attachment_button.connect("clicked", lambda button, file_filter=self.file_filter_attachments: dialogs.attach_file(self, file_filter))
        self.create_model_name.get_delegate().connect("insert-text", self.check_alphanumeric)
        self.remote_connection_entry.connect("entry-activated", lambda entry : entry.set_css_classes([]))
        self.remote_connection_switch.connect("notify", lambda pspec, user_data : self.connection_switched())
        self.background_switch.connect("notify", lambda pspec, user_data : self.switch_run_on_background())
        self.setup_model_dropdown()
        if os.path.exists(os.path.join(self.config_dir, "server.json")):
            with open(os.path.join(self.config_dir, "server.json"), "r") as f:
                data = json.load(f)
                self.run_remote = data['run_remote']
                local_instance.port = data['local_port']
                self.remote_url = data['remote_url']
                self.remote_bearer_token = data['remote_bearer_token'] if 'remote_bearer_token' in data else ''
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
                self.remote_bearer_token_entry.set_text(self.remote_bearer_token)
                if self.run_remote:
                    connection_handler.bearer_token = self.remote_bearer_token
                    connection_handler.url = self.remote_url
                    self.remote_connection_switch.set_active(True)
                else:
                    connection_handler.bearer_token = None
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
