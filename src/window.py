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
import numpy as np

from datetime import datetime

import gi
from pydbus import SessionBus, Variant

gi.require_version('GtkSource', '5')
gi.require_version('Spelling', '1')

from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, Spelling

from .sql_manager import generate_uuid, generate_numbered_name, Instance as SQL
from . import widgets as Widgets
from .constants import SPEACH_RECOGNITION_LANGUAGES, TTS_VOICES, TTS_AUTO_MODES, STT_MODELS, data_dir, source_dir

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
    split_view_overlay_model_manager = Gtk.Template.Child()
    split_view_overlay = Gtk.Template.Child()
    selected_chat_row : Gtk.ListBoxRow = None
    preferences_dialog = Gtk.Template.Child()
    welcome_carousel = Gtk.Template.Child()
    welcome_previous_button = Gtk.Template.Child()
    welcome_next_button = Gtk.Template.Child()
    main_overlay = Gtk.Template.Child()
    chat_stack = Gtk.Template.Child()
    chat_list_stack = Gtk.Template.Child()
    message_text_view = None
    message_text_view_scrolled_window = Gtk.Template.Child()
    quick_ask_text_view_scrolled_window = Gtk.Template.Child()
    action_button_stack = Gtk.Template.Child()
    bottom_chat_controls_container = Gtk.Template.Child()
    attachment_button = Gtk.Template.Child()
    chat_right_click_menu = Gtk.Template.Child()
    send_message_menu = Gtk.Template.Child()
    attachment_menu = Gtk.Template.Child()
    model_searchbar = Gtk.Template.Child()
    searchentry_models = Gtk.Template.Child()
    model_search_button = Gtk.Template.Child()
    message_searchbar = Gtk.Template.Child()
    searchentry_messages = Gtk.Template.Child()
    title_stack = Gtk.Template.Child()
    title_no_model_button = Gtk.Template.Child()
    model_filter_button = Gtk.Template.Child()

    file_filter_db = Gtk.Template.Child()
    file_filter_gguf = Gtk.Template.Child()

    chat_list_container = Gtk.Template.Child()
    chat_list_box = Gtk.Template.Child()
    model_manager = None
    global_attachment_container = None

    background_switch = Gtk.Template.Child()
    powersaver_warning_switch = Gtk.Template.Child()
    mic_auto_send_switch = Gtk.Template.Child()
    mic_language_combo = Gtk.Template.Child()
    mic_model_combo = Gtk.Template.Child()
    tts_voice_combo = Gtk.Template.Child()
    tts_auto_mode_combo = Gtk.Template.Child()

    banner = Gtk.Template.Child()

    quick_ask = Gtk.Template.Child()
    quick_ask_overlay = Gtk.Template.Child()
    quick_ask_save_button = Gtk.Template.Child()

    model_creator_stack = Gtk.Template.Child()
    model_creator_base = Gtk.Template.Child()
    model_creator_profile_picture = Gtk.Template.Child()
    model_creator_name = Gtk.Template.Child()
    model_creator_tag = Gtk.Template.Child()
    model_creator_context = Gtk.Template.Child()
    model_creator_imagination = Gtk.Template.Child()
    model_creator_focus = Gtk.Template.Child()
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

    SQL.initialize()

    # tts
    message_dictated = None

    @Gtk.Template.Callback()
    def microphone_toggled(self, button):
        language=SQL.get_preference('mic_language')
        text_view = list(button.get_parent().get_parent())[0].get_child()
        buffer = text_view.get_buffer()
        model_name = os.getenv("ALPACA_SPEECH_MODEL", "base")

        def recognize_audio(model, audio_data, current_iter):
            result = model.transcribe(audio_data, language=language)
            if len(result.get("text").encode('utf8')) == 0:
                self.mic_timeout += 1
            else:
                GLib.idle_add(buffer.insert, current_iter, result.get("text"), len(result.get("text").encode('utf8')))
                self.mic_timeout = 0

        def run_mic(pulling_model:Gtk.Widget=None):
            GLib.idle_add(button.get_parent().set_visible_child_name, "loading")
            import whisper
            import pyaudio
            GLib.idle_add(button.add_css_class, 'accent')

            samplerate=16000
            p = pyaudio.PyAudio()
            model = None

            self.mic_timeout=0

            try:
                model = whisper.load_model(model_name, download_root=os.path.join(data_dir, 'whisper'))
                if pulling_model:
                    GLib.idle_add(pulling_model.update_progressbar, {'status': 'success'})
            except Exception as e:
                Widgets.dialog.simple_error(
                    parent = button.get_root(),
                    title = _('Speech Recognition Error'),
                    body = _('An error occurred while pulling speech recognition model'),
                    error_log = e
                )
                logger.error(e)
            GLib.idle_add(button.get_parent().set_visible_child_name, "button")

            if model:
                stream = p.open(
                    format=pyaudio.paInt16,
                    rate=samplerate,
                    input=True,
                    frames_per_buffer=1024,
                    channels=1
                )

                try:
                    while button.get_active():
                        frames = []
                        for i in range(0, int(samplerate / 1024 * 2)):
                            data = stream.read(1024, exception_on_overflow=False)
                            frames.append(np.frombuffer(data, dtype=np.int16))
                        audio_data = np.concatenate(frames).astype(np.float32) / 32768.0
                        threading.Thread(target=recognize_audio, args=(model, audio_data, buffer.get_end_iter())).start()

                        if self.mic_timeout >= 2 and SQL.get_preference('mic_auto_send', False) and buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False):
                            if text_view.get_name() == 'main_text_view':
                                GLib.idle_add(self.send_message)
                            elif text_view.get_name() == 'quick_chat_text_view':
                                GLib.idle_add(self.quick_chat, buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False), 0)
                            break

                except Exception as e:
                    Widgets.dialog.simple_error(
                        parent = button.get_root(),
                        heading = _('Speech Recognition Error'),
                        body = _('An error occurred while using speech recognition'),
                        error_log = e
                    )
                    logger.error(e)
                finally:
                    stream.stop_stream()
                    stream.close()
                    p.terminate()

            if button.get_active():
                button.set_active(False)

        def prepare_download():
            pulling_model = Widgets.model_manager.PullingModel(model_name, Widgets.model_manager.add_speech_to_text_model, False)
            self.local_model_flowbox.prepend(pulling_model)
            threading.Thread(target=run_mic, args=(pulling_model,)).start()

        if button.get_active():
            if os.path.isfile(os.path.join(data_dir, 'whisper', '{}.pt'.format(model_name))):
                threading.Thread(target=run_mic).start()
            else:
                Widgets.dialog.simple(
                    parent = button.get_root(),
                    heading = _("Download Speech Recognition Model"),
                    body = _("To use speech recognition you'll need to download a special model ({})").format(STT_MODELS.get(model_name, '~151mb')),
                    callback = prepare_download,
                    button_name = _("Download Model")
                )
        else:
            button.remove_css_class('accent')
            button.set_sensitive(False)
            GLib.timeout_add(2000, lambda button: button.set_sensitive(True) and False, button)


    @Gtk.Template.Callback()
    def closing_notice(self, dialog):
        SQL.insert_or_update_preferences({"last_notice_seen": dialog.get_name()})

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
                tbv=Adw.ToolbarView()
                tbv.add_top_bar(Adw.HeaderBar())
                tbv.set_content(ins().get_preferences_page())
                self.main_navigation_view.push(Adw.NavigationPage(title=_('Add Instance'), tag='instance', child=tbv))

        options = {}
        for ins_type in Widgets.instance_manager.ready_instances:
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
        """
        This method is called when the selected instance changes.
        It updates corresponding UI elements, selections and internal variables.
        """

        def change_instance():
            if self.last_selected_instance_row:
                self.last_selected_instance_row.instance.stop()

            self.last_selected_instance_row = row

            Widgets.model_manager.update_local_model_list()
            Widgets.model_manager.update_available_model_list()

            self.available_models_stack_page.set_visible(len(Widgets.model_manager.available_models) > 0)
            self.model_creator_stack_page.set_visible(len(Widgets.model_manager.available_models) > 0)

            if row:
                SQL.insert_or_update_preferences({'selected_instance': row.instance.instance_id})

            self.chat_list_box.get_selected_row().update_profile_pictures()
            visible_model_manger_switch = len([p for p in self.model_manager_stack.get_pages() if p.get_visible()]) > 1

            self.model_manager_bottom_view_switcher.set_visible(visible_model_manger_switch)
            self.model_manager_top_view_switcher.set_visible(visible_model_manger_switch)
        if listbox.get_sensitive():
            threading.Thread(target=change_instance).start()


    @Gtk.Template.Callback()
    def model_creator_accept(self, button):
        profile_picture = self.model_creator_profile_picture.get_subtitle()
        model_name = '{}:{}'.format(self.model_creator_name.get_text(), self.model_creator_tag.get_text() if self.model_creator_tag.get_text() else 'latest').replace(' ', '-').lower()
        context_buffer = self.model_creator_context.get_buffer()
        system_message = context_buffer.get_text(context_buffer.get_start_iter(), context_buffer.get_end_iter(), False).replace('"', '\\"')
        top_k = self.model_creator_imagination.get_value()
        top_p = self.model_creator_focus.get_value() / 100

        found_models = [row.model for row in list(self.model_dropdown.get_model()) if row.model.get_name() == model_name]
        if not found_models:
            if profile_picture:
                SQL.insert_or_update_model_picture(model_name, Widgets.attachments.extract_image(profile_picture, 128))

            data_json = {
                'model': model_name,
                'system': system_message,
                'parameters': {
                    'top_k': top_k,
                    'top_p': top_p
                },
                'stream': True
            }

            if self.model_creator_base.get_subtitle():
                gguf_path = self.model_creator_base.get_subtitle()
                Widgets.model_manager.create_model(data_json, gguf_path)
            else:
                data_json['from'] = self.convert_model_name(self.model_creator_base.get_selected_item().get_string(), 1)
                Widgets.model_manager.create_model(data_json)

    @Gtk.Template.Callback()
    def model_creator_cancel(self, button):
        self.model_creator_stack.set_visible_child_name('introduction')

    @Gtk.Template.Callback()
    def model_creator_load_profile_picture(self, button):
        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        Widgets.dialog.simple_file(
            parent = button.get_root(),
            file_filters = [file_filter],
            callback = lambda file: self.model_creator_profile_picture.set_subtitle(file.get_path())
        )

    @Gtk.Template.Callback()
    def model_creator_base_changed(self, comborow, params):
        model_name = comborow.get_selected_item().get_string()
        if model_name != 'GGUF' and not comborow.get_subtitle():
            model_name = self.convert_model_name(model_name, 1)

            GLib.idle_add(self.model_creator_name.set_text, model_name.split(':')[0])
            GLib.idle_add(self.model_creator_tag.set_text, 'custom')

            system = None
            modelfile = None

            found_models = [row.model for row in list(self.model_dropdown.get_model()) if row.model.get_name() == model_name]
            if found_models:
                system = found_models[0].data.get('system')
                modelfile = found_models[0].data.get('modelfile')

            if system:
                context_buffer = self.model_creator_context.get_buffer()
                GLib.idle_add(context_buffer.delete, context_buffer.get_start_iter(), context_buffer.get_end_iter())
                GLib.idle_add(context_buffer.insert_at_cursor, system, len(system))

            if modelfile:
                for line in modelfile.splitlines():
                    if line.startswith('PARAMETER top_k'):
                        top_k = int(line.split(' ')[2])
                        GLib.idle_add(self.model_creator_imagination.set_value, top_k)
                    elif line.startswith('PARAMETER top_p'):
                        top_p = int(float(line.split(' ')[2]) * 100)
                        GLib.idle_add(self.model_creator_focus.set_value, top_p)

    @Gtk.Template.Callback()
    def model_creator_gguf(self, button):
        def result(file):
            try:
                file_path = file.get_path()
            except Exception as e:
                return
            context_buffer = self.model_creator_context.get_buffer()
            context_buffer.delete(context_buffer.get_start_iter(), context_buffer.get_end_iter())
            self.model_creator_profile_picture.set_subtitle('')
            string_list = Gtk.StringList()
            string_list.append('GGUF')
            self.model_creator_base.set_model(string_list)
            self.model_creator_base.set_subtitle(file_path)
            self.model_creator_stack.set_visible_child_name('content')

        Widgets.dialog.simple_file(
            parent = button.get_root(),
            file_filters = [self.file_filter_gguf],
            callback = result
        )

    @Gtk.Template.Callback()
    def model_creator_existing(self, button, selected_model:str=None):
        GLib.idle_add(self.model_manager_stack.set_visible_child_name, 'model_creator')
        context_buffer = self.model_creator_context.get_buffer()
        context_buffer.delete(context_buffer.get_start_iter(), context_buffer.get_end_iter())
        GLib.idle_add(self.model_creator_profile_picture.set_subtitle, '')
        GLib.idle_add(self.model_creator_base.set_subtitle, '')
        string_list = Gtk.StringList()
        if selected_model:
            GLib.idle_add(string_list.append, self.convert_model_name(selected_model, 0))
        else:
            [GLib.idle_add(string_list.append, value.model_title) for value in Widgets.model_manager.get_local_models().values()]
        GLib.idle_add(self.model_creator_base.set_model, string_list)
        GLib.idle_add(self.model_creator_stack.set_visible_child_name, 'content')

    @Gtk.Template.Callback()
    def model_manager_stack_changed(self, viewstack, params):
        self.local_model_flowbox.unselect_all()
        self.available_model_flowbox.unselect_all()
        self.model_creator_stack.set_visible_child_name('introduction')
        self.model_search_button.set_sensitive(viewstack.get_visible_child_name() not in ('model_creator', 'instances'))
        self.model_search_button.set_active(self.model_search_button.get_active() and viewstack.get_visible_child_name() not in ('model_creator', 'instances'))

    @Gtk.Template.Callback()
    def model_manager_child_activated(self, flowbox, selected_child):
        self.split_view_overlay_model_manager.set_show_sidebar(selected_child)
        self.set_focus(selected_child.get_child().get_default_widget())

    @Gtk.Template.Callback()
    def model_manager_child_selected(self, flowbox):
        def set_default_sidebar():
            time.sleep(1)
            if not self.split_view_overlay_model_manager.get_show_sidebar():
                tbv = Adw.ToolbarView()
                tbv.add_top_bar(
                    Adw.HeaderBar(
                        show_back_button=False,
                        show_title=False
                    )
                )
                tbv.set_content(Adw.StatusPage(icon_name='brain-augemnted-symbolic'))
                GLib.idle_add(self.split_view_overlay_model_manager.set_sidebar, tbv)

        selected_children = flowbox.get_selected_children()
        if len(selected_children) > 0:
            self.split_view_overlay_model_manager.set_show_sidebar(True)
            model = selected_children[0].get_child()
            buttons, content = model.get_page()

            tbv = Adw.ToolbarView()
            hb = Adw.HeaderBar(
                show_back_button=False,
                show_title=False
            )
            tbv.add_top_bar(hb)
            for btn in buttons:
                hb.pack_start(btn)
            tbv.set_content(Gtk.ScrolledWindow(
                vexpand=True
            ))
            tbv.get_content().set_child(content)
            self.split_view_overlay_model_manager.set_sidebar(tbv)
        else:
            self.split_view_overlay_model_manager.set_show_sidebar(False)
            threading.Thread(target=set_default_sidebar).start()

    @Gtk.Template.Callback()
    def stop_message(self, button=None):
        self.chat_list_box.get_selected_row().chat.stop_message()

    @Gtk.Template.Callback()
    def send_message(self, button=None, mode:int=0): #mode 0=user 1=system 2=tool
        if button and not button.get_visible():
            return
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False):
            return
        current_chat = self.chat_list_box.get_selected_row().chat
        if current_chat.busy == True:
            return

        if self.get_current_instance().instance_type == 'empty':
            self.get_application().lookup_action('instance_manager').activate()
            return

        current_model = Widgets.model_manager.get_selected_model().get_name()
        if mode == 2 and len(Widgets.tools.get_enabled_tools(self.tool_listbox)) == 0:
            Widgets.dialog.show_toast(_("No tools enabled."), current_chat.get_root(), 'app.tool_manager', _('Open Tool Manager'))
            return
        if 'ollama' in self.get_current_instance().instance_type and mode == 2 and 'tools' not in Widgets.model_manager.available_models.get(current_model.split(':')[0], {}).get('categories', []):
            Widgets.dialog.show_toast(_("'{}' does not support tools.").format(self.convert_model_name(current_model, 0)), current_chat.get_root(), 'app.model_manager', _('Open Model Manager'))
            return
        if current_model is None:
            Widgets.dialog.show_toast(_("Please select a model before chatting"), current_chat.get_root())
            return

        tab = self.chat_list_box.get_selected_row()
        self.chat_list_box.unselect_all()
        self.chat_list_box.remove(tab)
        self.chat_list_box.prepend(tab)
        self.chat_list_box.select_row(tab)

        raw_message = self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        m_element = Widgets.message.Message(
            dt=datetime.now(),
            message_id=generate_uuid(),
            chat=current_chat,
            mode=0 if mode in (0,2) else 2
        )
        current_chat.add_message(m_element)

        for old_attachment in list(self.global_attachment_container.container):
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

        self.message_text_view.get_buffer().set_text("", 0)

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
            SQL.insert_or_update_preferences({'skip_welcome_page': True})
            self.prepare_alpaca()

    @Gtk.Template.Callback()
    def zoom_changed(self, spinner, force:bool=False):
        if force or SQL.get_preference('zoom', 100) != int(spinner.get_value()):
            threading.Thread(target=SQL.insert_or_update_preferences, args=({'zoom': int(spinner.get_value())},)).start()
            settings = Gtk.Settings.get_default()
            settings.reset_property('gtk-xft-dpi')
            settings.set_property('gtk-xft-dpi',  settings.get_property('gtk-xft-dpi') + (int(spinner.get_value()) - 100) * 400)

    @Gtk.Template.Callback()
    def switch_run_on_background(self, switch, user_data):
        if switch.get_sensitive():
            self.set_hide_on_close(switch.get_active())
            SQL.insert_or_update_preferences({'run_on_background': switch.get_active()})
    
    @Gtk.Template.Callback()
    def switch_mic_auto_send(self, switch, user_data):
        if switch.get_sensitive():
            SQL.insert_or_update_preferences({'mic_auto_send': switch.get_active()})

    @Gtk.Template.Callback()
    def selected_mic_model(self, combo, user_data):
        if combo.get_sensitive():
            model = combo.get_selected_item().get_string().split(' (')[0].lower()
            if model:
                SQL.insert_or_update_preferences({'mic_model': model})

    @Gtk.Template.Callback()
    def selected_mic_language(self, combo, user_data):
        if combo.get_sensitive():
            language = combo.get_selected_item().get_string().split(' (')[-1][:-1]
            if language:
                SQL.insert_or_update_preferences({'mic_language': language})

    @Gtk.Template.Callback()
    def selected_tts_voice(self, combo, user_data):
        if combo.get_sensitive():
            language = TTS_VOICES.get(combo.get_selected_item().get_string())
            if language:
                SQL.insert_or_update_preferences({'tts_voice': language})

    @Gtk.Template.Callback()
    def selected_tts_auto_mode(self, combo, user_data):
        if combo.get_sensitive():
            mode = TTS_AUTO_MODES.get(combo.get_selected_item().get_string())
            if mode:
                SQL.insert_or_update_preferences({'tts_auto_mode': mode})

    @Gtk.Template.Callback()
    def switch_powersaver_warning(self, switch, user_data):
        if switch.get_sensitive():
            if switch.get_active():
                self.banner.set_revealed(Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled() and self.get_current_instance().instance_type == 'ollama:managed')
            else:
                self.banner.set_revealed(False)
            SQL.insert_or_update_preferences({'powersaver_warning': switch.get_active()})

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        def close():
            selected_chat = self.chat_list_box.get_selected_row().get_name()
            SQL.insert_or_update_preferences({'selected_chat': selected_chat})
            self.get_current_instance().stop()
            if self.message_dictated:
                self.message_dictated.footer.popup.tts_button.set_active(False)
            self.get_application().quit()

        def switch_to_hide():
            self.set_hide_on_close(True)
            self.close() #Recalls this function

        if self.get_hide_on_close():
            logger.info("Hiding app...")
        else:
            logger.info("Closing app...")
            if any([chat_row.chat.busy for chat_row in list(self.chat_list_box)]) or any([el for el in list(self.local_model_flowbox) if isinstance(el.get_child(), Widgets.model_manager.PullingModel)]):
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
            self.local_model_stack.set_visible_child_name('content' if results_local else 'no-results')
        else:
            self.local_model_stack.set_visible_child_name('no-models')

        results_available = False
        if len(Widgets.model_manager.available_models) > 0:
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
                print(e)
                pass
        if message_results > 0 or not search_term:
            if len(list(current_chat.container)) > 0:
                current_chat.set_visible_child_name('content')
            else:
                current_chat.set_visible_child_name('welcome-screen')
        else:
            current_chat.set_visible_child_name('no-results')


    def convert_model_name(self, name:str, mode:int): # mode=0 name:tag -> Name (tag)   |   mode=1 Name (tag) -> name:tag   |   mode=2 name:tag -> name, tag
        try:
            if mode == 0:
                if ':' in name:
                    name = name.split(':')
                    if name[1].lower() in ('latest', 'custom'):
                        return name[0].replace('-', ' ').title()
                    else:
                        return '{} ({})'.format(name[0].replace('-', ' ').title(), name[1].replace('-', ' ').title())
                else:
                    return name.replace('-', ' ').title()
            elif mode == 1:
                if ' (' in name:
                    name = name.split(' (')
                    return '{}:{}'.format(name[0].replace(' ', '-').lower(), name[1][:-1].replace(' ', '-').lower())
                else:
                    return name.replace(' ', '-').lower()
            elif mode == 2:
                if ':' in name:
                    name = name.split(':')
                    return name[0].replace('-', ' ').title(), name[1].replace('-', ' ').title()
                else:
                    return name.replace('-', ' ').title(), None


        except Exception as e:
            pass

    @Gtk.Template.Callback()
    def quick_ask_save(self, button):
        self.quick_ask.close()
        chat = self.quick_ask_overlay.get_child()
        chat_name = generate_numbered_name(chat.get_name(), [tab.get_name() for tab in list(self.chat_list_box)])
        new_chat = self.new_chat(chat_name)
        for message in list(chat.container):
            SQL.insert_or_update_message(message, new_chat.chat_id)
        threading.Thread(target=new_chat.load_chat_messages).start()
        self.present()

    @Gtk.Template.Callback()
    def closing_quick_ask(self, user_data):
        if not self.get_visible():
            self.closing_app(None)

    @Gtk.Template.Callback()
    def chat_changed(self, listbox, future_row):
        def find_model_index(model_name:str):
            if len(list(self.model_dropdown.get_model())) == 0:
                return None
            detected_models = [i for i, future_row in enumerate(list(self.model_dropdown.get_model())) if future_row.model.get_name() == model_name]
            if len(detected_models) > 0:
                return detected_models[0]

        if future_row:
            current_row = next((t for t in list(self.chat_list_box) if t.chat == self.chat_stack.get_visible_child()), future_row)
            if list(self.chat_list_box).index(future_row) != list(self.chat_list_box).index(current_row) or future_row.chat.get_visible_child_name() != 'content':
                # Empty Search
                if self.searchentry_messages.get_text() != '':
                    self.searchentry_messages.set_text('')
                    self.message_search_changed(self.searchentry_messages, self.chat_stack.get_visible_child())
                self.message_searchbar.set_search_mode(False)

                load_chat_thread = None
                # Load future_row if not loaded already
                if len(list(future_row.chat.container)) == 0:
                    load_chat_thread = threading.Thread(target=future_row.chat.load_messages)
                    load_chat_thread.start()

                # Unload current_row
                if not current_row.chat.busy and current_row.chat.get_visible_child_name() == 'content' and len(list(current_row.chat.container)) > 0:
                    threading.Thread(target=current_row.chat.unload_messages).start()

                # Select transition type and change chat
                self.chat_stack.set_transition_type(4 if list(self.chat_list_box).index(future_row) > list(self.chat_list_box).index(current_row) else 5)
                self.chat_stack.set_visible_child(future_row.chat)

                # Sync stop/send button to chat's state
                self.switch_send_stop_button(not future_row.chat.busy)
                if load_chat_thread:
                    load_chat_thread.join()
                # Select the correct model for the chat
                model_to_use_index = find_model_index(self.get_current_instance().get_default_model())
                print(self.get_current_instance().get_default_model(), model_to_use_index)
                if len(list(future_row.chat.container)) > 0:
                    message_model = find_model_index(list(future_row.chat.container)[-1].get_model())
                    if message_model:
                        model_to_use_index = message_model

                if model_to_use_index is None:
                    model_to_use_index = 0

                self.model_dropdown.set_selected(model_to_use_index)

                # If it has the "new message" indicator, hide it
                if future_row.indicator.get_visible():
                    future_row.indicator.set_visible(False)

    def on_clipboard_paste(self, textview):
        logger.debug("Pasting from clipboard")
        clipboard = Gdk.Display.get_default().get_clipboard()
        #clipboard.read_text_async(None, lambda clipboard, result: self.cb_text_received(clipboard.read_text_finish(result)))
        clipboard.read_texture_async(None, self.cb_image_received)

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        if length == 1:
            new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
            if new_text != text:
                editable.stop_emission_by_name("insert-text")

    def show_notification(self, title:str, body:str, icon:Gio.ThemedIcon=None):
        if not self.is_active() and not self.quick_ask.is_active():
            body = body.replace('<span>', '').replace('</span>', '')
            logger.info(f"{title}, {body}")
            notification = Gio.Notification.new(title)
            notification.set_body(body)
            if icon:
                notification.set_icon(icon)
            self.get_application().send_notification(None, notification)

    def switch_send_stop_button(self, send:bool):
        self.action_button_stack.set_visible_child_name('send' if send else 'stop')

    def add_chat(self, chat_name:str, chat_id:str, chat_type:str, mode:int) -> Widgets.chat.Chat or None: #mode = 0: append, mode = 1: prepend
        chat_name = chat_name.strip()
        if chat_name and mode in (0, 1):
            chat_name = generate_numbered_name(chat_name, [row.get_name() for row in list(self.chat_list_box)])
            chat = None
            if chat_type == 'chat':
                chat = Widgets.chat.Chat(
                    chat_id=chat_id,
                    name=chat_name
                )
            elif chat_type == 'notebook':
                chat = Widgets.chat.Notebook(
                    chat_id=chat_id,
                    name=chat_name
                )
            if chat:
                if mode == 0:
                    self.chat_list_box.append(chat.row)
                else:
                    self.chat_list_box.prepend(chat.row)
                self.chat_stack.add_child(chat)
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
        selected_chat = SQL.get_preference('selected_chat')
        chats = SQL.get_chats()
        if len(chats) > 0:
            threads = []
            if selected_chat not in [row[1] for row in chats]:
                selected_chat = chats[0][1]
            for row in chats:
                self.add_chat(
                    chat_name=row[1],
                    chat_id=row[0],
                    chat_type=row[2],
                    mode=0
                )
                if row[1] == selected_chat:
                    self.chat_list_box.select_row(list(self.chat_list_box)[-1])
        else:
            self.chat_list_box.new_chat(chat_type='chat')

    def chat_actions(self, action, user_data):
        chat = self.selected_chat_row.chat
        action_name = action.get_name()
        if action_name in ('delete_chat', 'delete_current_chat'):
            chat.row.prompt_delete()
        elif action_name in ('duplicate_chat', 'duplicate_current_chat'):
            chat.row.duplicate()
        elif action_name in ('rename_chat', 'rename_current_chat'):
            chat.row.prompt_rename()
        elif action_name in ('export_chat', 'export_current_chat'):
            chat.row.prompt_export()

    def current_chat_actions(self, action, user_data):
        self.selected_chat_row = self.chat_list_box.get_selected_row()
        self.chat_actions(action, user_data)

    def attach_youtube(self, yt_url:str, caption_id:str):
        file_name, content = Widgets.attachments.extract_youtube_content(yt_url, caption_id)
        attachment = Widgets.attachments.Attachment(
            file_id="-1",
            file_name=file_name,
            file_type='youtube',
            file_content=content
        )
        self.global_attachment_container.add_attachment(attachment)

    def attach_website(self, url:str):
        content = Widgets.attachments.extract_content("website", url)
        website_title = 'website'
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            website_title = match.group(1)
        attachment = Widgets.attachments.Attachment(
            file_id="-1",
            file_name=website_title,
            file_type="website",
            file_content=content
        )
        self.global_attachment_container.add_attachment(attachment)

    def youtube_detected(self, video_url:str):
        try:
            response = requests.get('https://noembed.com/embed?url={}'.format(video_url))
            data = json.loads(response.text)

            transcriptions = Widgets.attachments.get_youtube_transcripts(data['url'].split('=')[1])
            if len(transcriptions) == 0:
                GLib.idle_add(Widgets.dialog.show_toast, _("This video does not have any transcriptions"), self)
                return

            if not any(filter(lambda x: '(en' in x and 'auto-generated' not in x and len(transcriptions) > 1, transcriptions)):
                transcriptions.insert(1, 'English (translate:en)')

            GLib.idle_add(Widgets.dialog.simple_dropdown,
                parent = self,
                heading = _('Attach YouTube Video?'),
                body = _('{}\n\nPlease select a transcript to include').format(data['title']),
                callback = lambda caption_name, video_url=video_url: threading.Thread(target=self.attach_youtube, args=(video_url, caption_name.split(' (')[-1][:-1])).start(),
                items = transcriptions
            )
        except Exception as e:
            logger.error(e)
            GLib.idle_add(Widgets.dialog.show_toast, _("Error attaching video, please try again"), self)
        GLib.idle_add(self.message_text_view_scrolled_window.set_sensitive, True)

    def cb_text_received(self, text):
        try:
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
                self.message_text_view_scrolled_window.set_sensitive(False)
                threading.Thread(target=self.youtube_detected, args=(text,)).start()
            elif url_regex.match(text):
                Widgets.dialog.simple(
                    parent = self,
                    heading = _('Attach Website? (Experimental)'),
                    body = _("Are you sure you want to attach\n'{}'?").format(text),
                    callback = lambda url=text: threading.Thread(target=self.attach_website, args=(url,)).start()
                )
        except Exception as e:
            logger.error(e)

    def cb_image_received(self, clipboard, result):
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                if Widgets.model_manager.get_selected_model().get_vision():
                    pixbuf = Gdk.pixbuf_get_from_texture(texture)
                    tdir = tempfile.TemporaryDirectory()
                    pixbuf.savev(os.path.join(tdir.name, 'image.png'), 'png', [], [])
                    os.system('ls {}'.format(tdir.name))
                    file = Gio.File.new_for_path(os.path.join(tdir.name, 'image.png'))
                    self.on_attachment(file)
                    tdir.cleanup()
                else:
                    Widgets.dialog.show_toast(_("Image recognition is only available on specific models"), self)
        except Exception as e:
            pass

    def on_file_drop(self, drop_target, value, x, y):
        files = value.get_files()
        for file in files:
            self.on_attachment(file)

    def prepare_quick_chat(self):
        self.quick_ask_save_button.set_sensitive(False)
        chat = Widgets.chat.Chat(
            name=_('Quick Ask')
        )
        chat.set_visible_child_name('welcome-screen')
        self.quick_ask_overlay.set_child(chat)

    def quick_chat(self, message:str, mode:int):
        if not message:
            return

        buffer = self.quick_ask_message_text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        self.quick_ask.present()
        default_model = self.get_current_instance().get_default_model()
        current_model = None
        if default_model:
            current_model = self.convert_model_name(default_model, 1)
        if current_model is None:
            Widgets.dialog.show_toast(_("Please select a model before chatting"), self.quick_ask)
            return
        chat = self.quick_ask_overlay.get_child()

        m_element = Widgets.message.Message(
            dt=datetime.now(),
            message_id=generate_uuid(),
            chat=chat,
            mode=0 if mode in (0,2) else 2
        )
        chat.add_message(m_element)
        m_element.block_container.set_content(message)

        if mode in (0, 2):
            m_element_bot = Widgets.message.Message(
                dt=datetime.now(),
                message_id=generate_uuid(),
                chat=chat,
                mode=1,
                author=current_model
            )
            chat.add_message(m_element_bot)

            chat.busy = True
            if mode == 0:
                threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model)).start()
            else:
                threading.Thread(target=self.get_current_instance().use_tools, args=(m_element_bot, current_model, Widgets.tools.get_enabled_tools(self.tool_listbox), True)).start()

    def get_current_instance(self):
        if self.instance_listbox.get_selected_row():
            return self.instance_listbox.get_selected_row().instance
        else:
            return Widgets.instance_manager.Empty()

    def prepare_alpaca(self):
        self.main_navigation_view.replace_with_tags(['chat'])
        # Notice
        if not SQL.get_preference('last_notice_seen') == self.notice_dialog.get_name():
            self.notice_dialog.present(self)

        #Chat History
        self.load_history()

        threading.Thread(target=Widgets.tools.update_available_tools, args=(self.tool_listbox,)).start()

        if self.get_application().args.new_chat:
            self.new_chat(self.get_application().args.new_chat)

        self.powersaver_warning_switch.set_active(SQL.get_preference('powersaver_warning', True))
        self.powersaver_warning_switch.set_sensitive(True)
        self.background_switch.set_active(SQL.get_preference('run_on_background', False))
        self.background_switch.set_sensitive(True)
        self.mic_auto_send_switch.set_active(SQL.get_preference('mic_auto_send', False))
        self.mic_auto_send_switch.set_sensitive(True)
        self.zoom_spin.set_value(SQL.get_preference('zoom', 100))
        self.zoom_spin.set_sensitive(True)
        self.zoom_changed(self.zoom_spin, True)
        self.global_attachment_container = Widgets.attachments.AttachmentContainer()
        self.bottom_chat_controls_container.prepend(self.global_attachment_container)

        selected_mic_model = SQL.get_preference('mic_model', 'base')
        selected_index = 0
        string_list = Gtk.StringList()
        for i, (model, size) in enumerate(STT_MODELS.items()):
            if model == selected_mic_model:
                selected_index = i
            string_list.append('{} ({})'.format(model.title(), size))

        self.mic_model_combo.set_model(string_list)
        self.mic_model_combo.set_selected(selected_index)
        self.mic_model_combo.set_sensitive(True)

        selected_language = SQL.get_preference('mic_language', 'en')
        selected_index = 0
        string_list = Gtk.StringList()
        for i, lan in enumerate(SPEACH_RECOGNITION_LANGUAGES):
            if lan == selected_language:
                selected_index = i
            string_list.append('{} ({})'.format(icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title(), lan))

        self.mic_language_combo.set_model(string_list)
        self.mic_language_combo.set_selected(selected_index)
        self.mic_language_combo.set_sensitive(True)

        selected_voice = SQL.get_preference('tts_voice', '')
        selected_index = 0
        string_list = Gtk.StringList()
        for i, (name, value) in enumerate(TTS_VOICES.items()):
            if value == selected_voice:
                selected_index = i
            string_list.append(name)

        self.tts_voice_combo.set_model(string_list)
        self.tts_voice_combo.set_selected(selected_index)
        self.tts_voice_combo.set_sensitive(True)

        selected_tts_mode = SQL.get_preference('tts_auto_mode', '')
        selected_index = 0
        string_list = Gtk.StringList()
        for i, (name, value) in enumerate(TTS_AUTO_MODES.items()):
            if value == selected_tts_mode:
                selected_index = i
            string_list.append(name)

        self.tts_auto_mode_combo.set_model(string_list)
        self.tts_auto_mode_combo.set_selected(selected_index)
        self.tts_auto_mode_combo.set_sensitive(True)

        Widgets.instance_manager.update_instance_list()

        # Ollama is available but there are no instances added
        if not any(i.get("type") == "ollama:managed" for i in SQL.get_instances()) and shutil.which("ollama"):
            SQL.insert_or_update_instance(instance_manager.OllamaManaged({
                "id": generate_uuid(),
                "name": "Alpaca",
                "url": "http://{}:11435".format("127.0.0.1" if sys.platform == "win32" else "0.0.0.0"),
                "pinned": True
            }))

        if self.get_application().args.ask or self.get_application().args.quick_ask:
            self.prepare_quick_chat()
            self.quick_chat(self.get_application().args.ask, 0)

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
            for chat in SQL.import_chat(os.path.join(cache_dir, 'import.db'), [tab.chat.get_name() for tab in list(self)]):
                self.add_chat(
                    chat_name=chat[1],
                    chat_id=chat[0],
                    chat_type='chat', #TODO notebook
                    mode=1
                )
            Widgets.dialog.show_toast(_("Chat imported successfully"), self)

    def request_screenshot(self):
        bus = SessionBus()
        portal = bus.get("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
        subscription = None

        def on_response(sender, obj, iface, signal, *params):
            response = params[0]
            if response[0] == 0:
                uri = response[1].get("uri")
                self.on_attachment(Gio.File.new_for_uri(uri))
            else:
                logger.error(f"Screenshot request failed with response: {response}\n{sender}\n{obj}\n{iface}\n{signal}")
                Widgets.dialog.show_toast(_("Attachment failed, screenshot might be too big"), self)
            if subscription:
                subscription.disconnect()

        subscription = bus.subscribe(
            iface="org.freedesktop.portal.Request",
            signal="Response",
            signal_fired=on_response
        )

        portal.Screenshot("", {"interactive": Variant('b', True)})

    def on_attachment(self, file:Gio.File):
        file_types = {
            "plain_text": ["txt", "md"],
            "code": ["c", "h", "css", "html", "js", "ts", "py", "java", "json", "xml", "asm", "nasm",
                    "cs", "csx", "cpp", "cxx", "cp", "hxx", "inc", "csv", "lsp", "lisp", "el", "emacs",
                    "l", "cu", "dockerfile", "glsl", "g", "lua", "php", "rb", "ru", "rs", "sql", "sh", "p8",
                    "yaml"],
            "image": ["png", "jpeg", "jpg", "webp", "gif"],
            "pdf": ["pdf"],
            "odt": ["odt"],
            "docx": ["docx"],
            "pptx": ["pptx"],
            "xlsx": ["xlsx"]
        }
        if file.query_info("standard::content-type", 0, None).get_content_type() == 'text/plain':
            extension = 'txt'
        else:
            extension = file.get_path().split(".")[-1]
        found_types = [key for key, value in file_types.items() if extension in value]
        if len(found_types) == 0:
            file_type = 'plain_text'
        else:
            file_type = found_types[0]
        if file_type == 'image':
            content = Widgets.attachments.extract_image(file.get_path(), 256)
        else:
            content = Widgets.attachments.extract_content(file_type, file.get_path())
        attachment = Widgets.attachments.Attachment(
            file_id="-1",
            file_name=os.path.basename(file.get_path()),
            file_type=file_type,
            file_content=content
        )
        self.global_attachment_container.add_attachment(attachment)

    def attachment_request(self):
        ff = Gtk.FileFilter()
        ff.set_name(_('Any compatible Alpaca attachment'))
        file_filters = [ff]
        mimes = (
            'text/plain',
            'application/pdf',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        for mime in mimes:
            ff = Gtk.FileFilter()
            ff.add_mime_type(mime)
            file_filters[0].add_mime_type(mime)
            file_filters.append(ff)
        if Widgets.model_manager.get_selected_model().get_vision():
            file_filters[0].add_pixbuf_formats()
            file_filter = Gtk.FileFilter()
            file_filter.add_pixbuf_formats()
            file_filters.append(file_filter)
        Widgets.dialog.simple_file(
            parent = self,
            file_filters = file_filters,
            callback = self.on_attachment
        )

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        Widgets.message.window = self
        Widgets.chat.window = self
        Widgets.model_manager.window = self
        Widgets.instance_manager.window = self

        self.prepare_quick_chat()
        self.model_searchbar.connect_entry(self.searchentry_models)
        self.model_searchbar.connect('notify::search-mode-enabled', lambda *_: self.model_search_changed(self.searchentry_models))

        # Prepare model selector
        list(self.model_dropdown)[0].add_css_class('flat')
        self.model_dropdown.set_model(Gio.ListStore.new(Widgets.model_manager.LocalModelRow))
        self.model_dropdown.set_expression(Gtk.PropertyExpression.new(Widgets.model_manager.LocalModelRow, None, "name"))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.model_dropdown.set_factory(factory)
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)
        list(list(self.title_no_model_button.get_child())[0])[1].set_ellipsize(3)

        if sys.platform not in ('win32', 'darwin'):
            self.model_manager_stack.set_enable_transitions(True)

            # Logic to remember the window size upon application shutdown and
            # startup; will restore the state of the app after closing and
            # opening it again, especially useful for large, HiDPI displays.
            self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca.State")

            # Please also see the GNOME developer documentation:
            # https://developer.gnome.org/documentation/tutorials/save-state.html
            for el in [
                ("width", "default-width"),
                ("height", "default-height"),
                ("is-maximized", "maximized")
            ]:
                self.settings.bind(
                    el[0],
                    self,
                    el[1],
                    Gio.SettingsBindFlags.DEFAULT
                )

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.on_file_drop)
        self.message_text_view = GtkSource.View(
            css_classes=['message_text_view'],
            top_margin=10,
            bottom_margin=10,
            hexpand=True,
            wrap_mode=3,
            valign=3,
            name="main_text_view"
        )

        self.message_text_view_scrolled_window.set_child(self.message_text_view)
        self.message_text_view.add_controller(drop_target)
        self.message_text_view.get_buffer().set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('adwaita'))
        self.message_text_view.connect('paste-clipboard', self.on_clipboard_paste)

        self.quick_ask_message_text_view = GtkSource.View(
            css_classes=['message_text_view'],
            top_margin=10,
            bottom_margin=10,
            hexpand=True,
            wrap_mode=3,
            valign=3,
            name="quick_chat_text_view"
        )
        self.quick_ask_text_view_scrolled_window.set_child(self.quick_ask_message_text_view)
        self.quick_ask_message_text_view.get_buffer().set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('adwaita'))

        def enter_key_handler(controller, keyval, keycode, state, text_view):
            if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK): # Enter pressed without shift
                mode = 0
                if state & Gdk.ModifierType.CONTROL_MASK: # Ctrl, send system message
                    mode = 1
                elif state & Gdk.ModifierType.ALT_MASK: # Alt, send tool message
                    mode = 2
                if text_view.get_name() == 'main_text_view':
                    self.send_message(None, mode)
                elif text_view.get_name() == 'quick_chat_text_view':
                    buffer = text_view.get_buffer()
                    self.quick_chat(buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False), mode)
                return True

        for text_view in (self.message_text_view, self.quick_ask_message_text_view):
            enter_key_controller = Gtk.EventControllerKey.new()
            enter_key_controller.connect("key-pressed", lambda c, kv, kc, stt, tv=text_view: enter_key_handler(c, kv, kc, stt, tv))
            text_view.add_controller(enter_key_controller)

        for name, data in {
            'send': {
                'button': self.action_button_stack.get_child_by_name('send'),
                'menu': self.send_message_menu
            },
            'attachment': {
                'button': self.attachment_button,
                'menu': self.attachment_menu
            }
        }.items():
            if name == 'attachment' and sys.platform not in ('win32', 'darwin'):
                data['menu'].append(_('Attach Screenshot'), 'app.attach_screenshot')
            gesture_click = Gtk.GestureClick(button=3)
            gesture_click.connect("released", lambda gesture, _n_press, x, y, menu=data.get('menu'): self.open_button_menu(gesture, x, y, menu))
            data.get('button').add_controller(gesture_click)
            gesture_long_press = Gtk.GestureLongPress()
            gesture_long_press.connect("pressed", lambda gesture, x, y, menu=data.get('menu'): self.open_button_menu(gesture, x, y, menu))
            data.get('button').add_controller(gesture_long_press)

        universal_actions = {
            'new_chat': [lambda *_: self.new_chat(chat_type='chat'), ['<primary>n']],
            'new_notebook': [lambda *_: self.new_chat(chat_type='notebook') if os.getenv("ALPACA_NOTEBOOK", "0") == "1" else None, ['<primary><shift>n']],
            'import_chat': [lambda *_: Widgets.dialog.simple_file(
                parent=self,
                file_filters=[self.file_filter_db],
                callback=self.on_chat_imported
            )],
            'duplicate_chat': [self.chat_actions],
            'duplicate_current_chat': [self.current_chat_actions],
            'delete_chat': [self.chat_actions],
            'delete_current_chat': [self.current_chat_actions, ['<primary>w']],
            'rename_chat': [self.chat_actions],
            'rename_current_chat': [self.current_chat_actions, ['F2']],
            'export_chat': [self.chat_actions],
            'export_current_chat': [self.current_chat_actions],
            'toggle_sidebar': [lambda *_: self.split_view_overlay.set_show_sidebar(not self.split_view_overlay.get_show_sidebar()), ['F9']],
            'toggle_search': [lambda *_: self.toggle_searchbar(), ['<primary>f']],
            'send_message': [lambda *_: self.send_message(None, 0)],
            'send_system_message': [lambda *_: self.send_message(None, 1)],
            'attach_file': [lambda *_: self.attachment_request()],
            'attach_screenshot': [lambda *i: self.request_screenshot() if Widgets.model_manager.get_selected_model().get_vision() else Widgets.dialog.show_toast(_("Image recognition is only available on specific models"), self)],
            'attach_url': [lambda *i: Widgets.dialog.simple_entry(
                parent=self,
                heading=_('Attach Website? (Experimental)'),
                body=_('Please enter a website URL'),
                callback=self.cb_text_received,
                entries={'placeholder': 'https://jeffser.com/alpaca/'}
            )],
            'attach_youtube': [lambda *i: Widgets.dialog.simple_entry(
                parent=self,
                heading=_('Attach YouTube Captions?'),
                body=_('Please enter a YouTube video URL'),
                callback=self.cb_text_received,
                entries={'placeholder': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}
            )],
            'model_manager' : [lambda *i: GLib.idle_add(self.main_navigation_view.push_by_tag, 'model_manager') if self.main_navigation_view.get_visible_page().get_tag() != 'model_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>m']],
            'instance_manager' : [lambda *i: self.show_instance_manager() if self.main_navigation_view.get_visible_page().get_tag() != 'instance_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>i']],
            'download_model_from_name' : [lambda *i: Widgets.dialog.simple_entry(
                parent=self,
                heading=_('Download Model?'),
                body=_('Please enter the model name following this template: name:tag'),
                callback=lambda name: threading.Thread(target=Widgets.model_manager.pull_model_confirm, args=(name,)).start(),
                entries={'placeholder': 'deepseek-r1:7b'}
            )],
            'reload_added_models': [lambda *_: Widgets.model_manager.update_local_model_list()],
            'delete_all_chats': [lambda *i: self.get_visible_dialog().close() and Widgets.dialog.simple(
                parent=self,
                heading=_('Delete All Chats?'),
                body=_('Are you sure you want to delete all chats?'),
                callback=lambda: [GLib.idle_add(c.chat.delete) for c in list(self.chat_list_box)],
                button_name=_('Delete'),
                button_appearance='destructive'
            )],
            'use_tools': [lambda *_: self.send_message(None, 2)],
            'tool_manager': [lambda *i: GLib.idle_add(self.main_navigation_view.push_by_tag, 'tool_manager') if self.main_navigation_view.get_visible_page().get_tag() != 'tool_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>t']],
            'start_quick_ask': [lambda *_: self.quick_ask.present(), ['<primary><alt>a']]
        }
        for action_name, data in universal_actions.items():
            self.get_application().create_action(action_name, data[0], data[1] if len(data) > 1 else None)

        if sys.platform in ('win32', 'darwin'):
            self.get_application().lookup_action('attach_screenshot').set_enabled(False)

        self.model_creator_name.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))
        self.model_creator_tag.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))

        checker = Spelling.Checker.get_default()
        adapter = Spelling.TextBufferAdapter.new(self.message_text_view.get_buffer(), checker)
        self.message_text_view.set_extra_menu(adapter.get_menu_model())
        self.message_text_view.insert_action_group('spelling', adapter)
        adapter.set_enabled(True)
        self.set_focus(self.message_text_view)
            
        Gio.PowerProfileMonitor.dup_default().connect("notify::power-saver-enabled", lambda monitor, *_: self.banner.set_revealed(monitor.get_power_saver_enabled() and self.powersaver_warning_switch.get_active() and self.get_current_instance().instance_type == 'ollama:managed'))
        self.banner.connect('button-clicked', lambda *_: self.banner.set_revealed(False))

        if shutil.which('ollama'):
            text = _('Already Installed!')
            self.install_ollama_button.set_label(text)
            self.install_ollama_button.set_tooltip_text(text)
            self.install_ollama_button.set_sensitive(False)

        if SQL.get_preference('skip_welcome_page', False):
            self.prepare_alpaca()
        else:
            self.main_navigation_view.replace_with_tags(['welcome'])
