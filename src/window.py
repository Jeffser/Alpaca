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
import json, threading, os, re, base64, gettext, uuid, shutil, logging, time
from io import BytesIO
from PIL import Image
from pypdf import PdfReader
from datetime import datetime
from pytube import YouTube

import gi
gi.require_version('GtkSource', '5')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, GdkPixbuf

from . import connection_handler, generic_actions
from .custom_widgets import message_widget, chat_widget, model_widget, terminal_widget, dialog_widget
from .internal import config_dir, data_dir, cache_dir, source_dir

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    app_dir = os.getenv("FLATPAK_DEST")

    __gtype_name__ = 'AlpacaWindow'

    localedir = os.path.join(source_dir, 'locale')

    gettext.bindtextdomain('com.jeffser.Alpaca', localedir)
    gettext.textdomain('com.jeffser.Alpaca')
    _ = gettext.gettext

    #Variables
    attachments = {}

    #Override elements
    overrides_group = Gtk.Template.Child()

    #Elements
    split_view_overlay = Gtk.Template.Child()
    regenerate_button : Gtk.Button = None
    selected_chat_row : Gtk.ListBoxRow = None
    create_model_base = Gtk.Template.Child()
    create_model_name = Gtk.Template.Child()
    create_model_system = Gtk.Template.Child()
    create_model_modelfile = Gtk.Template.Child()
    tweaks_group = Gtk.Template.Child()
    preferences_dialog = Gtk.Template.Child()
    shortcut_window : Gtk.ShortcutsWindow  = Gtk.Template.Child()
    file_preview_dialog = Gtk.Template.Child()
    file_preview_text_view = Gtk.Template.Child()
    file_preview_image = Gtk.Template.Child()
    welcome_dialog = Gtk.Template.Child()
    welcome_carousel = Gtk.Template.Child()
    welcome_previous_button = Gtk.Template.Child()
    welcome_next_button = Gtk.Template.Child()
    main_overlay = Gtk.Template.Child()
    manage_models_overlay = Gtk.Template.Child()
    chat_stack = Gtk.Template.Child()
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
    message_searchbar = Gtk.Template.Child()
    message_search_button = Gtk.Template.Child()
    searchentry_messages = Gtk.Template.Child()
    no_results_page = Gtk.Template.Child()
    model_link_button = Gtk.Template.Child()
    title_stack = Gtk.Template.Child()
    manage_models_dialog = Gtk.Template.Child()
    model_scroller = Gtk.Template.Child()

    chat_list_container = Gtk.Template.Child()
    chat_list_box = None
    ollama_instance = None
    model_manager = None
    add_chat_button = Gtk.Template.Child()
    instance_idle_timer = Gtk.Template.Child()

    background_switch = Gtk.Template.Child()
    powersaver_warning_switch = Gtk.Template.Child()
    remote_connection_switch = Gtk.Template.Child()
    remote_connection_switch_handler = None

    banner = Gtk.Template.Child()

    style_manager = Adw.StyleManager()

    terminal_scroller = Gtk.Template.Child()
    terminal_dialog = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def stop_message(self, button=None):
        self.chat_list_box.get_current_chat().stop_message()

    @Gtk.Template.Callback()
    def send_message(self, button=None):
        if button and not button.get_visible():
            return
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False):
            return
        current_chat = self.chat_list_box.get_current_chat()
        if current_chat.busy == True:
            return

        self.chat_list_box.send_tab_to_top(self.chat_list_box.get_selected_row())

        current_model = self.model_manager.get_selected_model()
        if current_model is None:
            self.show_toast(_("Please select a model before chatting"), self.main_overlay)
            return
        message_id = self.generate_uuid()

        attached_images = []
        attached_files = {}
        for name, content in self.attachments.items():
            if content["type"] == 'image':
                if self.model_manager.verify_if_image_can_be_used():
                    attached_images.append(os.path.join(data_dir, "chats", current_chat.get_name(), message_id, name))
            else:
                attached_files[os.path.join(data_dir, "chats", current_chat.get_name(), message_id, name)] = content['type']
            if not os.path.exists(os.path.join(data_dir, "chats", current_chat.get_name(), message_id)):
                os.makedirs(os.path.join(data_dir, "chats", current_chat.get_name(), message_id))
            shutil.copy(content['path'], os.path.join(data_dir, "chats", current_chat.get_name(), message_id, name))
            content["button"].get_parent().remove(content["button"])
        self.attachments = {}
        self.attachment_box.set_visible(False)
        raw_message = self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        current_chat.add_message(message_id, None)
        m_element = current_chat.messages[message_id]

        if len(attached_files) > 0:
            m_element.add_attachments(attached_files)
        if len(attached_images) > 0:
            m_element.add_images(attached_images)
        m_element.set_text(raw_message)
        m_element.add_footer(datetime.now())
        m_element.add_action_buttons()

        data = {
            "model": current_model,
            "messages": self.convert_history_to_ollama(current_chat),
            "options": {"temperature": self.ollama_instance.tweaks["temperature"], "seed": self.ollama_instance.tweaks["seed"]},
            "keep_alive": f"{self.ollama_instance.tweaks['keep_alive']}m",
            "stream": True
        }

        self.message_text_view.get_buffer().set_text("", 0)

        bot_id=self.generate_uuid()
        current_chat.add_message(bot_id, current_model)
        m_element_bot = current_chat.messages[bot_id]
        m_element_bot.set_text()
        threading.Thread(target=self.run_message, args=(data, m_element_bot, current_chat)).start()

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
            self.powersaver_warning_switch.set_active(True)

    @Gtk.Template.Callback()
    def switch_run_on_background(self, switch, user_data):
        logger.debug("Switching run on background")
        self.set_hide_on_close(switch.get_active())
        self.save_server_config()
    
    @Gtk.Template.Callback()
    def switch_powersaver_warning(self, switch, user_data):
        logger.debug("Switching powersaver warning banner")
        if switch.get_active():
            self.banner.set_revealed(Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled())
        else:
            self.banner.set_revealed(False)
        self.save_server_config()

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        with open(os.path.join(data_dir, "chats", "selected_chat.txt"), 'w') as f:
            f.write(self.chat_list_box.get_selected_row().chat_window.get_name())
        if self.get_hide_on_close():
            logger.info("Hiding app...")
        else:
            logger.info("Closing app...")
            self.ollama_instance.stop()
            self.get_application().quit()

    @Gtk.Template.Callback()
    def model_spin_changed(self, spin):
        value = spin.get_value()
        if spin.get_name() != "temperature":
            value = round(value)
        else:
            value = round(value, 1)
        if self.ollama_instance.tweaks[spin.get_name()] != value:
            self.ollama_instance.tweaks[spin.get_name()] = value
            self.save_server_config()

    @Gtk.Template.Callback()
    def instance_idle_timer_changed(self, spin):
        self.ollama_instance.idle_timer_delay = round(spin.get_value())
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
        threading.Thread(target=self.model_manager.pull_model, kwargs={"model_name": name, "modelfile": '\n'.join(modelfile)}).start()
        self.navigation_view_manage_models.pop()

    @Gtk.Template.Callback()
    def override_changed(self, entry):
        name = entry.get_name()
        value = entry.get_text()
        if self.ollama_instance:
            if value:
                self.ollama_instance.overrides[name] = value
            elif name in self.ollama_instance.overrides:
                del self.ollama_instance.overrides[name]
            if not self.ollama_instance.remote:
                self.ollama_instance.reset()
            self.save_server_config()

    @Gtk.Template.Callback()
    def link_button_handler(self, button):
        os.system(f'xdg-open "{button.get_name()}"'.replace("{selected_chat}", self.chat_list_box.get_current_chat().get_name()))

    @Gtk.Template.Callback()
    def model_search_toggle(self, button):
        self.model_searchbar.set_search_mode(button.get_active())
        self.model_manager.pulling_list.set_visible(not button.get_active() and len(list(self.model_manager.pulling_list)) > 0)
        self.model_manager.local_list.set_visible(not button.get_active() and len(list(self.model_manager.local_list)) > 0)

    @Gtk.Template.Callback()
    def message_search_toggle(self, button):
        self.message_searchbar.set_search_mode(button.get_active())

    @Gtk.Template.Callback()
    def model_search_changed(self, entry):
        results = 0
        if self.model_manager:
            for model in list(self.model_manager.available_list):
                model.set_visible(re.search(entry.get_text(), '{} {} {} {} {}'.format(model.get_name(), model.model_title, model.model_author, model.model_description, (_('image') if model.image_recognition else '')), re.IGNORECASE))
                if model.get_visible():
                    results += 1
            if entry.get_text() and results == 0:
                self.no_results_page.set_visible(True)
                self.model_scroller.set_visible(False)
            else:
                self.model_scroller.set_visible(True)
                self.no_results_page.set_visible(False)

    @Gtk.Template.Callback()
    def message_search_changed(self, entry, current_chat=None):
        search_term=entry.get_text()
        results = 0
        if not current_chat:
            current_chat = self.chat_list_box.get_current_chat()
        if current_chat:
            for key, message in current_chat.messages.items():
                if message and message.text:
                    message.set_visible(re.search(search_term, message.text, re.IGNORECASE))
                    for block in message.content_children:
                        if isinstance(block, message_widget.text_block):
                            if search_term:
                                highlighted_text = re.sub(f"({re.escape(search_term)})", r"<span background='yellow' bgalpha='30%'>\1</span>", block.get_text(),flags=re.IGNORECASE)
                                block.set_markup(highlighted_text)
                            else:
                                block.set_markup(block.get_text())

    @Gtk.Template.Callback()
    def on_clipboard_paste(self, textview):
        logger.debug("Pasting from clipboard")
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self.cb_text_received)
        clipboard.read_texture_async(None, self.cb_image_received)

    def convert_model_name(self, name:str, mode:int) -> str: # mode=0 name:tag -> Name (tag)   |   mode=1 Name (tag) -> name:tag
        try:
            if mode == 0:
                return "{} ({})".format(name.split(":")[0].replace("-", " ").title(), name.split(":")[1])
            if mode == 1:
                return "{}:{}".format(name.split(" (")[0].replace(" ", "-").lower(), name.split(" (")[1][:-1])
        except Exception as e:
            pass

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
        if new_text != text:
            editable.stop_emission_by_name("insert-text")

    def create_model(self, model:str, file:bool):
        modelfile_buffer = self.create_model_modelfile.get_buffer()
        modelfile_buffer.delete(modelfile_buffer.get_start_iter(), modelfile_buffer.get_end_iter())
        self.create_model_system.set_text('')
        if not file:
            response = self.ollama_instance.request("POST", "api/show", json.dumps({"name": self.convert_model_name(model, 1)}))
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

    def preview_file(self, file_path, file_type, presend_name):
        logger.debug(f"Previewing file: {file_path}")
        file_path = file_path.replace("{selected_chat}", self.chat_list_box.get_current_chat().get_name())
        if not os.path.isfile(file_path):
            self.show_toast(_("Missing file"), self.main_overlay)
            return
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

    def convert_history_to_ollama(self, chat):
        messages = []
        for message_id, message in chat.messages_to_dict().items():
            new_message = message.copy()
            if 'model' in new_message:
                del new_message['model']
            if 'date' in new_message:
                del new_message['date']
            if 'files' in message and len(message['files']) > 0:
                del new_message['files']
                new_message['content'] = ''
                for name, file_type in message['files'].items():
                    file_path = os.path.join(data_dir, "chats", chat.get_name(), message_id, name)
                    file_data = self.get_content_of_file(file_path, file_type)
                    if file_data:
                        new_message['content'] += f"```[{name}]\n{file_data}\n```"
                new_message['content'] += message['content']
            if 'images' in message and len(message['images']) > 0:
                new_message['images'] = []
                for name in message['images']:
                    file_path = os.path.join(data_dir, "chats", chat.get_name(), message_id, name)
                    image_data = self.get_content_of_file(file_path, 'image')
                    if image_data:
                        new_message['images'].append(image_data)
            messages.append(new_message)
        return messages

    def generate_chat_title(self, message, old_chat_name):
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
        current_model = self.model_manager.get_selected_model()
        data = {"model": current_model, "prompt": prompt, "stream": False}
        if 'images' in message:
            data["images"] = message['images']
        response = self.ollama_instance.request("POST", "api/generate", json.dumps(data))
        if response.status_code == 200:
            new_chat_name = json.loads(response.text)["response"].strip().removeprefix("Title: ").removeprefix("title: ").strip('\'"').replace('\n', ' ').title().replace('\'S', '\'s')
            new_chat_name = new_chat_name[:50] + (new_chat_name[50:] and '...')
            self.chat_list_box.rename_chat(old_chat_name, new_chat_name)

    def save_server_config(self):
        if self.ollama_instance:
            with open(os.path.join(config_dir, "server.json"), "w+", encoding="utf-8") as f:
                data = {
                    'remote_url': self.ollama_instance.remote_url,
                    'remote_bearer_token': self.ollama_instance.bearer_token,
                    'run_remote': self.ollama_instance.remote,
                    'local_port': self.ollama_instance.local_port,
                    'run_on_background': self.background_switch.get_active(),
                    'powersaver_warning': self.powersaver_warning_switch.get_active(),
                    'model_tweaks': self.ollama_instance.tweaks,
                    'ollama_overrides': self.ollama_instance.overrides,
                    'idle_timer': self.ollama_instance.idle_timer_delay
                }

                json.dump(data, f, indent=6)

    def verify_connection(self):
        try:
            response = self.ollama_instance.request("GET", "api/tags")
            if response.status_code == 200:
                self.save_server_config()
                #self.update_list_local_models()
            return response.status_code == 200
        except Exception as e:
            logger.error(e)
            return False

    def on_theme_changed(self, manager, dark, buffer):
        logger.debug("Theme changed")
        if manager.get_dark():
            source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark')
        else:
            source_style = GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita')
        buffer.set_style_scheme(source_style)

    def switch_send_stop_button(self, send:bool):
        self.stop_button.set_visible(not send)
        self.send_button.set_visible(send)

    def run_message(self, data:dict, message_element:message_widget.message, chat:chat_widget.chat):
        logger.debug("Running message")
        self.save_history(chat)
        chat.busy = True
        self.chat_list_box.get_tab_by_name(chat.get_name()).spinner.set_visible(True)
        if len(data['messages']) == 1 and chat.get_name().startswith(_("New Chat")):
            threading.Thread(target=self.generate_chat_title, args=(data['messages'][0].copy(), chat.get_name())).start()

        if chat.welcome_screen:
            chat.welcome_screen.set_visible(False)
        if chat.regenerate_button:
            chat.container.remove(chat.regenerate_button)
        self.switch_send_stop_button(False)
        if self.regenerate_button:
            GLib.idle_add(self.chat_list_box.get_current_chat().remove, self.regenerate_button)
        try:
            response = self.ollama_instance.request("POST", "api/chat", json.dumps(data), lambda data, message_element=message_element: message_element.update_message(data))
            if response.status_code != 200:
                raise Exception('Network Error')
        except Exception as e:
            logger.error(e)
            self.chat_list_box.get_tab_by_name(chat.get_name()).spinner.set_visible(False)
            chat.busy = False
            GLib.idle_add(message_element.add_action_buttons)
            if message_element.spinner:
                GLib.idle_add(message_element.container.remove, message_element.spinner)
                message_element.spinner = None
            GLib.idle_add(chat.show_regenerate_button, message_element)
            GLib.idle_add(self.connection_error)


    def save_history(self, chat:chat_widget.chat=None):
        logger.info("Saving history")
        history = None
        if chat and os.path.exists(os.path.join(data_dir, "chats", "chats.json")):
            history = {'chats': {chat.get_name(): {'messages': chat.messages_to_dict()}}}
            try:
                with open(os.path.join(data_dir, "chats", "chats.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for chat_tab in self.chat_list_box.tab_list:
                        if chat_tab.chat_window.get_name() != chat.get_name():
                            history['chats'][chat_tab.chat_window.get_name()] = data['chats'][chat_tab.chat_window.get_name()]
                history['chats'][chat.get_name()] = {'messages': chat.messages_to_dict()}
            except Exception as e:
                logger.error(e)
                history = None
        if not history:
            history = {'chats': {}}
            for chat_tab in self.chat_list_box.tab_list:
                history['chats'][chat_tab.chat_window.get_name()] = {'messages': chat_tab.chat_window.messages_to_dict()}

        with open(os.path.join(data_dir, "chats", "chats.json"), "w+", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

    def load_history(self):
        logger.debug("Loading history")
        if os.path.exists(os.path.join(data_dir, "chats", "chats.json")):
            try:
                with open(os.path.join(data_dir, "chats", "chats.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    selected_chat = None
                    if len(list(data)) == 0:
                        data['chats'][_("New Chat")] = {"messages": {}}
                    if os.path.exists(os.path.join(data_dir, "chats", "selected_chat.txt")):
                        with open(os.path.join(data_dir, "chats", "selected_chat.txt"), 'r') as scf:
                            selected_chat = scf.read()
                    elif 'selected_chat' in data and data['selected_chat'] in data['chats']:
                        selected_chat = data['selected_chat']
                    if not selected_chat or selected_chat not in data['chats']:
                        selected_chat = list(data['chats'])[0]
                    if len(data['chats'][selected_chat]['messages'].keys()) > 0:
                        last_model_used = data['chats'][selected_chat]['messages'][list(data["chats"][selected_chat]["messages"])[-1]]["model"]
                        self.model_manager.change_model(last_model_used)
                    for chat_name in data['chats']:
                        self.chat_list_box.append_chat(chat_name)
                        chat_container = self.chat_list_box.get_chat_by_name(chat_name)
                        if chat_name == selected_chat:
                            self.chat_list_box.select_row(self.chat_list_box.tab_list[-1])
                        chat_container.load_chat_messages(data['chats'][chat_name]['messages'])

            except Exception as e:
                logger.error(e)
                self.chat_list_box.prepend_chat(_("New Chat"))
        else:
            self.chat_list_box.prepend_chat(_("New Chat"))


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

    def connection_error(self):
        logger.error("Connection error")
        if self.ollama_instance.remote:
            options = {
                _("Close Alpaca"): {"callback": lambda *_: self.get_application().quit(), "appearance": "destructive"},
                _("Use Local Instance"): {"callback": lambda *_: window.remote_connection_switch.set_active(False)},
                _("Connect"): {"callback": lambda url, bearer: generic_actions.connect_remote(url,bearer), "appearance": "suggested"}
            }
            entries = [
                {"text": self.ollama_instance.remote_url, "css": ['error'], "placeholder": _('Server URL')},
                {"text": self.ollama_instance.bearer_token, "css": ['error'] if self.ollama_instance.bearer_token else None, "placeholder": _('Bearer Token (Optional)')}
            ]
            dialog_widget.Entry(_('Connection Error'), _('The remote instance has disconnected'), list(options)[0], options, entries)
        else:
            self.ollama_instance.reset()
            self.show_toast(_("There was an error with the local Ollama instance, so it has been reset"), self.main_overlay)

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
        if self.file_preview_dialog.get_visible():
            self.file_preview_dialog.close()

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
            button.connect("clicked", lambda button : self.preview_file(file_path, file_type, file_name))
            self.attachment_container.append(button)
            self.attachment_box.set_visible(True)

    def chat_actions(self, action, user_data):
        chat_row = self.selected_chat_row
        chat_name = chat_row.label.get_label()
        action_name = action.get_name()
        if action_name in ('delete_chat', 'delete_current_chat'):
            dialog_widget.simple(
                _('Delete Chat?'),
                _("Are you sure you want to delete '{}'?").format(chat_name),
                lambda chat_name=chat_name, *_: self.chat_list_box.delete_chat(chat_name),
                _('Delete'),
                'destructive'
            )
        elif action_name in ('duplicate_chat', 'duplicate_current_chat'):
            self.chat_list_box.duplicate_chat(chat_name)
        elif action_name in ('rename_chat', 'rename_current_chat'):
            dialog_widget.simple_entry(
                _('Rename Chat?'),
                _("Renaming '{}'").format(chat_name),
                lambda new_chat_name, old_chat_name=chat_name, *_: self.chat_list_box.rename_chat(old_chat_name, new_chat_name),
                {'placeholder': _('Chat name')},
                _('Rename')
            )
        elif action_name in ('export_chat', 'export_current_chat'):
            self.chat_list_box.export_chat(chat_name)

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
                    yt = YouTube(text)
                    captions = yt.captions
                    if len(captions) == 0:
                        self.show_toast(_("This video does not have any transcriptions"), self.main_overlay)
                        return
                    video_title = yt.title
                    dialog_widget.simple_dropdown(
                        _('Attach YouTube Video?'),
                        _('{}\n\nPlease select a transcript to include').format(video_title),
                        lambda caption_name, video_url=text: generic_actions.attach_youtube(video_url, caption_name),
                        ["{} ({})".format(caption.name.title(), caption.code) for caption in captions]
                    )
                except Exception as e:
                    logger.error(e)
                    self.show_toast(_("This video is not available"), self.main_overlay)
            elif url_regex.match(text):
                dialog_widget.simple(
                    _('Attach Website? (Experimental)'),
                    _("Are you sure you want to attach\n'{}'?").format(text),
                    lambda url=text: generic_actions.attach_website(url)
                )
        except Exception as e:
            logger.error(e)

    def cb_image_received(self, clipboard, result):
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                if self.model_manager.verify_if_image_can_be_used():
                    pixbuf = Gdk.pixbuf_get_from_texture(texture)
                    if not os.path.exists(os.path.join(cache_dir, 'tmp/images/')):
                        os.makedirs(os.path.join(cache_dir, 'tmp/images/'))
                    image_name = self.generate_numbered_name('image.png', os.listdir(os.path.join(cache_dir, os.path.join(cache_dir, 'tmp/images'))))
                    pixbuf.savev(os.path.join(cache_dir, 'tmp/images/{}'.format(image_name)), "png", [], [])
                    self.attach_file(os.path.join(cache_dir, 'tmp/images/{}'.format(image_name)), 'image')
                else:
                    self.show_toast(_("Image recognition is only available on specific models"), self.main_overlay)
        except Exception as e:
            pass

    def handle_enter_key(self):
        self.send_message()
        return True

    def on_file_drop(self, drop_target, value, x, y):
        files = value.get_files()
        for file in files:
            extension = os.path.splitext(file.get_path())[1][1:]
            if extension in ('png', 'jpeg', 'jpg', 'webp', 'gif'):
                self.attach_file(file.get_path(), 'image')
            elif extension in ('txt', 'md', 'html', 'css', 'js', 'py', 'java', 'json', 'xml'):
                self.attach_file(file.get_path(), 'plain_text')
            elif extension == 'pdf':
                self.attach_file(file.get_path(), 'pdf')

    def power_saver_toggled(self, monitor):
        self.banner.set_revealed(monitor.get_power_saver_enabled() and self.powersaver_warning_switch.get_active())

    def remote_switched(self, switch, state):
        def local_instance_process():
            switch.set_sensitive(False)
            self.ollama_instance.remote = False
            self.ollama_instance.start()
            self.model_manager.update_local_list()
            self.save_server_config()
            switch.set_sensitive(True)

        if state:
            options = {
                _("Cancel"): {"callback": lambda *_: self.remote_connection_switch.set_active(False)},
                _("Connect"): {"callback": lambda url, bearer: generic_actions.connect_remote(url, bearer), "appearance": "suggested"}
            }
            entries = [
                {"text": self.ollama_instance.remote_url, "placeholder": _('Server URL')},
                {"text": self.ollama_instance.bearer_token, "placeholder": _('Bearer Token (Optional)')}
            ]
            dialog_widget.Entry(
                _('Connect Remote Instance'),
                _('Enter instance information to continue'),
                list(options)[0],
                options,
                entries
            )
        elif self.ollama_instance.remote:
            threading.Thread(target=local_instance_process).start()

    def prepare_alpaca(self, local_port:int, remote_url:str, remote:bool, tweaks:dict, overrides:dict, bearer_token:str, idle_timer_delay:int, save:bool):
        #Model Manager
        self.model_manager = model_widget.model_manager_container()
        self.model_scroller.set_child(self.model_manager)

        #Chat History
        self.load_history()

        #Instance
        self.ollama_instance = connection_handler.instance(local_port, remote_url, remote, tweaks, overrides, bearer_token, idle_timer_delay)

        #Model Manager P.2
        self.model_manager.update_available_list()
        self.model_manager.update_local_list()

        #User Preferences
        for element in list(list(list(list(self.tweaks_group)[0])[1])[0]):
            if element.get_name() in self.ollama_instance.tweaks:
                element.set_value(self.ollama_instance.tweaks[element.get_name()])

        for element in list(list(list(list(self.overrides_group)[0])[1])[0]):
            if element.get_name() in self.ollama_instance.overrides:
                element.set_text(self.ollama_instance.overrides[element.get_name()])

        self.set_hide_on_close(self.background_switch.get_active())

        self.remote_connection_switch.get_activatable_widget().handler_block(self.remote_connection_switch_handler)
        self.remote_connection_switch.set_active(self.ollama_instance.remote)
        self.remote_connection_switch.get_activatable_widget().handler_unblock(self.remote_connection_switch_handler)
        self.instance_idle_timer.set_value(self.ollama_instance.idle_timer_delay)

        #Save preferences
        if save:
            self.save_server_config()
        self.send_button.set_sensitive(True)
        self.attachment_button.set_sensitive(True)
        self.get_application().lookup_action('manage_models').set_enabled(True)
        self.get_application().lookup_action('preferences').set_enabled(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_searchbar.connect('notify::search-mode-enabled', lambda *_: self.message_search_button.set_active(self.message_searchbar.get_search_mode()))
        message_widget.window = self
        chat_widget.window = self
        model_widget.window = self
        dialog_widget.window = self
        terminal_widget.window = self
        generic_actions.window = self
        connection_handler.window = self

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.on_file_drop)
        self.message_text_view.add_controller(drop_target)

        self.chat_list_box = chat_widget.chat_list()
        self.chat_list_container.set_child(self.chat_list_box)
        GtkSource.init()
        if not os.path.exists(os.path.join(data_dir, "chats")):
            os.makedirs(os.path.join(data_dir, "chats"))
        enter_key_controller = Gtk.EventControllerKey.new()
        enter_key_controller.connect("key-pressed", lambda controller, keyval, keycode, state: self.handle_enter_key() if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK) else None)
        self.message_text_view.add_controller(enter_key_controller)
        self.set_help_overlay(self.shortcut_window)
        self.get_application().set_accels_for_action("win.show-help-overlay", ['<primary>slash'])

        universal_actions = {
            'new_chat': [lambda *_: self.chat_list_box.new_chat(), ['<primary>n']],
            'clear': [lambda *i: dialog_widget.simple(_('Clear Chat?'), _('Are you sure you want to clear the chat?'), self.chat_list_box.get_current_chat().clear_chat, _('Clear')), ['<primary>e']],
            'import_chat': [lambda *_: self.chat_list_box.import_chat(), ['<primary>i']],
            'create_model_from_existing': [lambda *i: dialog_widget.simple_dropdown(_('Select Model'), _('This model will be used as the base for the new model'), lambda model: self.create_model(model, False), self.model_manager.get_model_list())],
            'create_model_from_file': [lambda *i, file_filter=self.file_filter_gguf: dialog_widget.simple_file(file_filter, lambda file: self.create_model(file.get_path(), True))],
            'create_model_from_name': [lambda *i: dialog_widget.simple_entry(_('Pull Model'), _('Input the name of the model in this format\nname:tag'), lambda model: threading.Thread(target=self.model_manager.pull_model, kwargs={"model_name": model}).start(), {'placeholder': 'llama3.2:latest'})],
            'duplicate_chat': [self.chat_actions],
            'duplicate_current_chat': [self.current_chat_actions],
            'delete_chat': [self.chat_actions],
            'delete_current_chat': [self.current_chat_actions],
            'rename_chat': [self.chat_actions],
            'rename_current_chat': [self.current_chat_actions, ['F2']],
            'export_chat': [self.chat_actions],
            'export_current_chat': [self.current_chat_actions],
            'toggle_sidebar': [lambda *_: self.split_view_overlay.set_show_sidebar(not self.split_view_overlay.get_show_sidebar()), ['F9']],
            'manage_models': [lambda *_: self.manage_models_dialog.present(self), ['<primary>m']],
            'search_messages': [lambda *_: self.message_searchbar.set_search_mode(not self.message_searchbar.get_search_mode()), ['<primary>f']]
        }

        for action_name, data in universal_actions.items():
            self.get_application().create_action(action_name, data[0], data[1] if len(data) > 1 else None)

        self.get_application().lookup_action('manage_models').set_enabled(False)
        self.get_application().lookup_action('preferences').set_enabled(False)
        self.remote_connection_switch_handler = self.remote_connection_switch.get_activatable_widget().connect('state-set', self.remote_switched)

        self.file_preview_remove_button.connect('clicked', lambda button : dialog_widget.simple(_('Remove Attachment?'), _("Are you sure you want to remove attachment?"), lambda button=button: self.remove_attached_file(button.get_name()), _('Remove'), 'destructive'))
        self.attachment_button.connect("clicked", lambda button, file_filter=self.file_filter_attachments: dialog_widget.simple_file(file_filter, generic_actions.attach_file))
        self.create_model_name.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_']))
        self.set_focus(self.message_text_view)
        if os.path.exists(os.path.join(config_dir, "server.json")):
            try:
                with open(os.path.join(config_dir, "server.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.background_switch.set_active(data['run_on_background'])                    
                    if 'idle_timer' not in data:
                        data['idle_timer'] = 0
                    if 'powersaver_warning' not in data:
                        data['powersaver_warning'] = True
                    self.powersaver_warning_switch.set_active(data['powersaver_warning'])
                    threading.Thread(target=self.prepare_alpaca, args=(data['local_port'], data['remote_url'], data['run_remote'], data['model_tweaks'], data['ollama_overrides'], data['remote_bearer_token'], round(data['idle_timer']), False)).start()
            except Exception as e:
                logger.error(e)
                threading.Thread(target=self.prepare_alpaca, args=(11435, '', False, {'temperature': 0.7, 'seed': 0, 'keep_alive': 5}, {}, '', 0, True)).start()
                self.powersaver_warning_switch.set_active(True)
        else:
            if shutil.which('ollama'):
                threading.Thread(target=self.prepare_alpaca, args=(11435, '', False, {'temperature': 0.7, 'seed': 0, 'keep_alive': 5}, {}, '', 0, True)).start()
            else:
                threading.Thread(target=self.prepare_alpaca, args=(11435, 'http://0.0.0.0:11434', True, {'temperature': 0.7, 'seed': 0, 'keep_alive': 5}, {}, '', 0, True)).start()
            self.welcome_dialog.present(self)

        if self.powersaver_warning_switch.get_active():
            self.banner.set_revealed(Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled())
            
        Gio.PowerProfileMonitor.dup_default().connect("notify::power-saver-enabled", lambda monitor, *_: self.power_saver_toggled(monitor))
        self.banner.connect('button-clicked', lambda *_: self.banner.set_revealed(False))
