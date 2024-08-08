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
"""
Handles the main window
"""
import json, threading, os, re, base64, sys, gettext, uuid, shutil, tarfile, tempfile, logging, random
from io import BytesIO
from PIL import Image
from pypdf import PdfReader
from datetime import datetime

import gi
gi.require_version('GtkSource', '5')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, GdkPixbuf

from . import dialogs, local_instance, connection_handler, available_models_descriptions
from .table_widget import TableWidget
from .internal import config_dir, data_dir, cache_dir, source_dir

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    app_dir = os.getenv("FLATPAK_DEST")
    config_dir = config_dir
    data_dir = data_dir
    cache_dir = cache_dir

    __gtype_name__ = 'AlpacaWindow'

    localedir = os.path.join(source_dir, 'locale')

    gettext.bindtextdomain('com.jeffser.Alpaca', localedir)
    gettext.textdomain('com.jeffser.Alpaca')
    _ = gettext.gettext

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
    split_view_overlay = Gtk.Template.Child()
    regenerate_button : Gtk.Button = None
    selected_chat_row : Gtk.ListBoxRow = None
    create_model_base = Gtk.Template.Child()
    create_model_name = Gtk.Template.Child()
    create_model_system = Gtk.Template.Child()
    create_model_modelfile = Gtk.Template.Child()
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
    chat_right_click_menu = Gtk.Template.Child()
    model_tag_list_box = Gtk.Template.Child()
    navigation_view_manage_models = Gtk.Template.Child()
    file_preview_open_button = Gtk.Template.Child()
    file_preview_remove_button = Gtk.Template.Child()
    secondary_menu_button = Gtk.Template.Child()
    model_searchbar = Gtk.Template.Child()
    no_results_page = Gtk.Template.Child()
    model_link_button = Gtk.Template.Child()
    model_list_box = Gtk.Template.Child()
    model_popover = Gtk.Template.Child()
    model_selector_button = Gtk.Template.Child()
    chat_welcome_screen : Adw.StatusPage = None

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
    def stop_message(self, button=None):
        if self.loading_spinner:
            self.chat_container.remove(self.loading_spinner)
        self.toggle_ui_sensitive(True)
        self.switch_send_stop_button(True)
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
            buffer.insert_markup(buffer.get_end_iter(), footer, len(footer.encode('utf-8')))
            self.chats["chats"][self.chats["selected_chat"]]["messages"][self.editing_message["id"]]["content"] = text
            self.editing_message = None
            self.save_history()
            self.show_toast(_("Message edited successfully"), self.main_overlay)

        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False):
            return
        current_chat_row = self.chat_list_box.get_selected_row()
        self.chat_list_box.unselect_all()
        self.chat_list_box.remove(current_chat_row)
        self.chat_list_box.prepend(current_chat_row)
        self.chat_list_box.select_row(self.chat_list_box.get_row_at_index(0))
        self.chats['order'].remove(self.chats['selected_chat'])
        self.chats['order'].insert(0, self.chats['selected_chat'])
        self.save_history()
        current_model = self.get_current_model(1)
        if current_model is None:
            self.show_toast(_("Please select a model before chatting"), self.main_overlay)
            return
        message_id = self.generate_uuid()

        attached_images = []
        attached_files = {}
        can_use_images = self.verify_if_image_can_be_used()
        for name, content in self.attachments.items():
            if content["type"] == 'image' and can_use_images:
                attached_images.append(name)
            else:
                attached_files[name] = content['type']
            if not os.path.exists(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id)):
                os.makedirs(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id))
            shutil.copy(content['path'], os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id, name))
            content["button"].get_parent().remove(content["button"])
        self.attachments = {}
        self.attachment_box.set_visible(False)

            #{"path": file_path, "type": file_type, "content": content}

        current_datetime = datetime.now()

        self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id] = {
            "role": "user",
            "model": "User",
            "date": current_datetime.strftime("%Y/%m/%d %H:%M:%S"),
            "content": self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        }
        if len(attached_images) > 0:
            self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]['images'] = attached_images
        if len(attached_files.keys()) > 0:
            self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]['files'] = attached_files
        data = {
            "model": current_model,
            "messages": self.convert_history_to_ollama(),
            "options": {"temperature": self.model_tweaks["temperature"], "seed": self.model_tweaks["seed"]},
            "keep_alive": f"{self.model_tweaks['keep_alive']}m"
        }
        self.switch_send_stop_button(False)
        self.toggle_ui_sensitive(False)

        #self.attachments[name] = {"path": file_path, "type": file_type, "content": content}
        raw_message = self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        formated_date = GLib.markup_escape_text(self.generate_datetime_format(current_datetime))
        self.show_message(raw_message, False, f"\n\n<small>{formated_date}</small>", attached_images, attached_files, message_id=message_id)
        self.message_text_view.get_buffer().set_text("", 0)
        self.loading_spinner = Gtk.Spinner(spinning=True, margin_top=12, margin_bottom=12, hexpand=True)
        self.chat_container.append(self.loading_spinner)
        bot_id=self.generate_uuid()
        self.show_message("", True, message_id=bot_id)

        if self.chat_welcome_screen:
            self.chat_container.remove(self.chat_welcome_screen)

        thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model'], bot_id))
        thread.start()
        if len(data['messages']) == 1:
            message_data = data["messages"][0].copy()
            message_data['content'] = raw_message
            generate_title_thread = threading.Thread(target=self.generate_chat_title, args=(message_data, self.chat_list_box.get_selected_row().get_child()))
            generate_title_thread.start()

    @Gtk.Template.Callback()
    def welcome_carousel_page_changed(self, carousel, index):
        logger.debug("Showing welcome carousel")
        if index == 0:
            self.welcome_previous_button.set_sensitive(False)
        else:
            self.welcome_previous_button.set_sensitive(True)
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
        if button.get_label() == "Next":
            self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()+1), True)
        else:
            self.welcome_dialog.force_close()
            if not self.verify_connection():
                self.connection_error()

    @Gtk.Template.Callback()
    def chat_changed(self, listbox, row):
        logger.debug("Changing selected chat")
        if row and row.get_child().get_name() != self.chats["selected_chat"]:
            self.chats["selected_chat"] = row.get_child().get_name()
            self.load_history_into_chat()
            if len(self.chats["chats"][self.chats["selected_chat"]]["messages"]) > 0:
                last_model_used = self.chats["chats"][self.chats["selected_chat"]]["messages"][list(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys())[-1]]["model"]
                for i, m in enumerate(self.local_models):
                    if m == last_model_used:
                        self.model_list_box.select_row(self.model_list_box.get_row_at_index(i))
                        break
            else:
                self.load_history_into_chat()
            self.save_history()

    @Gtk.Template.Callback()
    def change_remote_url(self, entry):
        if not entry.get_text().startswith("http"):
            entry.set_text("http://{}".format(entry.get_text()))
            return
        self.remote_url = entry.get_text()
        logger.debug(f"Changing remote url: {self.remote_url}")
        if self.run_remote:
            connection_handler.URL = self.remote_url
            if self.verify_connection() == False:
                entry.set_css_classes(["error"])
                self.show_toast(_("Failed to connect to server"), self.preferences_dialog)

    @Gtk.Template.Callback()
    def change_remote_bearer_token(self, entry):
        self.remote_bearer_token = entry.get_text()
        self.save_server_config()
        return
        if self.remote_url and self.run_remote:
            connection_handler.URL = self.remote_url
            if self.verify_connection() == False:
                entry.set_css_classes(["error"])
                self.show_toast(_("Failed to connect to server"), self.preferences_dialog)

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        if self.get_hide_on_close():
            logger.info("Hiding app...")
        else:
            logger.info("Closing app...")
            local_instance.stop()

    @Gtk.Template.Callback()
    def model_spin_changed(self, spin):
        value = spin.get_value()
        if spin.get_name() != "temperature":
            value = round(value)
        else:
            value = round(value, 1)
        if self.model_tweaks[spin.get_name()] is not None and self.model_tweaks[spin.get_name()] != value:
            self.model_tweaks[spin.get_name()] = value
            self.save_server_config()

    @Gtk.Template.Callback()
    def create_model_start(self, button):
        name = self.create_model_name.get_text().lower().replace(":", "")
        modelfile_buffer = self.create_model_modelfile.get_buffer()
        modelfile_raw = modelfile_buffer.get_text(modelfile_buffer.get_start_iter(), modelfile_buffer.get_end_iter(), False)
        modelfile = ["FROM {}".format(self.create_model_base.get_subtitle()), "SYSTEM {}".format(self.create_model_system.get_text())]
        for line in modelfile_raw.split('\n'):
            if not line.startswith('SYSTEM') and not line.startswith('FROM'):
                modelfile.append(line)
        self.pulling_model_list_box.set_visible(True)
        model_row = Adw.ActionRow(
            title = name
        )
        thread = threading.Thread(target=self.pull_model_process, kwargs={"model": name, "modelfile": '\n'.join(modelfile)})
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
        self.navigation_view_manage_models.pop()
        thread.start()

    @Gtk.Template.Callback()
    def override_changed(self, entry):
        name = entry.get_name()
        value = entry.get_text()
        if (not value and name not in local_instance.overrides) or (value and value in local_instance.overrides and local_instance.overrides[name] == value):
            return
        if not value:
            del local_instance.overrides[name]
        else:
            local_instance.overrides[name] = value
        self.save_server_config()
        if not self.run_remote:
            local_instance.reset()

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
            if row.get_visible():
                results += 1
        if entry.get_text() and results == 0:
            self.available_model_list_box.set_visible(False)
            self.no_results_page.set_visible(True)
        else:
            self.available_model_list_box.set_visible(True)
            self.no_results_page.set_visible(False)

    @Gtk.Template.Callback()
    def close_model_popup(self, *_):
        self.model_popover.hide()

    @Gtk.Template.Callback()
    def change_model(self, listbox=None, row=None):
        if not row:
            current_model = self.model_selector_button.get_name()
            if current_model != 'NO_MODEL':
                for i, m in enumerate(self.local_models):
                    if m == current_model:
                        self.model_list_box.select_row(self.model_list_box.get_row_at_index(i))
                        return
            if len(self.local_models) > 0:
                self.model_list_box.select_row(self.model_list_box.get_row_at_index(0))
                return
            else:
                model_name = None
        else:
            model_name = row.get_child().get_label()
        button_content = Gtk.Box(
            spacing=10
        )
        button_content.append(
            Gtk.Label(
                label=model_name if model_name else _("Select a Model"),
                ellipsize=2
            )
        )
        button_content.append(
            Gtk.Image.new_from_icon_name("down-symbolic")
        )
        self.model_selector_button.set_name(row.get_name() if row else 'NO_MODEL')
        self.model_selector_button.set_child(button_content)
        self.close_model_popup()
        self.verify_if_image_can_be_used()

    def verify_if_image_can_be_used(self):
        logger.debug("Verifying if image can be used")
        selected = self.get_current_model(1)
        if selected == None:
            return True
        selected = selected.split(":")[0]
        if selected in [key for key, value in self.available_models.items() if value["image"]]:
            for name, content in self.attachments.items():
                if content['type'] == 'image':
                    content['button'].set_css_classes(["flat"])
            return True
        for name, content in self.attachments.items():
            if content['type'] == 'image':
                content['button'].set_css_classes(["flat", "error"])
        return False

    def convert_model_name(self, name:str, mode:int) -> str: # mode=0 name:tag -> Name (tag)   |   mode=1 Name (tag) -> name:tag
        try:
            if mode == 0:
                return "{} ({})".format(name.split(":")[0].replace("-", " ").title(), name.split(":")[1])
            if mode == 1:
                return "{}:{}".format(name.split(" (")[0].replace(" ", "-").lower(), name.split(" (")[1][:-1])
        except Exception as e:
            pass

    def get_current_model(self, mode:int) -> str:
        if not self.model_list_box.get_selected_row():
            return None
        if mode == 0:
            return self.model_list_box.get_selected_row().get_child().get_label()
        if mode == 1:
            return self.model_list_box.get_selected_row().get_name()

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
        if new_text != text:
            editable.stop_emission_by_name("insert-text")

    def create_model(self, model:str, file:bool):
        modelfile_buffer = self.create_model_modelfile.get_buffer()
        modelfile_buffer.delete(modelfile_buffer.get_start_iter(), modelfile_buffer.get_end_iter())
        self.create_model_system.set_text('')
        if not file:
            response = connection_handler.simple_post(f"{connection_handler.URL}/api/show", json.dumps({"name": self.convert_model_name(model, 1)}))
            if response.status_code == 200:
                data = json.loads(response.text)
                modelfile = []
                for line in data['modelfile'].split('\n'):
                    if line.startswith('SYSTEM'):
                        self.create_model_system.set_text(line[len('SYSTEM'):].strip())
                    if not line.startswith('SYSTEM') and not line.startswith('FROM') and not line.startswith('#'):
                        modelfile.append(line)
                self.create_model_name.set_text(self.convert_model_name(model, 1).split(':')[0] + "-custom")
                modelfile_buffer.insert(modelfile_buffer.get_start_iter(), '\n'.join(modelfile), len('\n'.join(modelfile).encode('utf-8')))
            else:
                ##TODO ERROR MESSAGE
                return
            self.create_model_base.set_subtitle(self.convert_model_name(model, 1))
        else:
            self.create_model_name.set_text(os.path.splitext(os.path.basename(model))[0])
            self.create_model_base.set_subtitle(model)
        self.navigation_view_manage_models.push_by_tag('model_create_page')

    def show_toast(self, message:str, overlay):
        logger.info(message)
        toast = Adw.Toast(
            title=message,
            timeout=2
        )
        overlay.add_toast(toast)

    def show_notification(self, title:str, body:str, icon:Gio.ThemedIcon=None):
        if not self.is_active():
            logger.info(f"{title}, {body}")
            notification = Gio.Notification.new(title)
            notification.set_body(body)
            if icon:
                notification.set_icon(icon)
            self.get_application().send_notification(None, notification)

    def delete_message(self, message_element):
        logger.debug("Deleting message")
        message_id = message_element.get_name()
        del self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]
        self.chat_container.remove(message_element)
        if os.path.exists(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id)):
            shutil.rmtree(os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id))
        self.save_history()
        if len(self.chats["chats"][self.chats["selected_chat"]]["messages"]) == 0:
            self.load_history_into_chat()

    def copy_message(self, message_element):
        logger.debug("Copying message")
        message_id = message_element.get_name()
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]["content"])
        self.show_toast(_("Message copied to the clipboard"), self.main_overlay)

    def edit_message(self, message_element, text_view, button_container):
        logger.debug("Editing message")
        if self.editing_message:
            self.send_message()

        button_container.set_visible(False)
        message_id = message_element.get_name()

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

        self.editing_message = {"text_view": text_view, "id": message_id, "button_container": button_container, "footer": footer}

    def preview_file(self, file_path, file_type, presend_name):
        logger.debug(f"Previewing file: {file_path}")
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
                buffer.insert(buffer.get_start_iter(), content, len(content.encode('utf-8')))
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
        for message_id, message in self.chats["chats"][self.chats["selected_chat"]]["messages"].items():
            new_message = message.copy()
            if 'files' in message and len(message['files']) > 0:
                del new_message['files']
                new_message['content'] = ''
                for name, file_type in message['files'].items():
                    file_path = os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id, name)
                    file_data = self.get_content_of_file(file_path, file_type)
                    if file_data:
                        new_message['content'] += f"```[{name}]\n{file_data}\n```"
                new_message['content'] += message['content']
            if 'images' in message and len(message['images']) > 0:
                new_message['images'] = []
                for name in message['images']:
                    file_path = os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id, name)
                    image_data = self.get_content_of_file(file_path, 'image')
                    if image_data:
                        new_message['images'].append(image_data)
            messages.append(new_message)
        return messages

    def generate_chat_title(self, message, label_element):
        logger.debug("Generating chat title")
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
        current_model = self.get_current_model(1)
        data = {"model": current_model, "prompt": prompt, "stream": False}
        if 'images' in message:
            data["images"] = message['images']
        response = connection_handler.simple_post(f"{connection_handler.URL}/api/generate", data=json.dumps(data))

        new_chat_name = json.loads(response.text)["response"].strip().removeprefix("Title: ").removeprefix("title: ").strip('\'"').replace('\n', ' ').title().replace('\'S', '\'s')
        new_chat_name = new_chat_name[:50] + (new_chat_name[50:] and '...')
        self.rename_chat(label_element.get_name(), new_chat_name, label_element)

    def show_message(self, msg:str, bot:bool, footer:str=None, images:list=None, files:dict=None, message_id:str=None):
        message_text = Gtk.TextView(
            editable=False,
            focusable=True,
            wrap_mode= Gtk.WrapMode.WORD,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            hexpand=True,
            css_classes=["flat"] if bot else ["flat", "user_message"],
        )
        if not bot:
            message_text.update_property([4, 7, 1], [_("User message"), True, msg])
        message_buffer = message_text.get_buffer()
        message_buffer.insert(message_buffer.get_end_iter(), msg)
        if footer is not None:
            message_buffer.insert_markup(message_buffer.get_end_iter(), footer, len(footer.encode('utf-8')))

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
        regenerate_button = Gtk.Button(
            icon_name = "update-symbolic",
            css_classes = ["flat", "circular"],
            tooltip_text = _("Regenerate Message")
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
                path = os.path.join(self.data_dir, "chats", self.chats['selected_chat'], message_id, image)
                try:
                    if not os.path.isfile(path):
                        raise FileNotFoundError("'{}' was not found or is a directory".format(path))
                    image_element = Gtk.Image.new_from_file(path)
                    image_element.set_size_request(240, 240)
                    button = Gtk.Button(
                        child=image_element,
                        css_classes=["flat", "chat_image_button"],
                        name=os.path.join(self.data_dir, "chats", "{selected_chat}", message_id, image),
                        tooltip_text=_("Image")
                    )
                    image_element.update_property([4], [_("Image")])
                    button.connect("clicked", lambda button, file_path=path: self.preview_file(file_path, 'image', None))
                except Exception as e:
                    logger.error(e)
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
                        tooltip_text=_("Missing Image")
                    )
                    image_texture.update_property([4], [_("Missing image")])
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
                file_path = os.path.join(self.data_dir, "chats", "{selected_chat}", message_id, name)
                button.connect("clicked", lambda button, file_path=file_path, file_type=file_type: self.preview_file(file_path, file_type, None))
                file_container.append(button)
            message_box.append(file_scroller)

        message_box.append(message_text)
        overlay = Gtk.Overlay(css_classes=["message"], name=message_id)
        overlay.set_child(message_box)

        delete_button.connect("clicked", lambda button, element=overlay: self.delete_message(element))
        copy_button.connect("clicked", lambda button, element=overlay: self.copy_message(element))
        edit_button.connect("clicked", lambda button, element=overlay, textview=message_text, button_container=button_container: self.edit_message(element, textview, button_container))
        regenerate_button.connect('clicked', lambda button, message_id=message_id, bot_message_box=message_box, bot_message_button_container=button_container : self.regenerate_message(message_id, bot_message_box, bot_message_button_container))
        button_container.append(delete_button)
        button_container.append(copy_button)
        button_container.append(regenerate_button if bot else edit_button)
        overlay.add_overlay(button_container)
        self.chat_container.append(overlay)

        if bot:
            self.bot_message = message_buffer
            self.bot_message_view = message_text
            self.bot_message_box = message_box
            self.bot_message_button_container = button_container

    def update_list_local_models(self):
        logger.debug("Updating list of local models")
        self.local_models = []
        response = connection_handler.simple_get(f"{connection_handler.URL}/api/tags")
        self.model_list_box.remove_all()
        if response.status_code == 200:
            self.local_model_list_box.remove_all()
            if len(json.loads(response.text)['models']) == 0:
                self.local_model_list_box.set_visible(False)
            else:
                self.local_model_list_box.set_visible(True)
            for model in json.loads(response.text)['models']:
                model_name = self.convert_model_name(model["name"], 0)
                model_row = Adw.ActionRow(
                    title = "<b>{}</b>".format(model_name.split(" (")[0]),
                    subtitle = model_name.split(" (")[1][:-1]
                )
                button = Gtk.Button(
                    icon_name = "user-trash-symbolic",
                    vexpand = False,
                    valign = 3,
                    css_classes = ["error", "circular"],
                    tooltip_text = _("Remove '{}'").format(model_name)
                )
                button.connect("clicked", lambda button=button, model_name=model["name"]: dialogs.delete_model(self, model_name))
                model_row.add_suffix(button)
                self.local_model_list_box.append(model_row)

                selector_row = Gtk.ListBoxRow(
                    child = Gtk.Label(
                        label=model_name, halign=1, hexpand=True
                    ),
                    halign=0,
                    hexpand=True,
                    name=model["name"],
                    tooltip_text=model_name
                )
                self.model_list_box.append(selector_row)
                self.local_models.append(model["name"])
        else:
            self.connection_error()

    def save_server_config(self):
        with open(os.path.join(self.config_dir, "server.json"), "w+", encoding="utf-8") as f:
            json.dump({'remote_url': self.remote_url, 'remote_bearer_token': self.remote_bearer_token, 'run_remote': self.run_remote, 'local_port': local_instance.port, 'run_on_background': self.run_on_background, 'model_tweaks': self.model_tweaks, 'ollama_overrides': local_instance.overrides}, f, indent=6)

    def verify_connection(self):
        try:
            response = connection_handler.simple_get(f"{connection_handler.URL}/api/tags")
            if response.status_code == 200:
                self.save_server_config()
                self.update_list_local_models()
            return response.status_code == 200
        except Exception as e:
            logger.error(e)
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
        # Match code blocks without language
        no_lang_code_block_pattern = re.compile(r'`\n(.*?)\n`', re.DOTALL)
        for match in no_lang_code_block_pattern.finditer(text):
            start, end = match.span()
            if pos < start:
                normal_text = text[pos:start]
                parts.append({"type": "normal", "text": normal_text.strip()})
            code_text = match.group(1)
            parts.append({"type": "code", "text": code_text, "language": None})
            pos = end
        # Match tables
        table_pattern = re.compile(r'((\r?\n){2}|^)([^\r\n]*\|[^\r\n]*(\r?\n)?)+(?=(\r?\n){2}|$)', re.MULTILINE)
        for match in table_pattern.finditer(text):
            start, end = match.span()
            if pos < start:
                normal_text = text[pos:start]
                parts.append({"type": "normal", "text": normal_text.strip()})
            table_text = match.group(0)
            parts.append({"type": "table", "text": table_text})
            pos = end
        # Extract any remaining normal text after the last code block
        if pos < len(text):
            normal_text = text[pos:]
            if normal_text.strip():
                parts.append({"type": "normal", "text": normal_text.strip()})
        bold_pattern = re.compile(r'\*\*(.*?)\*\*') #"**text**"
        code_pattern = re.compile(r'`([^`\n]*?)`') #"`text`"
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
                    css_classes=["flat", "response_message"]
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
                    message_buffer.insert_markup(message_buffer.get_end_iter(), match.group(0), len(match.group(0).encode('utf-8')))
                    position = end

                if position < len(part['text']):
                    message_buffer.insert(message_buffer.get_end_iter(), part['text'][position:])

                if footer: message_buffer.insert_markup(message_buffer.get_end_iter(), footer, len(footer.encode('utf-8')))

                message_text.update_property([4, 7, 1], [_("Response message"), False, message_buffer.get_text(message_buffer.get_start_iter(), message_buffer.get_end_iter(), False)])
                self.bot_message_box.append(message_text)
            elif part['type'] == 'code':
                language = None
                if part['language']:
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
                    top_margin=6, bottom_margin=6, left_margin=12, right_margin=12, css_classes=["response_message"]
                )
                source_view.update_property([4], [_("{}Code Block").format('{} '.format(language.get_name()) if language else "")])
                source_view.set_editable(False)
                code_block_box = Gtk.Box(css_classes=["card", "response_message"], orientation=1, overflow=1)
                title_box = Gtk.Box(margin_start=12, margin_top=3, margin_bottom=3, margin_end=3)
                title_box.append(Gtk.Label(label=language.get_name() if language else _("Code Block"), hexpand=True, xalign=0))
                copy_button = Gtk.Button(icon_name="edit-copy-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Copy Message"))
                copy_button.connect("clicked", self.on_copy_code_clicked, buffer)
                title_box.append(copy_button)
                code_block_box.append(title_box)
                code_block_box.append(Gtk.Separator())
                code_block_box.append(source_view)
                self.bot_message_box.append(code_block_box)
                self.style_manager.connect("notify::dark", self.on_theme_changed, buffer)
            elif part['type'] == 'table':
                table = TableWidget(part['text'])
                self.bot_message_box.append(table)
        vadjustment = self.chat_window.get_vadjustment()
        vadjustment.set_value(vadjustment.get_upper())
        self.bot_message = None
        self.bot_message_box = None

    def on_theme_changed(self, manager, dark, buffer):
        logger.debug("Theme changed")
        if manager.get_dark():
            source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark')
        else:
            source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita')
        buffer.set_style_scheme(source_style)

    def on_copy_code_clicked(self, btn, text_buffer):
        logger.debug("Copying code")
        clipboard = Gdk.Display().get_default().get_clipboard()
        start = text_buffer.get_start_iter()
        end = text_buffer.get_end_iter()
        text = text_buffer.get_text(start, end, False)
        clipboard.set(text)
        self.show_toast(_("Code copied to the clipboard"), self.main_overlay)

    def generate_datetime_format(self, dt:datetime) -> str:
        date = GLib.DateTime.new(GLib.DateTime.new_now_local().get_timezone(), dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        current_date = GLib.DateTime.new_now_local()
        if date.format("%Y/%m/%d") == current_date.format("%Y/%m/%d"):
            return date.format("%H:%M %p")
        if date.format("%Y") == current_date.format("%Y"):
            return date.format("%b %d, %H:%M %p")
        return date.format("%b %d %Y, %H:%M %p")

    def update_bot_message(self, data, message_id):
        if self.bot_message is None:
            self.save_history()
            sys.exit()
        vadjustment = self.chat_window.get_vadjustment()
        if message_id not in self.chats["chats"][self.chats["selected_chat"]]["messages"] or vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
            GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
        if 'done' in data and data['done']:
            formated_date = GLib.markup_escape_text(self.generate_datetime_format(datetime.strptime(self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]["date"], '%Y/%m/%d %H:%M:%S')))
            text = f"\n\n{self.convert_model_name(data['model'], 0)}\n<small>{formated_date}</small>"
            GLib.idle_add(self.bot_message.insert_markup, self.bot_message.get_end_iter(), text, len(text.encode('utf-8')))
            self.save_history()
            GLib.idle_add(self.bot_message_button_container.set_visible, True)
            #Notification
            first_paragraph = self.bot_message.get_text(self.bot_message.get_start_iter(), self.bot_message.get_end_iter(), False).split("\n")[0]
            GLib.idle_add(self.show_notification, self.chats["selected_chat"], first_paragraph[:100] + (first_paragraph[100:] and '...'), Gio.ThemedIcon.new("chat-message-new-symbolic"))
        else:
            if not self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]["content"] and self.loading_spinner:
                GLib.idle_add(self.chat_container.remove, self.loading_spinner)
                self.loading_spinner = None
            GLib.idle_add(self.bot_message.insert, self.bot_message.get_end_iter(), data['message']['content'])
            self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]['content'] += data['message']['content']

    def toggle_ui_sensitive(self, status):
        for element in [self.chat_list_box, self.add_chat_button, self.secondary_menu_button]:
            element.set_sensitive(status)

    def switch_send_stop_button(self, send:bool):
        self.stop_button.set_visible(not send)
        self.send_button.set_visible(send)

    def run_message(self, messages, model, message_id):
        logger.debug("Running message")
        self.bot_message_button_container.set_visible(False)
        self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id] = {
            "role": "assistant",
            "model": model,
            "date": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            "content": ''
        }
        if self.regenerate_button:
            GLib.idle_add(self.chat_container.remove, self.regenerate_button)
        try:
            response = connection_handler.stream_post(f"{connection_handler.URL}/api/chat", data=json.dumps({"model": model, "messages": messages}), callback=lambda data, message_id=message_id: self.update_bot_message(data, message_id))
            if response.status_code != 200:
                raise Exception('Network Error')
            GLib.idle_add(self.add_code_blocks)
        except Exception as e:
            GLib.idle_add(self.connection_error)
            self.regenerate_button = Gtk.Button(
                child=Adw.ButtonContent(
                    icon_name='update-symbolic',
                    label=_('Regenerate Response')
                ),
                css_classes=["suggested-action"],
                halign=3
            )
            GLib.idle_add(self.chat_container.append, self.regenerate_button)
            self.regenerate_button.connect('clicked', lambda button, message_id=message_id, bot_message_box=self.bot_message_box, bot_message_button_container=self.bot_message_button_container : self.regenerate_message(message_id, bot_message_box, bot_message_button_container))
        finally:
            GLib.idle_add(self.switch_send_stop_button, True)
            GLib.idle_add(self.toggle_ui_sensitive, True)
            if self.loading_spinner:
                GLib.idle_add(self.chat_container.remove, self.loading_spinner)
                self.loading_spinner = None

    def regenerate_message(self, message_id, bot_message_box, bot_message_button_container):
        if not self.bot_message:
            self.bot_message_button_container = bot_message_button_container
            self.bot_message_view = Gtk.TextView(
                editable=False,
                focusable=True,
                wrap_mode= Gtk.WrapMode.WORD,
                margin_top=12,
                margin_bottom=12,
                hexpand=True,
                css_classes=["flat"]
            )
            self.bot_message = self.bot_message_view.get_buffer()
            for widget in list(bot_message_box):
                bot_message_box.remove(widget)
            bot_message_box.append(self.bot_message_view)
            history = self.convert_history_to_ollama()[:list(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys()).index(message_id)]
            if message_id in self.chats["chats"][self.chats["selected_chat"]]["messages"]:
                del self.chats["chats"][self.chats["selected_chat"]]["messages"][message_id]
            data = {
                "model": self.get_current_model(1),
                "messages": history,
                "options": {"temperature": self.model_tweaks["temperature"], "seed": self.model_tweaks["seed"]},
                "keep_alive": f"{self.model_tweaks['keep_alive']}m"
            }
            self.switch_send_stop_button(False)
            self.toggle_ui_sensitive(False)
            thread = threading.Thread(target=self.run_message, args=(data['messages'], data['model'], message_id))
            thread.start()
        else:
            self.show_toast(_("Message cannot be regenerated while receiving a response"), self.main_overlay)

    def pull_model_update(self, data, model_name):
        if 'error' in data:
            self.pulling_models[model_name]['error'] = data['error']
            return
        if model_name in self.pulling_models.keys():
            if 'completed' in data and 'total' in data:
                GLib.idle_add(self.pulling_models[model_name]['row'].set_subtitle, '<tt>{}%</tt>'.format(round(data['completed'] / data['total'] * 100, 2)))
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
            response = connection_handler.stream_post(f"{connection_handler.URL}/api/create", data=json.dumps(data), callback=lambda data, model_name=model: self.pull_model_update(data, model_name))
        else:
            data = {"name": model}
            response = connection_handler.stream_post(f"{connection_handler.URL}/api/pull", data=json.dumps(data), callback=lambda data, model_name=model: self.pull_model_update(data, model_name))
        GLib.idle_add(self.update_list_local_models)
        GLib.idle_add(self.change_model)

        if response.status_code == 200 and 'error' not in self.pulling_models[model]:
            GLib.idle_add(self.show_notification, _("Task Complete"), _("Model '{}' pulled successfully.").format(model), Gio.ThemedIcon.new("emblem-ok-symbolic"))
            GLib.idle_add(self.show_toast, _("Model '{}' pulled successfully.").format(model), self.manage_models_overlay)
        elif response.status_code == 200 and self.pulling_models[model]['error']:
            GLib.idle_add(self.show_notification, _("Pull Model Error"), _("Failed to pull model '{}': {}").format(model, self.pulling_models[model]['error']), Gio.ThemedIcon.new("dialog-error-symbolic"))
            GLib.idle_add(self.show_toast, _("Error pulling '{}': {}").format(model, self.pulling_models[model]['error']), self.manage_models_overlay)
        else:
            GLib.idle_add(self.show_notification, _("Pull Model Error"), _("Failed to pull model '{}' due to network error.").format(model), Gio.ThemedIcon.new("dialog-error-symbolic"))
            GLib.idle_add(self.show_toast, _("Error pulling '{}'").format(model), self.manage_models_overlay)
            GLib.idle_add(self.manage_models_dialog.close)
            GLib.idle_add(self.connection_error)

        GLib.idle_add(self.pulling_models[model]['overlay'].get_parent().get_parent().remove, self.pulling_models[model]['overlay'].get_parent())
        del self.pulling_models[model]
        if len(list(self.pulling_models.keys())) == 0:
            GLib.idle_add(self.pulling_model_list_box.set_visible, False)

    def pull_model(self, model):
        if model in self.pulling_models.keys() or model in self.local_models or ":" not in model:
            return
        logger.info("Pulling model")
        self.pulling_model_list_box.set_visible(True)
        #self.pulling_model_list_box.connect('row_selected', lambda list_box, row: dialogs.stop_pull_model(self, row.get_name()) if row else None) #It isn't working for some reason
        model_name = self.convert_model_name(model, 0)
        model_row = Adw.ActionRow(
            title = "<b>{}</b> <small>{}</small>".format(model_name.split(" (")[0], model_name.split(" (")[1][:-1]),
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
            tooltip_text = _("Stop Pulling '{}'").format(model_name)
        )
        button.connect("clicked", lambda button, model_name=model : dialogs.stop_pull_model(self, model_name))
        model_row.add_suffix(button)
        self.pulling_models[model] = {"row": model_row, "progress_bar": progress_bar, "overlay": overlay}
        overlay.set_child(model_row)
        overlay.add_overlay(progress_bar)
        self.pulling_model_list_box.append(overlay)
        thread.start()

    def confirm_pull_model(self, model_name):
        logger.debug("Confirming pull model")
        self.navigation_view_manage_models.pop()
        self.model_tag_list_box.unselect_all()
        self.pull_model(model_name)

    def list_available_model_tags(self, model_name):
        logger.debug("Listing available model tags")
        self.navigation_view_manage_models.push_by_tag('model_tags_page')
        self.navigation_view_manage_models.find_page('model_tags_page').set_title(model_name.replace("-", " ").title())
        self.model_link_button.set_name(self.available_models[model_name]['url'])
        self.model_link_button.set_tooltip_text(self.available_models[model_name]['url'])
        self.available_model_list_box.unselect_all()
        self.model_tag_list_box.remove_all()
        tags = self.available_models[model_name]['tags']
        for tag_data in tags:
            if f"{model_name}:{tag_data[0]}" not in self.local_models:
                tag_row = Adw.ActionRow(
                    title = tag_data[0],
                    subtitle = tag_data[1],
                    name = f"{model_name}:{tag_data[0]}"
                )
                download_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
                tag_row.add_suffix(download_icon)
                download_icon.update_property([4], [_("Download {}:{}").format(model_name, tag_data[0])])

                gesture_click = Gtk.GestureClick.new()
                gesture_click.connect("pressed", lambda *_, name=f"{model_name}:{tag_data[0]}" : self.confirm_pull_model(name))

                event_controller_key = Gtk.EventControllerKey.new()
                event_controller_key.connect("key-pressed", lambda controller, key, *_, name=f"{model_name}:{tag_data[0]}" : self.confirm_pull_model(name) if key in (Gdk.KEY_space, Gdk.KEY_Return) else None)

                tag_row.add_controller(gesture_click)
                tag_row.add_controller(event_controller_key)

                self.model_tag_list_box.append(tag_row)
        return True

    def update_list_available_models(self):
        logger.debug("Updating list of available models")
        self.available_model_list_box.remove_all()
        for name, model_info in self.available_models.items():
            model = Adw.ActionRow(
                title = "<b>{}</b> <small>by {}</small>".format(name.replace("-", " ").title(), model_info['author']),
                subtitle = available_models_descriptions.descriptions[name] + ("\n\n<b>{}</b>".format(_("Image Recognition")) if model_info['image'] else ""),
                name = name
            )
            next_icon = Gtk.Image.new_from_icon_name("go-next")
            next_icon.set_margin_start(5)
            next_icon.update_property([4], [_("Enter download menu for {}").format(name.replace("-", ""))])
            model.add_suffix(next_icon)

            gesture_click = Gtk.GestureClick.new()
            gesture_click.connect("pressed", lambda *_, name=name : self.list_available_model_tags(name))

            event_controller_key = Gtk.EventControllerKey.new()
            event_controller_key.connect("key-pressed", lambda controller, key, *_, name=name : self.list_available_model_tags(name) if key in (Gdk.KEY_space, Gdk.KEY_Return) else None)

            model.add_controller(gesture_click)
            model.add_controller(event_controller_key)
            self.available_model_list_box.append(model)

    def save_history(self):
        logger.debug("Saving history")
        with open(os.path.join(self.data_dir, "chats", "chats.json"), "w+", encoding="utf-8") as f:
            json.dump(self.chats, f, indent=4)

    def send_sample_prompt(self, prompt):
        buffer = self.message_text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), prompt, len(prompt.encode('utf-8')))
        self.send_message()

    def load_history_into_chat(self):
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        self.chat_welcome_screen = None
        if len(self.chats['chats'][self.chats["selected_chat"]]['messages']) > 0:
            for key, message in self.chats['chats'][self.chats["selected_chat"]]['messages'].items():
                if message:
                    formated_date = GLib.markup_escape_text(self.generate_datetime_format(datetime.strptime(message['date'] + (":00" if message['date'].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S')))
                    if message['role'] == 'user':
                        self.show_message(message['content'], False, f"\n\n<small>{formated_date}</small>", message['images'] if 'images' in message else None, message['files'] if 'files' in message else None, message_id=key)
                    else:
                        self.show_message(message['content'], True, f"\n\n{self.convert_model_name(message['model'], 0)}\n<small>{formated_date}</small>", message_id=key)
                        self.add_code_blocks()
                        self.bot_message = None
        else:
            button_container = Gtk.Box(
                orientation = 1,
                spacing = 10,
                halign = 3
            )
            if len(self.local_models) > 0:
                possible_prompts = [
                    "What can you do?",
                    "Give me a pancake recipe",
                    "Why is the sky blue?"
                ]
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
                    css_classes=["accent"]
                )
                button.connect('clicked', lambda *_ : self.manage_models_dialog.present(self))
                button_container.append(button)
            self.chat_welcome_screen = Adw.StatusPage(
                icon_name="com.jeffser.Alpaca",
                title="Alpaca",
                description=_("Try one of these prompts") if len(self.local_models) > 0 else _("It looks like you don't have any models downloaded yet. Download models to get started!"),
                child=button_container,
                vexpand=True
            )
            self.chat_container.append(self.chat_welcome_screen)


    def load_history(self):
        logger.debug("Loading history")
        if os.path.exists(os.path.join(self.data_dir, "chats", "chats.json")):
            try:
                with open(os.path.join(self.data_dir, "chats", "chats.json"), "r", encoding="utf-8") as f:
                    self.chats = json.load(f)
                    if len(list(self.chats["chats"].keys())) == 0:
                        self.chats["chats"][_("New Chat")] = {"messages": {}}
                    if "selected_chat" not in self.chats or self.chats["selected_chat"] not in self.chats["chats"]:
                        self.chats["selected_chat"] = list(self.chats["chats"].keys())[0]
                    if "order" not in self.chats:
                        self.chats["order"] = []
                        for chat_name in self.chats["chats"].keys():
                            self.chats["order"].append(chat_name)
                    self.model_list_box.select_row(self.model_list_box.get_row_at_index(0))
                    if len(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys()) > 0:
                        last_model_used = self.chats["chats"][self.chats["selected_chat"]]["messages"][list(self.chats["chats"][self.chats["selected_chat"]]["messages"].keys())[-1]]["model"]
                        for i, m in enumerate(self.local_models):
                            if m == last_model_used:
                                self.model_list_box.select_row(self.model_list_box.get_row_at_index(i))
                                break
            except Exception as e:
                logger.error(e)
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
                    if f"{chat_name} {i+1}" not in compare_list:
                        chat_name = f"{chat_name} {i+1}"
                        break
        return chat_name

    def generate_uuid(self) -> str:
        return f"{datetime.today().strftime('%Y%m%d%H%M%S%f')}{uuid.uuid4().hex}"

    def clear_chat(self):
        logger.info("Clearing chat")
        for widget in list(self.chat_container): self.chat_container.remove(widget)
        self.chats["chats"][self.chats["selected_chat"]]["messages"] = []
        self.save_history()

    def delete_chat(self, chat_name):
        logger.info("Deleting chat")
        del self.chats['chats'][chat_name]
        self.chats['order'].remove(chat_name)
        if os.path.exists(os.path.join(self.data_dir, "chats", chat_name)):
            shutil.rmtree(os.path.join(self.data_dir, "chats", chat_name))
        self.save_history()
        self.update_chat_list()
        if len(self.chats['chats'])==0:
            self.new_chat()
        if self.chats['selected_chat'] == chat_name:
            self.chat_list_box.select_row(self.chat_list_box.get_row_at_index(0))

    def rename_chat(self, old_chat_name, new_chat_name, label_element):
        logger.info(f"Renaming chat \"{old_chat_name}\" -> \"{new_chat_name}\"")
        new_chat_name = self.generate_numbered_name(new_chat_name, self.chats["chats"].keys())
        if self.chats["selected_chat"] == old_chat_name:
            self.chats["selected_chat"] = new_chat_name
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
        logger.debug("Stopping model pull")
        self.pulling_models[model_name]['overlay'].get_parent().get_parent().remove(self.pulling_models[model_name]['overlay'].get_parent())
        del self.pulling_models[model_name]

    def delete_model(self, model_name):
        logger.debug("Deleting model")
        response = connection_handler.simple_delete(f"{connection_handler.URL}/api/delete", data={"name": model_name})
        self.update_list_local_models()
        if response.status_code == 200:
            self.show_toast(_("Model deleted successfully"), self.manage_models_overlay)
            self.change_model()
        else:
            self.manage_models_dialog.close()
            self.connection_error()

    def chat_click_handler(self, gesture, n_press, x, y):
        chat_row = gesture.get_widget()
        popover = Gtk.PopoverMenu(
            menu_model=self.chat_right_click_menu,
            has_arrow=False,
            halign=1,
            height_request=125
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

        if append:
            self.chat_list_box.append(chat_row)
        else:
            self.chat_list_box.prepend(chat_row)
        if select:
            self.chat_list_box.select_row(chat_row)

    def update_chat_list(self):
        self.chat_list_box.remove_all()
        for name in self.chats['order']:
            if name in self.chats['chats'].keys():
                self.new_chat_element(name, self.chats["selected_chat"] == name, True)

    def show_preferences_dialog(self):
        logger.debug("Showing preferences dialog")
        self.preferences_dialog.present(self)

    def connect_remote(self, url, bearer_token):
        logger.debug(f"Connecting to remote: {url}")
        connection_handler.URL = url
        connection_handler.BEARER_TOKEN = bearer_token
        self.remote_url = connection_handler.URL
        self.remote_connection_entry.set_text(self.remote_url)
        if self.verify_connection() == False: self.connection_error()

    def connect_local(self):
        logger.debug("Connecting to Alpaca's Ollama instance")
        self.run_remote = False
        connection_handler.BEARER_TOKEN = None
        connection_handler.URL = f"http://127.0.0.1:{local_instance.port}"
        local_instance.start()
        if self.verify_connection() == False:
            self.connection_error()
        else:
            self.remote_connection_switch.set_active(False)

    def connection_error(self):
        logger.error("Connection error")
        if self.run_remote:
            dialogs.reconnect_remote(self, connection_handler.URL, connection_handler.BEARER_TOKEN)
        else:
            local_instance.reset()
            self.show_toast(_("There was an error with the local Ollama instance, so it has been reset"), self.main_overlay)

    def connection_switched(self):
        logger.debug("Connection switched")
        new_value = self.remote_connection_switch.get_active()
        if new_value != self.run_remote:
            self.run_remote = new_value
            if self.run_remote:
                connection_handler.BEARER_TOKEN = self.remote_bearer_token
                connection_handler.URL = self.remote_url
                if self.verify_connection() == False:
                    self.connection_error()
                else:
                    local_instance.stop()
            else:
                connection_handler.BEARER_TOKEN = None
                connection_handler.URL = f"http://127.0.0.1:{local_instance.port}"
                local_instance.start()
                if self.verify_connection() == False:
                    self.connection_error()

    def on_replace_contents(self, file, result):
        file.replace_contents_finish(result)
        self.show_toast(_("Chat exported successfully"), self.main_overlay)

    def on_export_chat(self, file_dialog, result, chat_name):
        file = file_dialog.save_finish(result)
        if not file:
            return
        json_data = json.dumps({chat_name: self.chats["chats"][chat_name]}, indent=4).encode("UTF-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = os.path.join(temp_dir, "data.json")
            with open(json_path, "wb", encoding="utf-8") as json_file:
                json_file.write(json_data)

            tar_path = os.path.join(temp_dir, chat_name)
            with tarfile.open(tar_path, "w") as tar:
                tar.add(json_path, arcname="data.json")
                directory = os.path.join(self.data_dir, "chats", chat_name)
                if os.path.exists(directory) and os.path.isdir(directory):
                    tar.add(directory, arcname=os.path.basename(directory))

            with open(tar_path, "rb", encoding="utf-8") as tar:
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
        logger.info("Exporting chat")
        file_dialog = Gtk.FileDialog(initial_name=f"{chat_name}.tar")
        file_dialog.save(parent=self, cancellable=None, callback=lambda file_dialog, result, chat_name=chat_name: self.on_export_chat(file_dialog, result, chat_name))

    def on_chat_imported(self, file_dialog, result):
        file = file_dialog.open_finish(result)
        if not file:
            return
        stream = file.read(None)
        data_stream = Gio.DataInputStream.new(stream)
        tar_content = data_stream.read_bytes(1024 * 1024, None)

        with tempfile.TemporaryDirectory() as temp_dir:
            tar_filename = os.path.join(temp_dir, "imported_chat.tar")

            with open(tar_filename, "wb", encoding="utf-8") as tar_file:
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
        logger.info("Importing chat")
        file_dialog = Gtk.FileDialog(default_filter=self.file_filter_tar)
        file_dialog.open(self, None, self.on_chat_imported)

    def switch_run_on_background(self):
        logger.debug("Switching run on background")
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
                logger.error(e)
                self.show_toast(_("Cannot open image"), self.main_overlay)
        elif file_type == 'plain_text' or file_type == 'youtube' or file_type == 'website':
            with open(file_path, 'r', encoding="utf-8") as f:
                return f.read()
        elif file_type == 'pdf':
            reader = PdfReader(file_path)
            if len(reader.pages) == 0:
                return None
            text = ""
            for i, page in enumerate(reader.pages):
                text += f"\n- Page {i}\n{page.extract_text(extraction_mode='layout', layout_mode_space_vertically=False)}\n"
            return text

    def remove_attached_file(self, name):
        logger.debug("Removing attached file")
        button = self.attachments[name]['button']
        button.get_parent().remove(button)
        del self.attachments[name]
        if len(self.attachments) == 0:
            self.attachment_box.set_visible(False)

    def attach_file(self, file_path, file_type):
        logger.debug(f"Attaching file: {file_path}")
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
        if action_name in ('delete_chat', 'delete_current_chat'):
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
                    logger.error(e)
                    self.show_toast(_("This video is not available"), self.main_overlay)
            elif url_regex.match(text):
                dialogs.attach_website(self, text)
        except Exception as e:
            logger.error(e)

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
        except Exception as e:
            pass

    def on_clipboard_paste(self, textview):
        logger.debug("Pasting from clipboard")
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self.cb_text_received)
        clipboard.read_texture_async(None, self.cb_image_received)

    def handle_enter_key(self):
        if not self.bot_message:
            self.send_message()
        return True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        with open(os.path.join(source_dir, 'available_models.json'), 'r', encoding="utf-8") as f:
            self.available_models = json.load(f)
        if not os.path.exists(os.path.join(self.data_dir, "chats")):
            os.makedirs(os.path.join(self.data_dir, "chats"))
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", lambda controller, keyval, keycode, state: self.handle_enter_key() if keyval==Gdk.KEY_Return else None)
        self.message_text_view.add_controller(key_controller)
        self.set_help_overlay(self.shortcut_window)
        self.get_application().set_accels_for_action("win.show-help-overlay", ['<primary>slash'])
        self.get_application().create_action('new_chat', lambda *_: self.new_chat(), ['<primary>n'])
        self.get_application().create_action('clear', lambda *_: dialogs.clear_chat(self), ['<primary>e'])
        self.get_application().create_action('import_chat', lambda *_: self.import_chat(), ['<primary>i'])
        self.get_application().create_action('create_model_from_existing', lambda *_: dialogs.create_model_from_existing(self))
        self.get_application().create_action('create_model_from_file', lambda *_: dialogs.create_model_from_file(self))
        self.get_application().create_action('create_model_from_name', lambda *_: dialogs.create_model_from_name(self))
        self.get_application().create_action('delete_chat', self.chat_actions)
        self.get_application().create_action('delete_current_chat', self.current_chat_actions)
        self.get_application().create_action('rename_chat', self.chat_actions)
        self.get_application().create_action('rename_current_chat', self.current_chat_actions)
        self.get_application().create_action('export_chat', self.chat_actions)
        self.get_application().create_action('export_current_chat', self.current_chat_actions)
        self.get_application().create_action('toggle_sidebar', lambda *_: self.split_view_overlay.set_show_sidebar(not self.split_view_overlay.get_show_sidebar()), ['F9'])
        self.get_application().create_action('manage_models', lambda *_: self.manage_models_dialog.present(self), ['<primary>m'])
        self.message_text_view.connect("paste-clipboard", self.on_clipboard_paste)
        self.file_preview_remove_button.connect('clicked', lambda button : dialogs.remove_attached_file(self, button.get_name()))
        self.add_chat_button.connect("clicked", lambda button : self.new_chat())
        self.attachment_button.connect("clicked", lambda button, file_filter=self.file_filter_attachments: dialogs.attach_file(self, file_filter))
        self.create_model_name.get_delegate().connect("insert-text", lambda *_ : self.check_alphanumeric(*_, ['-', '.', '_']))
        self.remote_connection_entry.connect("entry-activated", lambda entry : entry.set_css_classes([]))
        self.remote_connection_switch.connect("notify", lambda pspec, user_data : self.connection_switched())
        self.background_switch.connect("notify", lambda pspec, user_data : self.switch_run_on_background())
        if os.path.exists(os.path.join(self.config_dir, "server.json")):
            with open(os.path.join(self.config_dir, "server.json"), "r", encoding="utf-8") as f:
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
                if "ollama_overrides" in data:
                    local_instance.overrides = data['ollama_overrides']
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
                    connection_handler.BEARER_TOKEN = self.remote_bearer_token
                    connection_handler.URL = self.remote_url
                    self.remote_connection_switch.set_active(True)
                else:
                    connection_handler.BEARER_TOKEN = None
                    self.remote_connection_switch.set_active(False)
                    connection_handler.URL = f"http://127.0.0.1:{local_instance.port}"
                    local_instance.start()
        else:
            local_instance.start()
            connection_handler.URL = f"http://127.0.0.1:{local_instance.port}"
            self.welcome_dialog.present(self)
        if self.verify_connection() is False:
            self.connection_error()
        self.update_list_available_models()
        self.load_history()
        self.update_chat_list()
