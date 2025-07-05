# window.py
#
# Copyright 2024-2025 Jeffser
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

import json
import threading
import os
import re
import gettext
import shutil
import logging
import time
import requests
import sys
import icu
import tempfile
import importlib.util
import numpy as np

from datetime import datetime

import gi

gi.require_version('Spelling', '1')

from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, Spelling

from .sql_manager import generate_uuid, generate_numbered_name, prettify_model_name, Instance as SQL
from . import widgets as Widgets
from .constants import SPEACH_RECOGNITION_LANGUAGES, TTS_VOICES, STT_MODELS, data_dir, source_dir, cache_dir


logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'AlpacaWindow'

    localedir = os.path.join(source_dir, 'locale')

    gettext.bindtextdomain('com.jeffser.Alpaca', localedir)
    gettext.textdomain('com.jeffser.Alpaca')
    _ = gettext.gettext

    #Variables
    attachments = {}

    #Elements
    zoom_spin = Gtk.Template.Child()
    local_model_stack = Gtk.Template.Child()
    available_model_stack = Gtk.Template.Child()
    model_manager_stack = Gtk.Template.Child()
    instance_manager_stack = Gtk.Template.Child()
    main_navigation_view = Gtk.Template.Child()
    local_model_flowbox = Gtk.Template.Child()
    available_model_flowbox = Gtk.Template.Child()
    split_view_overlay = Gtk.Template.Child()
    selected_chat_row : Gtk.ListBoxRow = None
    preferences_dialog = Gtk.Template.Child()
    welcome_carousel = Gtk.Template.Child()
    welcome_previous_button = Gtk.Template.Child()
    welcome_next_button = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()
    chat_bin = Gtk.Template.Child()
    chat_list_stack = Gtk.Template.Child()
    global_footer_container = Gtk.Template.Child()
    model_searchbar = Gtk.Template.Child()
    searchentry_models = Gtk.Template.Child()
    model_search_button = Gtk.Template.Child()
    message_searchbar = Gtk.Template.Child()
    searchentry_messages = Gtk.Template.Child()
    title_stack = Gtk.Template.Child()
    title_no_model_button = Gtk.Template.Child()
    model_filter_button = Gtk.Template.Child()
    background_switch = Gtk.Template.Child()

    file_filter_db = Gtk.Template.Child()
    file_filter_gguf = Gtk.Template.Child()

    chat_list_container = Gtk.Template.Child()
    chat_list_box = Gtk.Template.Child()

    powersaver_warning_switch = Gtk.Template.Child()
    mic_group = Gtk.Template.Child()
    tts_group = Gtk.Template.Child()
    mic_auto_send_switch = Gtk.Template.Child()
    mic_language_combo = Gtk.Template.Child()
    mic_model_combo = Gtk.Template.Child()
    tts_voice_combo = Gtk.Template.Child()
    tts_auto_mode_combo = Gtk.Template.Child()

    banner = Gtk.Template.Child()

    model_dropdown = Gtk.Template.Child()
    notice_dialog = Gtk.Template.Child()

    instance_preferences_page = Gtk.Template.Child()
    instance_listbox = Gtk.Template.Child()
    available_models_stack_page = Gtk.Template.Child()
    model_creator_stack_page = Gtk.Template.Child()
    install_ollama_button = Gtk.Template.Child()
    tool_listbox = Gtk.Template.Child()
    model_manager_bottom_view_switcher = Gtk.Template.Child()
    model_manager_top_view_switcher = Gtk.Template.Child()
    last_selected_instance_row = None


    @Gtk.Template.Callback()
    def closing_notice(self, dialog):
        self.settings.set_string('last-notice-seen', dialog.get_name())

    @Gtk.Template.Callback()
    def add_instance(self, button):
        def selected(ins):
            if ins.instance_type == 'ollama:managed' and not shutil.which('ollama'):
                Widgets.dialog.simple(
                    parent = button.get_root(),
                    heading = _("Ollama Was Not Found"),
                    body = _("To add a managed Ollama instance, you must have Ollama installed locally in your device, this is a simple process and should not take more than 5 minutes."),
                    callback = lambda: Gio.AppInfo.launch_default_for_uri('https://github.com/Jeffser/Alpaca/wiki/Installing-Ollama'),
                    button_name = _("Open Tutorial in Web Browser")
                )
            else:
                instance = ins(
                    instance_id=generate_uuid(),
                    properties={}
                )
                Widgets.instances.InstancePreferencesGroup(instance).present(self)

        options = {}
        for ins_type in Widgets.instances.ready_instances:
            options[ins_type.instance_type_display] = ins_type

        Widgets.dialog.simple_dropdown(
            parent = button.get_root(),
            heading = _("Add Instance"),
            body = _("Select a type of instance to add"),
            callback = lambda option, options=options: selected(options[option]),
            items = options.keys()
        )

    @Gtk.Template.Callback()
    def instance_changed(self, listbox, row):
        def change_instance():
            if self.last_selected_instance_row:
                self.last_selected_instance_row.instance.stop()

            self.last_selected_instance_row = row

            GLib.idle_add(Widgets.models.update_added_model_list, self)
            GLib.idle_add(Widgets.models.update_available_model_list, self)

            if row:
                self.settings.set_string('selected-instance', row.instance.instance_id)

            GLib.idle_add(self.chat_list_box.get_selected_row().update_profile_pictures)
        if listbox.get_sensitive():
            threading.Thread(target=change_instance).start()

    @Gtk.Template.Callback()
    def model_creator_gguf(self, button):
        def result(file):
            try:
                file_path = file.get_path()
            except Exception as e:
                return
            Widgets.models.creator.ModelCreatorDialog(self.get_current_instance(), file_path, True).present(self)

        Widgets.dialog.simple_file(
            parent = self,
            file_filters = [self.file_filter_gguf],
            callback = result
        )

    @Gtk.Template.Callback()
    def model_creator_existing(self, button, selected_model:str=None):
        Widgets.models.creator.ModelCreatorDialog(self.get_current_instance(), selected_model, False).present(self)

    @Gtk.Template.Callback()
    def model_manager_stack_changed(self, viewstack, params):
        self.local_model_flowbox.unselect_all()
        self.available_model_flowbox.unselect_all()
        self.model_search_button.set_sensitive(viewstack.get_visible_child_name() not in ('model_creator', 'instances'))
        self.model_search_button.set_active(self.model_search_button.get_active() and viewstack.get_visible_child_name() not in ('model_creator', 'instances'))

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
            self.settings.set_boolean('skip-welcome', True)
            self.main_navigation_view.replace_with_tags(['chat'])

    @Gtk.Template.Callback()
    def zoom_changed(self, spinner):
        settings = Gtk.Settings.get_default()
        settings.reset_property('gtk-xft-dpi')
        settings.set_property('gtk-xft-dpi',  settings.get_property('gtk-xft-dpi') + (int(spinner.get_value()) - 100) * 400)

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        def close():
            selected_chat = self.chat_list_box.get_selected_row()
            self.settings.set_string('default-chat', selected_chat.chat.chat_id)
            self.get_current_instance().stop()
            if Widgets.voice.message_dictated:
                Widgets.voice.message_dictated.popup.tts_button.set_active(False)
            self.get_application().quit()

        def switch_to_hide():
            self.set_hide_on_close(True)
            self.close() #Recalls this function

        if self.get_hide_on_close():
            logger.info("Hiding app...")
        else:
            logger.info("Closing app...")
            if any([chat_row.chat.busy for chat_row in list(self.chat_list_box)]) or any([el for el in list(self.local_model_flowbox) if isinstance(el.get_child(), Widgets.models.pulling.PullingModelButton)]):
                options = {
                    _('Cancel'): {'default': True},
                    _('Hide'): {'callback': switch_to_hide},
                    _('Close'): {'callback': close, 'appearance': 'destructive'},
                }
                Widgets.dialog.Options(
                    heading = _('Close Alpaca?'),
                    body = _('A task is currently in progress. Are you sure you want to close Alpaca?'),
                    close_response = list(options.keys())[0],
                    options = options,
                ).show(self)
                return True
            else:
                close()

    @Gtk.Template.Callback()
    def link_button_handler(self, button):
        try:
            Gio.AppInfo.launch_default_for_uri(button.get_name())
        except Exception as e:
            logger.error(e)

    @Gtk.Template.Callback()
    def chat_search_changed(self, entry):
        chat_results = 0
        for row in list(self.chat_list_box):
            string_search = re.search(entry.get_text(), row.get_name(), re.IGNORECASE)
            row.set_visible(string_search)
            chat_results += 1 if string_search else 0
        if chat_results > 0:
            self.chat_list_stack.set_visible_child_name('content')
        else:
            self.chat_list_stack.set_visible_child_name('no-results')

    @Gtk.Template.Callback()
    def model_search_changed(self, entry):
        filtered_categories = set()
        if self.model_filter_button.get_popover():
            filtered_categories = set([c.get_name() for c in list(self.model_filter_button.get_popover().get_child()) if c.get_active()])
        results_local = False

        if len(list(self.local_model_flowbox)) > 0:
            for model in list(self.local_model_flowbox):
                string_search = re.search(entry.get_text(), model.get_child().get_search_string(), re.IGNORECASE)
                category_filter = len(filtered_categories) == 0 or model.get_child().get_search_categories() & filtered_categories or not self.model_searchbar.get_search_mode()
                model.set_visible(string_search and category_filter)
                results_local = results_local or model.get_visible()
                if not model.get_visible() and model in self.local_model_flowbox.get_selected_children():
                    self.local_model_flowbox.unselect_all()
            self.local_model_stack.set_visible_child_name('content' if results_local or not entry.get_text() else 'no-results')
        else:
            self.local_model_stack.set_visible_child_name('no-models')

        results_available = False
        if len(Widgets.models.common.available_models_data) > 0:
            self.available_models_stack_page.set_visible(True)
            self.model_creator_stack_page.set_visible(True)
            for model in list(self.available_model_flowbox):
                string_search = re.search(entry.get_text(), model.get_child().get_search_string(), re.IGNORECASE)
                category_filter = len(filtered_categories) == 0 or model.get_child().get_search_categories() & filtered_categories or not self.model_searchbar.get_search_mode()
                model.set_visible(string_search and category_filter)
                results_available = results_available or model.get_visible()
                if not model.get_visible() and model in self.available_model_flowbox.get_selected_children():
                    self.available_model_flowbox.unselect_all()
            self.available_model_stack.set_visible_child_name('content' if results_available else 'no-results')
        else:
            self.available_models_stack_page.set_visible(False)
            self.model_creator_stack_page.set_visible(False)

    @Gtk.Template.Callback()
    def message_search_changed(self, entry, current_chat=None):
        search_term=entry.get_text()
        message_results = 0
        if not current_chat and self.chat_list_box.get_selected_row():
            current_chat = self.chat_list_box.get_selected_row().chat
        if current_chat:
            try:
                for message in list(current_chat.container):
                    if message:
                        content = message.get_content()
                        if content:
                            string_search = re.search(search_term, content, re.IGNORECASE)
                            message.set_visible(string_search)
                            message_results += 1 if string_search else 0
                            for block in list(message.block_container):
                                if isinstance(block, Widgets.blocks.text.Text):
                                    if search_term:
                                        highlighted_text = re.sub(f"({re.escape(search_term)})", r"<span background='yellow' bgalpha='30%'>\1</span>", block.get_content(),flags=re.IGNORECASE)
                                        block.set_markup(highlighted_text)
                                    else:
                                        block.set_content(block.get_content())
            except Exception as e:
                logger.error(e)
                pass
            if message_results > 0 or not search_term:
                if len(list(current_chat.container)) > 0:
                    current_chat.set_visible_child_name('content')
                else:
                    current_chat.set_visible_child_name('welcome-screen')
            else:
                current_chat.set_visible_child_name('no-results')

    def send_message(self, mode:int=0): #mode 0=user 1=system 2=tool
        buffer = self.global_footer.get_buffer()

        raw_message = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        if not raw_message:
            return

        current_chat = self.chat_list_box.get_selected_row().chat
        if current_chat.busy == True:
            return

        if self.get_current_instance().instance_type == 'empty':
            self.get_application().lookup_action('instance_manager').activate()
            return

        current_model = self.get_selected_model().get_name()
        if mode == 2 and len(Widgets.tools.get_enabled_tools(self.tool_listbox)) == 0:
            Widgets.dialog.show_toast(_("No tools enabled."), current_chat.get_root(), 'app.tool_manager', _('Open Tool Manager'))
            return
        if current_model is None:
            Widgets.dialog.show_toast(_("Please select a model before chatting"), current_chat.get_root())
            return

        # Bring tab to top
        tab = self.chat_list_box.get_selected_row()
        self.chat_list_box.unselect_all()
        self.chat_list_box.remove(tab)
        self.chat_list_box.prepend(tab)
        self.chat_list_box.select_row(tab)

        m_element = Widgets.message.Message(
            dt=datetime.now(),
            message_id=generate_uuid(),
            chat=current_chat,
            mode=0 if mode in (0,2) else 2
        )
        current_chat.add_message(m_element)

        for old_attachment in list(self.global_footer.attachment_container.container):
            attachment = m_element.add_attachment(
                file_id = generate_uuid(),
                name = old_attachment.file_name,
                attachment_type = old_attachment.file_type,
                content = old_attachment.file_content
            )
            old_attachment.delete()
            SQL.insert_or_update_attachment(m_element, attachment)

        m_element.block_container.set_content(raw_message)

        SQL.insert_or_update_message(m_element)

        buffer.set_text("", 0)

        if mode==0:
            m_element_bot = Widgets.message.Message(
                dt=datetime.now(),
                message_id=generate_uuid(),
                chat=current_chat,
                mode=1,
                author=current_model
            )
            current_chat.add_message(m_element_bot)
            SQL.insert_or_update_message(m_element_bot)
            if current_chat.chat_type == 'chat':
                threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model)).start()
            elif current_chat.chat_type == 'notebook':
                tls = Widgets.tools.NotebookTools
                if len(current_chat.get_notebook()) == 0:
                    tls = {Widgets.tools.notebook_tools.WriteNotebook.tool_metadata.get('name'): Widgets.tools.notebook_tools.WriteNotebook()}
                threading.Thread(target=self.get_current_instance().notebook_generation, args=(m_element_bot, current_model, tls)).start()
        elif mode==1:
            current_chat.set_visible_child_name('content')
        elif mode==2:
            m_element_bot = Widgets.message.Message(
                dt=datetime.now(),
                message_id=generate_uuid(),
                chat=current_chat,
                mode=1,
                author=current_model
            )
            current_chat.add_message(m_element_bot)
            SQL.insert_or_update_message(m_element_bot)
            threading.Thread(target=self.get_current_instance().use_tools, args=(m_element_bot, current_model, Widgets.tools.get_enabled_tools(self.tool_listbox), True)).start()

    def auto_select_model(self):
        def find_model_index(model_name:str) -> int:
            if len(list(self.model_dropdown.get_model())) == 0 or not model_name:
                return -1
            detected_models = [i for i, future_row in enumerate(list(self.model_dropdown.get_model())) if future_row.model.get_name() == model_name]
            if len(detected_models) > 0:
                return detected_models[0]
            return -1

        chat = self.chat_bin.get_child()
        if chat:
            model_index = -1
            if len(list(chat.container)) > 0:
                model_index = find_model_index(list(chat.container)[-1].get_model())
            if model_index == -1:
                model_index = find_model_index(self.get_current_instance().get_default_model())

            if model_index and model_index != -1:
                self.model_dropdown.set_selected(model_index)

    @Gtk.Template.Callback()
    def chat_changed(self, listbox, row):
        if row:
            # Discard Old Chat if Not Busy
            old_chat = self.chat_bin.get_child()
            if old_chat and not old_chat.busy:
                old_chat.unload_messages()
                old_chat.unrealize()

            # Load New Chat
            new_chat = row.chat
            if new_chat.get_parent():
                new_chat.get_parent().set_child(None)
            if new_chat.busy:
                self.get_root().global_footer.toggle_action_button(False)
            else:
                self.get_root().global_footer.toggle_action_button(True)
                new_chat.load_messages()

            # Show New Stack Page
            self.chat_bin.set_child(new_chat)

            # Select Model
            self.auto_select_model()

    def get_selected_model(self):
        selected_item = self.model_dropdown.get_selected_item()
        if selected_item:
            return selected_item.model
        else:
            return Widgets.models.added.FallbackModel

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        if length == 1:
            new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
            if new_text != text:
                editable.stop_emission_by_name("insert-text")

    def add_chat(self, chat_name:str, chat_id:str, chat_type:str, mode:int) -> Widgets.chat.Chat or None: #mode = 0: append, mode = 1: prepend
        chat_name = chat_name.strip()
        if chat_name and mode in (0, 1):
            chat_name = generate_numbered_name(chat_name, [row.get_name() for row in list(self.chat_list_box)])
            chat = None
            if chat_type == 'notebook':
                chat = Widgets.chat.Notebook(
                    chat_id=chat_id,
                    name=chat_name
                )
            else:
                chat = Widgets.chat.Chat(
                    chat_id=chat_id,
                    name=chat_name
                )

            if chat:
                if mode == 0:
                    self.chat_list_box.append(chat.row)
                else:
                    self.chat_list_box.prepend(chat.row)
                return chat

    def new_chat(self, chat_title:str=_("New Chat"), chat_type:str='chat') -> Widgets.chat.Chat or None:
        chat_title = chat_title.strip()
        if chat_title:
            chat = self.add_chat(
                chat_name=chat_title,
                chat_id=generate_uuid(),
                chat_type=chat_type,
                mode=1
            )
            SQL.insert_or_update_chat(chat)
            return chat

    def load_history(self):
        logger.debug("Loading history")
        selected_chat = self.settings.get_value('default-chat').unpack()
        chats = SQL.get_chats()
        if len(chats) > 0:
            threads = []
            if selected_chat not in [row[0] for row in chats]:
                selected_chat = chats[0][0]
            for row in chats:
                self.add_chat(
                    chat_name=row[1],
                    chat_id=row[0],
                    chat_type=row[2],
                    mode=0
                )
                if row[0] == selected_chat and len(list(self.chat_list_box)) > 0:
                    self.chat_list_box.select_row(list(self.chat_list_box)[-1])

        if len(list(self.chat_list_box)) == 0:
            self.chat_list_box.select_row(self.new_chat().row)
            self.chat_list_stack.set_visible_child_name('content')

    def get_current_instance(self):
        if self.instance_listbox.get_selected_row():
            return self.instance_listbox.get_selected_row().instance
        else:
            return Widgets.instances.Empty()

    def prepare_alpaca(self):
        self.main_navigation_view.replace_with_tags(['chat'])

        #Chat History
        self.load_history()

        threading.Thread(target=Widgets.tools.update_available_tools, args=(self.tool_listbox,)).start()

        if self.get_application().args.new_chat:
            self.new_chat(self.get_application().args.new_chat)

        self.mic_group.set_visible(importlib.util.find_spec('whisper'))
        self.tts_group.set_visible(importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'))

        string_list = Gtk.StringList()
        for model, size in STT_MODELS.items():
            string_list.append('{} ({})'.format(model.title(), size))
        self.mic_model_combo.set_model(string_list)
        self.settings.bind('stt-model', self.mic_model_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        string_list = Gtk.StringList()
        for lan in SPEACH_RECOGNITION_LANGUAGES:
            string_list.append('{} ({})'.format(icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title(), lan))
        self.mic_language_combo.set_model(string_list)
        self.settings.bind('stt-language', self.mic_language_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('stt-auto-send', self.mic_auto_send_switch, 'active', Gio.SettingsBindFlags.DEFAULT)

        string_list = Gtk.StringList()
        for name in TTS_VOICES:
            string_list.append(name)
        self.tts_voice_combo.set_model(string_list)
        self.settings.bind('tts-model', self.tts_voice_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('tts-auto-dictate', self.tts_auto_mode_combo, 'active', Gio.SettingsBindFlags.DEFAULT)

        # Ollama is available but there are no instances added
        if not any(i.get("type") == "ollama:managed" for i in SQL.get_instances()) and shutil.which("ollama"):
            SQL.insert_or_update_instance(
                instance_id=generate_uuid(),
                pinned=True,
                instance_type='ollama:managed',
                properties={
                    'name': 'Alpaca',
                    'url': 'http://127.0.0.1:11435',
                }
            )

        Widgets.instances.update_instance_list(
            instance_listbox=self.instance_listbox,
            selected_instance_id=self.settings.get_value('selected-instance').unpack()
        )

    def open_button_menu(self, gesture, x, y, menu):
        button = gesture.get_widget()
        popover = Gtk.PopoverMenu(
            menu_model=menu,
            has_arrow=False,
            halign=1
        )
        position = Gdk.Rectangle()
        position.x = x
        position.y = y
        popover.set_parent(button.get_child())
        popover.set_pointing_to(position)
        popover.popup()

    def on_chat_imported(self, file):
        if file:
            if os.path.isfile(os.path.join(cache_dir, 'import.db')):
                os.remove(os.path.join(cache_dir, 'import.db'))
            file.copy(Gio.File.new_for_path(os.path.join(cache_dir, 'import.db')), Gio.FileCopyFlags.OVERWRITE, None, None, None, None)
            for chat in SQL.import_chat(os.path.join(cache_dir, 'import.db'), [tab.chat.get_name() for tab in list(self.chat_list_box)]):
                self.add_chat(
                    chat_name=chat[1],
                    chat_id=chat[0],
                    chat_type='chat' if len(chat) == 2 else chat[2],
                    mode=1
                )
            Widgets.dialog.show_toast(_("Chat imported successfully"), self)

    def show_instance_manager(self):
        self.instance_preferences_page.set_sensitive(not any([tab.chat.busy for tab in list(self.chat_list_box)]))
        GLib.idle_add(self.main_navigation_view.push_by_tag, 'instance_manager')

    def toggle_searchbar(self):
        current_tag = self.main_navigation_view.get_visible_page_tag()

        searchbars = {
            'chat': self.message_searchbar,
            'model_manager': self.model_searchbar
        }

        if searchbars.get(current_tag):
            searchbars.get(current_tag).set_search_mode(not searchbars.get(current_tag).get_search_mode())

    def start_live_chat(self):
        if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
            self.get_application().create_live_chat().present()
        else:
            options = {_('Cancel'): {'default': True}}
            Widgets.dialog.Options(
                heading=_("Can't Run Live Chat"),
                body=_("You are missing TTS libraries"),
                close_response=list(options.keys())[0],
                options=options
            ).show(self)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.model_searchbar.connect_entry(self.searchentry_models)
        self.model_searchbar.connect('notify::search-mode-enabled', lambda *_: self.model_search_changed(self.searchentry_models))

        # Prepare model selector
        list(self.model_dropdown)[0].add_css_class('flat')
        self.model_dropdown.set_model(Gio.ListStore.new(Widgets.models.added.AddedModelRow))
        self.model_dropdown.set_expression(Gtk.PropertyExpression.new(Widgets.models.added.AddedModelRow, None, "name"))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.model_dropdown.set_factory(factory)
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)
        list(list(self.title_no_model_button.get_child())[0])[1].set_ellipsize(3)

        # Global Footer
        self.global_footer = Widgets.message.GlobalFooter()
        self.global_footer_container.set_child(self.global_footer)
        self.set_focus(self.global_footer.message_text_view)

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        for el in ("default-width", "default-height", "maximized", "hide-on-close"):
            self.settings.bind(el, self, el, Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('powersaver-warning', self.powersaver_warning_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('zoom', self.zoom_spin, 'value', Gio.SettingsBindFlags.DEFAULT)

        universal_actions = {
            'new_chat': [lambda *_: self.chat_list_box.select_row(self.new_chat().row), ['<primary>n']],
            'new_notebook': [lambda *_: self.new_chat(chat_type='notebook') if os.getenv("ALPACA_NOTEBOOK", "0") == "1" else None, ['<primary><shift>n']],
            'import_chat': [lambda *_: Widgets.dialog.simple_file(
                parent=self,
                file_filters=[self.file_filter_db],
                callback=self.on_chat_imported
            )],
            'duplicate_current_chat': [lambda *_: self.chat_list_box.get_selected_row().duplicate()],
            'delete_current_chat': [lambda *_: self.chat_list_box.get_selected_row().prompt_delete(), ['<primary>w']],
            'rename_current_chat': [lambda *_: self.chat_list_box.get_selected_row().prompt_rename(), ['F2']],
            'export_current_chat': [lambda *_: self.chat_list_box.get_selected_row().prompt_export()],
            'toggle_sidebar': [lambda *_: self.split_view_overlay.set_show_sidebar(not self.split_view_overlay.get_show_sidebar()), ['F9']],
            'toggle_search': [lambda *_: self.toggle_searchbar(), ['<primary>f']],
            'model_manager' : [lambda *i: GLib.idle_add(self.main_navigation_view.push_by_tag, 'model_manager') if self.main_navigation_view.get_visible_page().get_tag() != 'model_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>m']],
            'instance_manager' : [lambda *i: self.show_instance_manager() if self.main_navigation_view.get_visible_page().get_tag() != 'instance_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>i']],
            'download_model_from_name' : [lambda *i: Widgets.dialog.simple_entry(
                parent=self,
                heading=_('Download Model?'),
                body=_('Please enter the model name following this template: name:tag'),
                callback=lambda name: threading.Thread(target=Widgets.models.available.pull_model_confirm, args=(name, self.get_current_instance(), self)).start(),
                entries={'placeholder': 'deepseek-r1:7b'}
            )],
            'reload_added_models': [lambda *_: GLib.idle_add(Widgets.models.update_added_model_list, self)],
            'delete_all_chats': [lambda *i: self.get_visible_dialog().close() and Widgets.dialog.simple(
                parent=self,
                heading=_('Delete All Chats?'),
                body=_('Are you sure you want to delete all chats?'),
                callback=lambda: [GLib.idle_add(c.delete) for c in list(self.chat_list_box)],
                button_name=_('Delete'),
                button_appearance='destructive'
            )],
            'tool_manager': [lambda *i: GLib.idle_add(self.main_navigation_view.push_by_tag, 'tool_manager') if self.main_navigation_view.get_visible_page().get_tag() != 'tool_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>t']],
            'start_quick_ask': [lambda *_: self.get_application().create_quick_ask().present(), ['<primary><alt>a']],
            'start_live_chat': [lambda *_: self.start_live_chat(), ['<primary><alt>l']]
        }
        for action_name, data in universal_actions.items():
            self.get_application().create_action(action_name, data[0], data[1] if len(data) > 1 else None)

        #self.model_creator_name.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))
        #self.model_creator_tag.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))
        #TODO

        def verify_powersaver_mode():
            self.banner.set_revealed(
                Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled() and
                self.settings.get_value('powersaver-warning').unpack() and
                self.get_current_instance().instance_type == 'ollama:managed'
            )
        Gio.PowerProfileMonitor.dup_default().connect("notify::power-saver-enabled", lambda *_: verify_powersaver_mode())
        self.banner.connect('button-clicked', lambda *_: self.banner.set_revealed(False))


        if shutil.which('ollama'):
            text = _('Already Installed!')
            self.install_ollama_button.set_label(text)
            self.install_ollama_button.set_tooltip_text(text)
            self.install_ollama_button.set_sensitive(False)

        self.prepare_alpaca()
        if self.settings.get_value('skip-welcome').unpack():
            if not self.settings.get_value('last-notice-seen').unpack() == self.notice_dialog.get_name():
                self.notice_dialog.present(self)
        else:
            self.main_navigation_view.replace_with_tags(['welcome'])


