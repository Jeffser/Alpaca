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
import json, threading, os, re, base64, gettext, uuid, shutil, logging, time, requests, sqlite3, sys
import odf.opendocument as odfopen
import odf.table as odftable
from io import BytesIO
from PIL import Image
from pypdf import PdfReader
from datetime import datetime
from pydbus import SessionBus, Variant

import gi
gi.require_version('GtkSource', '5')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Spelling', '1')
from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, GdkPixbuf, Spelling, GObject

from . import generic_actions, sql_manager, instance_manager
from .custom_widgets import message_widget, chat_widget, terminal_widget, dialog_widget, model_manager_widget
from .internal import config_dir, data_dir, cache_dir, source_dir

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
    model_manager_sidebar = Gtk.Template.Child()
    model_manager_sidebar_bottom_bar : Gtk.ActionBar = None
    main_navigation_view = Gtk.Template.Child()
    local_model_flowbox = Gtk.Template.Child()
    available_model_flowbox = Gtk.Template.Child()
    split_view_overlay_model_manager = Gtk.Template.Child()
    split_view_overlay = Gtk.Template.Child()
    regenerate_button : Gtk.Button = None
    selected_chat_row : Gtk.ListBoxRow = None
    preferences_dialog = Gtk.Template.Child()
    file_preview_dialog = Gtk.Template.Child()
    file_preview_text = Gtk.Template.Child()
    file_preview_image = Gtk.Template.Child()
    welcome_carousel = Gtk.Template.Child()
    welcome_previous_button = Gtk.Template.Child()
    welcome_next_button = Gtk.Template.Child()
    main_overlay = Gtk.Template.Child()
    chat_stack = Gtk.Template.Child()
    message_text_view = None
    message_text_view_scrolled_window = Gtk.Template.Child()
    action_button_stack = Gtk.Template.Child()
    attachment_container = Gtk.Template.Child()
    attachment_box = Gtk.Template.Child()
    attachment_button = Gtk.Template.Child()
    chat_right_click_menu = Gtk.Template.Child()
    send_message_menu = Gtk.Template.Child()
    attachment_menu = Gtk.Template.Child()
    file_preview_open_button = Gtk.Template.Child()
    file_preview_remove_button = Gtk.Template.Child()
    model_searchbar = Gtk.Template.Child()
    model_search_button = Gtk.Template.Child()
    message_searchbar = Gtk.Template.Child()
    searchentry_messages = Gtk.Template.Child()
    title_stack = Gtk.Template.Child()

    file_filter_db = Gtk.Template.Child()
    file_filter_gguf = Gtk.Template.Child()
    file_filter_image = Gtk.FileFilter()
    file_filter_image.add_pixbuf_formats()

    chat_list_container = Gtk.Template.Child()
    chat_list_box = None
    model_manager = None

    background_switch = Gtk.Template.Child()
    powersaver_warning_switch = Gtk.Template.Child()

    banner = Gtk.Template.Child()

    terminal_scroller = Gtk.Template.Child()
    terminal_dialog = Gtk.Template.Child()
    terminal_dir_button = Gtk.Template.Child()

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

    instance_preferences_page = Gtk.Template.Child()
    instance_listbox = Gtk.Template.Child()
    available_models_stack_page = Gtk.Template.Child()
    model_creator_stack_page = Gtk.Template.Child()
    last_selected_instance_row = None

    sql_instance = sql_manager.instance(os.path.join(data_dir, "alpaca.db"))

    @Gtk.Template.Callback()
    def zoom_changed(self, spinner, force:bool=False):
        if force or self.sql_instance.get_preference('zoom', 100) != int(spinner.get_value()):
            threading.Thread(target=self.sql_instance.insert_or_update_preferences, args=({'zoom': int(spinner.get_value())},)).start()
            settings = Gtk.Settings.get_default()
            settings.reset_property('gtk-xft-dpi')
            settings.set_property('gtk-xft-dpi',  settings.get_property('gtk-xft-dpi') + (int(spinner.get_value()) - 100) * 400)

    @Gtk.Template.Callback()
    def add_instance(self, button):
        def selected(ins:str):
            tbv=Adw.ToolbarView()
            tbv.add_top_bar(Adw.HeaderBar())
            tbv.set_content(ins.get_preferences_page(ins))
            self.main_navigation_view.push(Adw.NavigationPage(title=_('Add Instance'), tag='instance', child=tbv))

        options = {}
        for ins_type in instance_manager.ready_instances:
            options[ins_type.instance_type_display] = ins_type

        dialog_widget.simple_dropdown(
            _("Add Instance"),
            _("Select a type of instance to add"),
            lambda option, options=options: selected(options[option]),
            options.keys()
        )

    @Gtk.Template.Callback()
    def instance_changed(self, listbox, row):
        def change_instance():
            if self.last_selected_instance_row:
                self.last_selected_instance_row.instance.stop()
            self.last_selected_instance_row = row

            self.available_models_stack_page.set_visible(len(model_manager_widget.available_models) > 0)
            self.model_creator_stack_page.set_visible(len(model_manager_widget.available_models) > 0)
            self.sql_instance.insert_or_update_preferences({'selected_instance': row.instance.instance_id})
        if listbox.get_sensitive() and row:
            model_manager_widget.update_local_model_list()
            model_manager_widget.update_available_model_list()
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
                self.sql_instance.insert_or_update_model_picture(model_name, self.get_content_of_file(profile_picture, 'profile_picture'))

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
                model_manager_widget.create_model(data_json, gguf_path)
            else:
                data_json['from'] = self.convert_model_name(self.model_creator_base.get_selected_item().get_string(), 1)
                model_manager_widget.create_model(data_json)

    @Gtk.Template.Callback()
    def model_creator_cancel(self, button):
        self.model_creator_stack.set_visible_child_name('introduction')

    @Gtk.Template.Callback()
    def model_creator_load_profile_picture(self, button):
        dialog_widget.simple_file([self.file_filter_image], lambda file: self.model_creator_profile_picture.set_subtitle(file.get_path()))

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

        dialog_widget.simple_file([self.file_filter_gguf], result)

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
            [GLib.idle_add(string_list.append, value.model_title) for value in model_manager_widget.get_local_models().values()]
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
                if self.model_manager_sidebar_bottom_bar and self.model_manager_sidebar_bottom_bar.get_parent():
                    GLib.idle_add(self.model_manager_sidebar.remove, self.model_manager_sidebar_bottom_bar)
                GLib.idle_add(self.model_manager_sidebar.get_content().set_child, Adw.StatusPage(icon_name='brain-augemnted-symbolic'))

        selected_children = flowbox.get_selected_children()
        if len(selected_children) > 0:
            if not self.split_view_overlay_model_manager.get_show_sidebar():
                self.split_view_overlay_model_manager.set_show_sidebar(True)
            model = selected_children[0].get_child()

            actionbar, content = model.get_page()

            if self.model_manager_sidebar_bottom_bar and self.model_manager_sidebar_bottom_bar.get_parent():
                self.model_manager_sidebar.remove(self.model_manager_sidebar_bottom_bar)
            self.model_manager_sidebar_bottom_bar = actionbar
            self.model_manager_sidebar.add_bottom_bar(self.model_manager_sidebar_bottom_bar)
            self.model_manager_sidebar.get_content().set_child(content)

        else:
            self.split_view_overlay_model_manager.set_show_sidebar(False)
            threading.Thread(target=set_default_sidebar).start()


    @Gtk.Template.Callback()
    def closing_terminal(self, dialog):
        dialog.get_child().get_content().get_child().feed_child(b"\x03")
        dialog.force_close()

    @Gtk.Template.Callback()
    def stop_message(self, button=None):
        self.chat_list_box.get_current_chat().stop_message()

    @Gtk.Template.Callback()
    def send_message(self, button=None, system:bool=False):
        if button and not button.get_visible():
            return
        if not self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False):
            return
        current_chat = self.chat_list_box.get_current_chat()
        if current_chat.busy == True:
            return

        self.chat_list_box.send_tab_to_top(self.chat_list_box.get_selected_row())

        current_model = model_manager_widget.get_selected_model().get_name()
        if current_model is None:
            self.show_toast(_("Please select a model before chatting"), self.main_overlay)
            return

        message_id = self.generate_uuid()

        raw_message = self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        m_element = current_chat.add_message(message_id, datetime.now(), None, system)

        for name, content in self.attachments.items():
            attachment = m_element.add_attachment(name, content['type'], content['content'])
            self.sql_instance.add_attachment(m_element, attachment)
            content["button"].get_parent().remove(content["button"])
        self.attachments = {}
        self.attachment_box.set_visible(False)

        m_element.set_text(raw_message)

        self.sql_instance.insert_or_update_message(m_element)

        self.message_text_view.get_buffer().set_text("", 0)

        if system:
            current_chat.set_visible_child_name('content')
        else:
            bot_id=self.generate_uuid()
            m_element_bot = current_chat.add_message(bot_id, datetime.now(), current_model, False)
            m_element_bot.set_text()
            m_element_bot.footer.options_button.set_sensitive(False)
            self.sql_instance.insert_or_update_message(m_element_bot)
            threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model)).start()

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
            self.sql_instance.insert_or_update_preferences({'skip_welcome_page': True})
            self.main_navigation_view.replace_with_tags(['loading'])
            threading.Thread(target=self.prepare_alpaca).start()

    @Gtk.Template.Callback()
    def switch_run_on_background(self, switch, user_data):
        logger.debug("Switching run on background")
        self.set_hide_on_close(switch.get_active())
        self.sql_instance.insert_or_update_preferences({'run_on_background': switch.get_active()})
    
    @Gtk.Template.Callback()
    def switch_powersaver_warning(self, switch, user_data):
        logger.debug("Switching powersaver warning banner")
        if switch.get_active():
            self.banner.set_revealed(Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled())
        else:
            self.banner.set_revealed(False)
        self.sql_instance.insert_or_update_preferences({'powersaver_warning': switch.get_active()})

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        def close():
            selected_chat = self.chat_list_box.get_selected_row().chat_window.get_name()
            self.sql_instance.insert_or_update_preferences({'selected_chat': selected_chat})
            self.get_current_instance().stop()
            self.get_application().quit()

        def switch_to_hide():
            self.set_hide_on_close(True)
            self.close() #Recalls this function

        if self.get_hide_on_close():
            logger.info("Hiding app...")
        else:
            logger.info("Closing app...")
            if any([chat.chat_window.busy for chat in self.chat_list_box.tab_list]) or any([el for el in list(self.local_model_flowbox) if isinstance(el.get_child(), model_manager_widget.pulling_model)]):
                options = {
                    _('Cancel'): {'default': True},
                    _('Hide'): {'callback': switch_to_hide},
                    _('Close'): {'callback': close, 'appearance': 'destructive'},
                }
                dialog_widget.Options(
                    _('Close Alpaca?'),
                    _('A task is currently in progress. Are you sure you want to close Alpaca?'),
                    list(options.keys())[0],
                    options,
                )
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
    def model_search_changed(self, entry):
        results_local = False
        if len(model_manager_widget.get_local_models()) > 0:
            for model in list(self.local_model_flowbox):
                model.set_visible(re.search(entry.get_text(), model.get_child().get_search_string(), re.IGNORECASE))
                results_local = results_local or model.get_visible()
                if not model.get_visible() and model in self.local_model_flowbox.get_selected_children():
                    self.local_model_flowbox.unselect_all()
            self.local_model_stack.set_visible_child_name('content' if results_local else 'no-results')
        else:
            self.local_model_stack.set_visible_child_name('no-models')

        results_available = False
        if len(model_manager_widget.available_models) > 0:
            self.available_models_stack_page.set_visible(True)
            self.model_creator_stack_page.set_visible(True)
            for model in list(self.available_model_flowbox):
                model.set_visible(re.search(entry.get_text(), model.get_child().get_search_string(), re.IGNORECASE))
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
        results = 0
        if not current_chat:
            current_chat = self.chat_list_box.get_current_chat()
        if current_chat:
            try:
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
            except Exception as e:
                pass

    def convert_model_name(self, name:str, mode:int): # mode=0 name:tag -> Name (tag)   |   mode=1 Name (tag) -> name:tag   |   mode=2 name:tag -> name, tag
        try:
            if mode == 0:
                if ':' in name:
                    name = name.split(':')
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
        chat_name = self.generate_numbered_name(chat.get_name(), [tab.chat_window.get_name() for tab in self.chat_list_box.tab_list])
        new_chat = self.chat_list_box.new_chat(chat_name)
        for message in chat.messages.values():
            self.sql_instance.insert_or_update_message(message, new_chat.chat_id)
        threading.Thread(target=new_chat.load_chat_messages).start()
        self.present()

    @Gtk.Template.Callback()
    def closing_quick_ask(self, user_data):
        if not self.get_visible():
            self.close()

    def on_clipboard_paste(self, textview):
        logger.debug("Pasting from clipboard")
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, lambda clipboard, result: self.cb_text_received(clipboard.read_text_finish(result)))
        clipboard.read_texture_async(None, self.cb_image_received)

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        if length == 1:
            new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
            if new_text != text:
                editable.stop_emission_by_name("insert-text")

    def show_toast(self, message:str, overlay):
        logger.info(message)
        toast = Adw.Toast(
            title=message,
            timeout=2
        )
        overlay.add_toast(toast)

    def show_notification(self, title:str, body:str, icon:Gio.ThemedIcon=None):
        if not self.is_active() and not self.quick_ask.is_active():
            body = body.replace('<span>', '').replace('</span>', '')
            logger.info(f"{title}, {body}")
            notification = Gio.Notification.new(title)
            notification.set_body(body)
            if icon:
                notification.set_icon(icon)
            self.get_application().send_notification(None, notification)

    def preview_file(self, file_name:str, file_content:str, file_type:str, show_remove:bool):
        logger.info(f"Previewing file: {file_name}")
        if show_remove:
            self.file_preview_remove_button.set_visible(True)
            self.file_preview_remove_button.set_name(file_name)
        else:
            self.file_preview_remove_button.set_visible(False)
        if file_content:
            if file_type == 'image':
                self.file_preview_image.set_visible(True)
                self.file_preview_text.set_visible(False)
                image_data = base64.b64decode(file_content)
                loader = GdkPixbuf.PixbufLoader.new()
                loader.write(image_data)
                loader.close()
                pixbuf = loader.get_pixbuf()
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self.file_preview_image.set_from_paintable(texture)
                self.file_preview_image.set_size_request(360, 360)
                self.file_preview_image.set_overflow(1)
                self.file_preview_dialog.set_title(file_name)
                self.file_preview_open_button.set_visible(False)
            else:
                self.file_preview_image.set_visible(False)
                buffer = self.file_preview_text.get_buffer()
                buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
                buffer.insert(buffer.get_end_iter(), file_content, len(file_content.encode('utf-8')))
                self.file_preview_text.set_visible(True)
                if file_type == 'youtube':
                    self.file_preview_dialog.set_title(file_content.split('\n')[0])
                    self.file_preview_open_button.set_name(file_content.split('\n')[2])
                elif file_type == 'website':
                    self.file_preview_open_button.set_name(file_content.split('\n')[0])
                else:
                    self.file_preview_dialog.set_title(file_name)
                    self.file_preview_open_button.set_visible(False)
            self.file_preview_dialog.present(self)

    def switch_send_stop_button(self, send:bool):
        self.action_button_stack.set_visible_child_name('send' if send else 'stop')

    def load_history(self):
        logger.debug("Loading history")
        selected_chat = self.sql_instance.get_preference('selected_chat')
        chats = self.sql_instance.get_chats()
        if len(chats) > 0:
            threads = []
            if selected_chat not in [row[1] for row in chats]:
                selected_chat = chats[0][1]
            for row in chats:
                chat_container =self.chat_list_box.append_chat(row[1], row[0])
                if row[1] == selected_chat:
                    self.chat_list_box.select_row(self.chat_list_box.tab_list[-1])
                threads.append(threading.Thread(target=chat_container.load_chat_messages))
                threads[-1].start()
            for thread in threads:
                thread.join()
        else:
            self.chat_list_box.new_chat()

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

    def get_content_of_file(self, file_path, file_type):
        if not os.path.exists(file_path): return None
        if file_type == 'image':
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    max_size = 640
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
        elif file_type == 'profile_picture':
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    max_size = 128
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
        elif file_type in ('plain_text', 'code', 'youtube', 'website'):
            with open(file_path, 'r', encoding="utf-8") as f:
                return f.read()
        elif file_type == 'pdf':
            reader = PdfReader(file_path)
            if len(reader.pages) == 0:
                return None
            text = ""
            for i, page in enumerate(reader.pages):
                text += f"\n- Page {i+1}\n{page.extract_text(extraction_mode='layout', layout_mode_space_vertically=False)}\n"
            return text
        elif file_type == 'odt':
            doc = odfopen.load(file_path)
            markdown_elements = []
            for child in doc.text.childNodes:
                if child.qname[1] == 'p' or child.qname[1] == 'span':
                    markdown_elements.append(str(child))
                elif child.qname[1] == 'h':
                    markdown_elements.append('# {}'.format(str(child)))
                elif child.qname[1] == 'table':
                    generated_table = []
                    column_sizes = []
                    for row in child.getElementsByType(odftable.TableRow):
                        generated_table.append([])
                        for column_n, cell in enumerate(row.getElementsByType(odftable.TableCell)):
                            if column_n + 1 > len(column_sizes):
                                column_sizes.append(0)
                            if len(str(cell)) > column_sizes[column_n]:
                                column_sizes[column_n] = len(str(cell))
                            generated_table[-1].append(str(cell))
                    generated_table.insert(1, [])
                    for column_n in range(len(generated_table[0])):
                        generated_table[1].append('-' * column_sizes[column_n])
                    table_str = ''
                    for row in generated_table:
                        for column_n, cell in enumerate(row):
                            table_str += '| {} '.format(cell.ljust(column_sizes[column_n], ' '))
                        table_str += '|\n'
                    markdown_elements.append(table_str)
            return '\n\n'.join(markdown_elements)

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
                    "code": "code-symbolic",
                    "pdf": "document-text-symbolic",
                    "odt": "document-text-symbolic",
                    "youtube": "play-symbolic",
                    "website": "globe-symbolic"
                }[file_type]
            )
            button = Gtk.Button(
                vexpand=True,
                valign=0,
                name=file_name,
                css_classes=["flat"],
                tooltip_text=file_name,
                child=button_content
            )
            self.attachments[file_name] = {"path": file_path, "type": file_type, "content": content, "button": button}
            button.connect("clicked", lambda button : self.preview_file(file_name, content, file_type, True))
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
                {'placeholder': _('Chat name'), 'default': True, 'text': chat_name},
                _('Rename')
            )
        elif action_name in ('export_chat', 'export_current_chat'):
            chat = self.chat_list_box.get_chat_by_name(chat_name)
            options = {
                _("Importable (.db)"): chat.export_db,
                _("Markdown"): lambda chat=chat: chat.export_md(False),
                _("Markdown (Obsidian Style)"): lambda chat=chat: chat.export_md(True),
                _("JSON"): lambda chat=chat: chat.export_json(False),
                _("JSON (Include Metadata)"): lambda chat=chat: chat.export_json(True)
            }
            dialog_widget.simple_dropdown(
                _("Export Chat"),
                _("Select a method to export the chat"),
                lambda option, options=options: options[option](),
                options.keys()
            )

    def current_chat_actions(self, action, user_data):
        self.selected_chat_row = self.chat_list_box.get_selected_row()
        self.chat_actions(action, user_data)

    def youtube_detected(self, video_url):
        try:
            response = requests.get('https://noembed.com/embed?url={}'.format(video_url))
            data = json.loads(response.text)

            transcriptions = generic_actions.get_youtube_transcripts(data['url'].split('=')[1])
            if len(transcriptions) == 0:
                GLib.idle_add(self.show_toast, _("This video does not have any transcriptions"), self.main_overlay)
                return

            if not any(filter(lambda x: '(en' in x and 'auto-generated' not in x and len(transcriptions) > 1, transcriptions)):
                transcriptions.insert(1, 'English (translate:en)')

            GLib.idle_add(dialog_widget.simple_dropdown,
                _('Attach YouTube Video?'),
                _('{}\n\nPlease select a transcript to include').format(data['title']),
                lambda caption_name, data=data, video_url=video_url: threading.Thread(target=generic_actions.attach_youtube, args=(data['title'], data['author_name'], data['url'], video_url, data['url'].split('=')[1], caption_name)).start(),
                transcriptions
            )
        except Exception as e:
            logger.error(e)
            GLib.idle_add(self.show_toast, _("Error attaching video, please try again"), self.main_overlay)
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
                dialog_widget.simple(
                    _('Attach Website? (Experimental)'),
                    _("Are you sure you want to attach\n'{}'?").format(text),
                    lambda url=text: threading.Thread(target=generic_actions.attach_website, args=(url,)).start()
                )
        except Exception as e:
            logger.error(e)

    def cb_image_received(self, clipboard, result):
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                if model_manager_widget.get_selected_model().get_vision():
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

    def on_file_drop(self, drop_target, value, x, y):
        files = value.get_files()
        for file in files:
            extension = os.path.splitext(file.get_path())[1][1:]
            if extension in ('png', 'jpeg', 'jpg', 'webp', 'gif'):
                if model_manager_widget.get_selected_model().get_vision():
                    self.attach_file(file.get_path(), 'image')
                else:
                    self.show_toast(_("Image recognition is only available on specific models"), self.main_overlay)
            elif extension in ('txt', 'md'):
                self.attach_file(file.get_path(), 'plain_text')
            elif extension in ("c", "h", "css", "html", "js", "ts", "py", "java", "json", "xml",
                                "asm", "nasm", "cs", "csx", "cpp", "cxx", "cp", "hxx", "inc", "csv",
                                "lsp", "lisp", "el", "emacs", "l", "cu", "dockerfile", "glsl", "g",
                                "lua", "php", "rb", "ru", "rs", "sql", "sh", "p8"):
                self.attach_file(file.get_path(), 'code')
            elif extension == 'pdf':
                self.attach_file(file.get_path(), 'pdf')

    def quick_chat(self, message:str):
        self.quick_ask_save_button.set_sensitive(False)
        self.quick_ask.present()
        default_model = self.get_current_instance().get_default_model()
        if default_model:
            current_model = self.convert_model_name(default_model, 1)
        if current_model is None:
            self.show_toast(_("Please select a model before chatting"), self.quick_ask_overlay)
            return
        chat = chat_widget.chat(_('Quick Ask'), 'QA', True)
        self.quick_ask_overlay.set_child(chat)
        m_element = chat.add_message(self.generate_uuid(), datetime.now(), None, False)
        m_element.set_text(message)
        m_element_bot = chat.add_message(self.generate_uuid(), datetime.now(), current_model, False)
        m_element_bot.set_text()
        chat.busy = True
        threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model)).start()

    def get_current_instance(self):
        if self.instance_listbox.get_selected_row():
            return self.instance_listbox.get_selected_row().instance
        else:
            return instance_manager.empty()

    def prepare_alpaca(self):
        instance_manager.update_instance_list()

        #Chat History
        self.load_history()
        self.chat_list_box.chat_changed(self.chat_list_box.get_selected_row(), True)

        if self.get_application().args.new_chat:
            self.chat_list_box.new_chat(self.get_application().args.new_chat)

        self.powersaver_warning_switch.set_active(self.sql_instance.get_preference('powersaver_warning', True))
        self.background_switch.set_active(self.sql_instance.get_preference('run_on_background', False))
        self.zoom_spin.set_value(self.sql_instance.get_preference('zoom', 100))
        self.zoom_changed(self.zoom_spin, True)

        GLib.idle_add(self.main_navigation_view.replace_with_tags, ['chat'])
        if self.get_application().args.ask:
            self.quick_chat(self.get_application().args.ask)

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

    def initial_convert_to_sql(self):
        if os.path.exists(os.path.join(data_dir, "chats", "chats.json")):
            try:
                with open(os.path.join(data_dir, "chats", "chats.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sqlite_con = sqlite3.connect(os.path.join(data_dir, "alpaca.db"))
                    cursor = sqlite_con.cursor()
                    for chat_name in data['chats'].keys():
                        chat_id = self.generate_uuid()
                        cursor.execute("INSERT INTO chat (id, name) VALUES (?, ?);", (chat_id, chat_name))

                        for message_id, message in data['chats'][chat_name]['messages'].items():
                            cursor.execute("INSERT INTO message (id, chat_id, role, model, date_time, content) VALUES (?, ?, ?, ?, ?, ?)",
                            (message_id, chat_id, message['role'], message['model'], message['date'], message['content']))

                            if 'files' in message:
                                for file_name, file_type in message['files'].items():
                                    attachment_id = self.generate_uuid()
                                    content = self.get_content_of_file(os.path.join(data_dir, "chats", chat_name, message_id, file_name), file_type)
                                    cursor.execute("INSERT INTO attachment (id, message_id, type, name, content) VALUES (?, ?, ?, ?, ?)",
                                    (attachment_id, message_id, file_type, file_name, content))
                            if 'images' in message:
                                for image in message['images']:
                                    attachment_id = self.generate_uuid()
                                    content = self.get_content_of_file(os.path.join(data_dir, "chats", chat_name, message_id, image), 'image')
                                    cursor.execute("INSERT INTO attachment (id, message_id, type, name, content) VALUES (?, ?, ?, ?, ?)",
                                    (attachment_id, message_id, 'image', image, content))

                    sqlite_con.commit()
                    sqlite_con.close()
                shutil.move(os.path.join(data_dir, "chats"), os.path.join(data_dir, "chats_OLD"))
            except Exception as e:
                logger.error(e)
                pass

        if os.path.exists(os.path.join(data_dir, "chats")):
            shutil.rmtree(os.path.join(data_dir, "chats"))

        if os.path.exists(os.path.join(config_dir, "server.json")):
            try:
                with open(os.path.join(config_dir, "server.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sqlite_con = sqlite3.connect(os.path.join(data_dir, "alpaca.db"))
                    cursor = sqlite_con.cursor()
                    if 'model_tweaks' in data:
                        for name, value in data['model_tweaks'].items():
                            data[name] = value
                        del data['model_tweaks']
                    for name, value in data.items():
                        if cursor.execute("SELECT * FROM preferences WHERE id=?", (name,)).fetchone():
                            cursor.execute("UPDATE preferences SET value=?, type=? WHERE id=?", (value, str(type(value)), name))
                        else:
                            cursor.execute("INSERT INTO preferences (id, value, type) VALUES (?, ?, ?)", (name, value, str(type(value))))
                    sqlite_con.commit()
                    sqlite_con.close()
                os.remove(os.path.join(config_dir, "server.json"))
            except Exception as e:
                logger.error(e)
                pass

    def request_screenshot(self):
        bus = SessionBus()
        portal = bus.get("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
        subscription = None

        def on_response(sender, obj, iface, signal, *params):
            response = params[0]
            if response[0] == 0:
                uri = response[1].get("uri")
                generic_actions.attach_file(Gio.File.new_for_uri(uri))
            else:
                logger.error(f"Screenshot request failed with response: {response}\n{sender}\n{obj}\n{iface}\n{signal}")
                self.show_toast(_("Attachment failed, screenshot might be too big"), self.main_overlay)
            if subscription:
                subscription.disconnect()

        subscription = bus.subscribe(
            iface="org.freedesktop.portal.Request",
            signal="Response",
            signal_fired=on_response
        )

        portal.Screenshot("", {"interactive": Variant('b', True)})

    def attachment_request(self):
        ff = Gtk.FileFilter()
        ff.set_name(_('Any compatible Alpaca attachment'))
        file_filters = [ff]
        for mime in ['text/plain', 'application/pdf', 'application/vnd.oasis.opendocument.text']:
            ff = Gtk.FileFilter()
            ff.add_mime_type(mime)
            file_filters[0].add_mime_type(mime)
            file_filters.append(ff)
        if model_manager_widget.get_selected_model().get_vision():
            file_filters[0].add_pixbuf_formats()
            file_filters.append(self.file_filter_image)
        dialog_widget.simple_file(file_filters, generic_actions.attach_file)

    def show_instance_manager(self):
        self.instance_preferences_page.set_sensitive(not any([tab.chat_window.busy for tab in self.chat_list_box.tab_list]))
        GLib.idle_add(self.main_navigation_view.push_by_tag, 'instance_manager')

    def toggle_searchbar(self):
        # TODO Gnome 48: Replace with get_visible_page_tag()
        current_tag = self.main_navigation_view.get_visible_page().get_tag()

        searchbars = {
            'chat': self.message_searchbar,
            'model_manager': self.model_searchbar
        }

        if searchbars.get(current_tag):
            searchbars.get(current_tag).set_search_mode(not searchbars.get(current_tag).get_search_mode())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        GtkSource.init()
        self.initial_convert_to_sql()
        message_widget.window = self
        chat_widget.window = self
        dialog_widget.window = self
        terminal_widget.window = self
        generic_actions.window = self
        model_manager_widget.window = self
        instance_manager.window = self

        # Prepare model selector
        list(self.model_dropdown)[0].add_css_class('flat')
        self.model_dropdown.set_model(Gio.ListStore.new(model_manager_widget.local_model_row))
        self.model_dropdown.set_expression(Gtk.PropertyExpression.new(model_manager_widget.local_model_row, None, "name"))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=2, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.model_dropdown.set_factory(factory)
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.on_file_drop)
        self.message_text_view = GtkSource.View(
            css_classes=['message_text_view'], top_margin=10, bottom_margin=10, hexpand=True, wrap_mode=3
        )

        self.message_text_view_scrolled_window.set_child(self.message_text_view)
        self.message_text_view.add_controller(drop_target)
        self.message_text_view.get_buffer().set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('adwaita'))
        self.message_text_view.connect('paste-clipboard', self.on_clipboard_paste)

        self.chat_list_box = chat_widget.chat_list()
        self.chat_list_container.set_child(self.chat_list_box)
        enter_key_controller = Gtk.EventControllerKey.new()
        enter_key_controller.connect("key-pressed", lambda controller, keyval, keycode, state: (self.send_message(None, bool(state & Gdk.ModifierType.CONTROL_MASK)) or True) if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK) else None)
        self.message_text_view.add_controller(enter_key_controller)

        for button, menu in {self.action_button_stack.get_child_by_name('send'): self.send_message_menu, self.attachment_button: self.attachment_menu}.items():
            gesture_click = Gtk.GestureClick(button=3)
            gesture_click.connect("released", lambda gesture, n_press, x, y, menu=menu: self.open_button_menu(gesture, x, y, menu))
            button.add_controller(gesture_click)
            gesture_long_press = Gtk.GestureLongPress()
            gesture_long_press.connect("pressed", lambda gesture, x, y, menu=menu: self.open_button_menu(gesture, x, y, menu))
            button.add_controller(gesture_long_press)

        universal_actions = {
            'new_chat': [lambda *_: self.chat_list_box.new_chat(), ['<primary>n']],
            'clear': [lambda *i: dialog_widget.simple(_('Clear Chat?'), _('Are you sure you want to clear the chat?'), self.chat_list_box.get_current_chat().clear_chat, _('Clear')), ['<primary>e']],
            'import_chat': [lambda *_: self.chat_list_box.import_chat()],
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
            'send_message': [lambda *_: self.send_message()],
            'send_system_message': [lambda *_: self.send_message(None, True)],
            'attach_file': [lambda *_: self.attachment_request()],
            'attach_screenshot': [lambda *i: self.request_screenshot() if model_manager_widget.get_selected_model().get_vision() else self.show_toast(_("Image recognition is only available on specific models"), self.main_overlay)],
            'attach_url': [lambda *i: dialog_widget.simple_entry(_('Attach Website? (Experimental)'), _('Please enter a website URL'), self.cb_text_received, {'placeholder': 'https://jeffser.com/alpaca/'})],
            'attach_youtube': [lambda *i: dialog_widget.simple_entry(_('Attach YouTube Captions?'), _('Please enter a YouTube video URL'), self.cb_text_received, {'placeholder': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})],
            'model_manager' : [lambda *i: GLib.idle_add(self.main_navigation_view.push_by_tag, 'model_manager') if self.main_navigation_view.get_visible_page().get_tag() != 'model_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>m']],
            'instance_manager' : [lambda *i: self.show_instance_manager() if self.main_navigation_view.get_visible_page().get_tag() != 'instance_manager' else GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat'), ['<primary>i']],
            'download_model_from_name' : [lambda *i: dialog_widget.simple_entry(_('Download Model?'), _('Please enter the model name following this template: name:tag'), lambda name: threading.Thread(target=model_manager_widget.pull_model_confirm, args=(name,)).start(), {'placeholder': 'deepseek-r1:7b'})],
            'reload_added_models': [lambda *_: model_manager_widget.update_local_model_list()]
        }

        for action_name, data in universal_actions.items():
            self.get_application().create_action(action_name, data[0], data[1] if len(data) > 1 else None)

        if sys.platform == 'darwin':
            self.get_application().lookup_action('attach_screenshot').set_enabled(False)

        self.file_preview_remove_button.connect('clicked', lambda button : dialog_widget.simple(_('Remove Attachment?'), _("Are you sure you want to remove attachment?"), lambda button=button: self.remove_attached_file(button.get_name()), _('Remove'), 'destructive'))
        self.model_creator_name.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))
        self.model_creator_tag.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))

        checker = Spelling.Checker.get_default()
        adapter = Spelling.TextBufferAdapter.new(self.message_text_view.get_buffer(), checker)
        self.message_text_view.set_extra_menu(adapter.get_menu_model())
        self.message_text_view.insert_action_group('spelling', adapter)
        adapter.set_enabled(True)
        self.set_focus(self.message_text_view)

        if self.sql_instance.get_preference('skip_welcome_page', False):
            threading.Thread(target=self.prepare_alpaca).start()
        else:
            self.main_navigation_view.replace_with_tags(['welcome'])
            
        Gio.PowerProfileMonitor.dup_default().connect("notify::power-saver-enabled", lambda monitor, *_: self.banner.set_revealed(monitor.get_power_saver_enabled() and self.powersaver_warning_switch.get_active()))
        self.banner.connect('button-clicked', lambda *_: self.banner.set_revealed(False))
