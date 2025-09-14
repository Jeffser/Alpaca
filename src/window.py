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

import json, threading, os, re, gettext, shutil, logging, time, requests, sys, tempfile, importlib.util
import numpy as np

from datetime import datetime

from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, Spelling

from .sql_manager import generate_uuid, generate_numbered_name, prettify_model_name, Instance as SQL
from . import widgets as Widgets
from .constants import data_dir, source_dir, cache_dir

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/window.ui')
class AlpacaWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AlpacaWindow'

    localedir = os.path.join(source_dir, 'locale')

    gettext.bindtextdomain('com.jeffser.Alpaca', localedir)
    gettext.textdomain('com.jeffser.Alpaca')
    _ = gettext.gettext

    #Elements
    new_chat_splitbutton = Gtk.Template.Child()
    local_model_stack = Gtk.Template.Child()
    available_model_stack = Gtk.Template.Child()
    model_manager_stack = Gtk.Template.Child()
    instance_manager_stack = Gtk.Template.Child()
    main_navigation_view = Gtk.Template.Child()
    local_model_flowbox = Gtk.Template.Child()
    available_model_flowbox = Gtk.Template.Child()
    split_view_overlay = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()
    chat_bin = Gtk.Template.Child()
    chat_list_navigationview = Gtk.Template.Child()
    global_footer_container = Gtk.Template.Child()
    model_searchbar = Gtk.Template.Child()
    searchentry_models = Gtk.Template.Child()
    model_search_button = Gtk.Template.Child()
    message_searchbar = Gtk.Template.Child()
    searchentry_messages = Gtk.Template.Child()
    title_stack = Gtk.Template.Child()
    title_no_model_button = Gtk.Template.Child()
    model_filter_button = Gtk.Template.Child()

    file_filter_db = Gtk.Template.Child()

    banner = Gtk.Template.Child()

    model_dropdown = Gtk.Template.Child()

    instance_preferences_page = Gtk.Template.Child()
    instance_listbox = Gtk.Template.Child()
    available_models_stack_page = Gtk.Template.Child()
    tool_listbox = Gtk.Template.Child()
    model_manager_bottom_view_switcher = Gtk.Template.Child()
    model_manager_top_view_switcher = Gtk.Template.Child()
    last_selected_instance_row = None

    chat_splitview = Gtk.Template.Child()
    activities_page = Gtk.Template.Child()
    last_breakpoint_status = False

    chat_searchbar = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def chat_list_page_changed(self, navigationview, page=None):
        if self.chat_searchbar.get_search_mode():
            self.chat_searchbar.set_search_mode(False)
            previous_page = navigationview.get_previous_page(navigationview.get_visible_page())
            if previous_page:
                previous_page.on_search('')

    @Gtk.Template.Callback()
    def last_breakpoint_applied(self, bp):
        self.last_breakpoint_status = True

    @Gtk.Template.Callback()
    def last_breakpoint_unapplied(self, bp):
        if len(self.activities_page.get_child().tabview.get_pages()) > 0:
            GLib.idle_add(self.chat_splitview.set_collapsed, False)
        self.chat_splitview.set_show_content(True)
        self.last_breakpoint_status = False

    @Gtk.Template.Callback()
    def show_activities_button_pressed(self, button):
        self.chat_splitview.set_show_content(False)

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
        instance_list = Widgets.instances.ollama_instances.BaseInstance.__subclasses__()
        if os.getenv('ALPACA_OLLAMA_ONLY', '0') != '1':
            instance_list += Widgets.instances.openai_instances.BaseInstance.__subclasses__()
        for ins_type in instance_list:
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

            Widgets.models.update_added_model_list(self)
            Widgets.models.update_available_model_list(self)

            if row:
                self.settings.set_string('selected-instance', row.instance.instance_id)
                self.get_application().lookup_action('model_creator_existing').set_enabled('ollama' in row.instance.instance_type)
                self.get_application().lookup_action('model_creator_gguf').set_enabled('ollama' in row.instance.instance_type)

            self.chat_bin.get_child().row.update_profile_pictures()
            listbox.set_sensitive(True)
        if listbox.get_sensitive():
            listbox.set_sensitive(False)
            GLib.idle_add(threading.Thread(target=change_instance, daemon=True).start)

    @Gtk.Template.Callback()
    def model_manager_stack_changed(self, viewstack, params):
        self.local_model_flowbox.unselect_all()
        self.available_model_flowbox.unselect_all()
        self.model_search_button.set_sensitive(viewstack.get_visible_child_name() not in ('model_creator', 'instances'))
        self.model_search_button.set_active(self.model_search_button.get_active() and viewstack.get_visible_child_name() not in ('model_creator', 'instances'))

    @Gtk.Template.Callback()
    def closing_app(self, user_data):
        def close():
            try:
                self.settings.set_string('default-chat', self.chat_bin.get_child().chat_id)
            except Exception as e:
                logger.warning(f"Could not save default chat: {e}")
            
            try:
                current_instance = self.get_current_instance()
                if hasattr(current_instance, 'stop'):
                    current_instance.stop()
            except Exception as e:
                logger.warning(f"Error stopping current instance: {e}")
            
            try:
                if Widgets.voice.message_dictated:
                    Widgets.voice.message_dictated.popup.tts_button.set_active(False)
            except Exception as e:
                logger.warning(f"Error stopping voice: {e}")
            
            # Quit from the GLib main loop to avoid teardown races with worker threads
            GLib.idle_add(self.get_application().quit)

        def switch_to_hide():
            self.set_hide_on_close(True)
            self.close() #Recalls this function

        if self.get_hide_on_close():
            logger.info("Hiding app...")
        else:
            logger.info("Closing app...")
            is_chat_busy = any([chat_row.chat.busy for chat_row in list(self.get_chat_list_page().chat_list_box)])
            is_model_downloading = any([el for el in list(self.local_model_flowbox) if isinstance(el.get_child(), Widgets.models.pulling.PullingModelButton)])
            if is_chat_busy or is_model_downloading:
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
    def chat_search_changed(self, entry):
        self.get_chat_list_page().on_search(entry.get_text())

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

    @Gtk.Template.Callback()
    def message_search_changed(self, entry, current_chat=None):
        search_term=entry.get_text()
        message_results = 0
        if not current_chat and self.chat_bin.get_child():
            current_chat = self.chat_bin.get_child()
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
        if not raw_message.strip():
            return

        current_chat = self.chat_bin.get_child()
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
        row = current_chat.row
        chat_list = row.get_parent()
        GLib.idle_add(chat_list.unselect_all)
        GLib.idle_add(chat_list.remove, row)
        GLib.idle_add(chat_list.prepend, row)
        GLib.idle_add(chat_list.select_row, row)

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
            threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model), daemon=True).start()
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
            threading.Thread(target=self.get_current_instance().use_tools, args=(m_element_bot, current_model, Widgets.tools.get_enabled_tools(self.tool_listbox), True), daemon=True).start()

    def get_selected_model(self):
        selected_item = self.model_dropdown.get_selected_item()
        if selected_item:
            return selected_item.model
        else:
            return Widgets.models.added.FallbackModel

    def get_current_instance(self):
        if self.instance_listbox.get_selected_row():
            return self.instance_listbox.get_selected_row().instance
        else:
            return Widgets.instances.Empty()

    def prepare_alpaca(self):
        self.main_navigation_view.replace_with_tags(['chat'])

        #Chat History
        root_folder = Widgets.chat.ChatList(show_bar=False)
        self.chat_list_navigationview.add(root_folder)
        root_folder.update()

        threading.Thread(target=Widgets.tools.update_available_tools, args=(self.tool_listbox,), daemon=True).start()

        if self.get_application().args.new_chat:
            self.get_chat_list_page().new_chat(self.get_application().args.new_chat)

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

    def on_chat_imported(self, file):
        if file:
            if os.path.isfile(os.path.join(cache_dir, 'import.db')):
                os.remove(os.path.join(cache_dir, 'import.db'))
            file.copy(Gio.File.new_for_path(os.path.join(cache_dir, 'import.db')), Gio.FileCopyFlags.OVERWRITE, None, None, None, None)
            chat_names = [tab.chat.get_name() for tab in list(self.get_chat_list_page().chat_list_box)]
            for chat in SQL.import_chat(os.path.join(cache_dir, 'import.db'), chat_names, self.get_chat_list_page().folder_id):
                print(chat)
                self.get_chat_list_page().add_chat(
                    chat_name=chat[1],
                    chat_id=chat[0],
                    mode=1
                )
            Widgets.dialog.show_toast(_("Chat imported successfully"), self)

    def toggle_searchbar(self):
        current_tag = self.main_navigation_view.get_visible_page_tag()

        searchbars = {
            'chat': self.message_searchbar,
            'model_manager': self.model_searchbar
        }

        if searchbars.get(current_tag):
            searchbars.get(current_tag).set_search_mode(not searchbars.get(current_tag).get_search_mode())

    def get_chat_list_page(self):
        return self.chat_list_navigationview.get_visible_page()

    def push_or_pop(self, page_name:str):
        if self.main_navigation_view.get_visible_page().get_tag() != page_name:
            GLib.idle_add(self.main_navigation_view.push_by_tag, page_name)
        else:
            GLib.idle_add(self.main_navigation_view.pop_to_tag, 'chat')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activities_page.set_child(Widgets.activities.ActivityManager())

        actions = [[{
            'label': _('New Chat'),
            'callback': lambda: self.get_application().lookup_action('new_chat').activate(),
            'icon': 'chat-message-new-symbolic'
        },{
            'label': _('New Folder'),
            'callback': lambda: self.get_application().lookup_action('new_folder').activate(),
            'icon': 'folder-new-symbolic'
        }]]
        popover = Widgets.dialog.Popover(actions)
        popover.set_has_arrow(True)
        popover.set_halign(0)
        self.new_chat_splitbutton.set_popover(popover)

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
        self.global_footer = Widgets.message.GlobalFooter(self.send_message)
        self.global_footer_container.set_child(self.global_footer)
        self.set_focus(self.global_footer.message_text_view)

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        for el in ("default-width", "default-height", "maximized", "hide-on-close"):
            self.settings.bind(el, self, el, Gio.SettingsBindFlags.DEFAULT)

        # Zoom
        Widgets.preferences.set_zoom(Widgets.preferences.get_zoom())

        universal_actions = {
            'new_chat': [lambda *_: self.get_chat_list_page().new_chat(), ['<primary>n']],
            'new_folder': [lambda *_: self.get_chat_list_page().prompt_new_folder(), ['<primary>d']],
            'import_chat': [lambda *_: Widgets.dialog.simple_file(
                parent=self,
                file_filters=[self.file_filter_db],
                callback=self.on_chat_imported
            )],
            'duplicate_current_chat': [lambda *_: self.chat_bin.get_child().row.duplicate()],
            'delete_current_chat': [lambda *_: self.chat_bin.get_child().row.prompt_delete(), ['<primary>w']],
            'rename_current_chat': [lambda *_: self.chat_bin.get_child().row.prompt_rename(), ['F2']],
            'export_current_chat': [lambda *_: self.chat_bin.get_child().row.prompt_export()],
            'toggle_sidebar': [lambda *_: self.split_view_overlay.set_show_sidebar(not self.split_view_overlay.get_show_sidebar()), ['F9']],
            'toggle_search': [lambda *_: self.toggle_searchbar(), ['<primary>f']],
            'model_manager' : [lambda *_: self.push_or_pop('model_manager'), ['<primary>m']],
            'instance_manager' : [lambda *_: self.push_or_pop('instance_manager'), ['<primary>i']],
            'add_model_by_name' : [lambda *i: Widgets.dialog.simple_entry(
                parent=self,
                heading=_('Pull Model'),
                body=_('Please enter the model name following this template: name:tag'),
                callback=lambda name: threading.Thread(target=Widgets.models.available.pull_model_confirm, args=(name, self.get_current_instance(), self), daemon=True).start(),
                entries={'placeholder': 'deepseek-r1:7b'}
            )],
            'reload_added_models': [lambda *_: GLib.idle_add(Widgets.models.update_added_model_list, self)],
            'tool_manager': [lambda *_: self.push_or_pop('tool_manager'), ['<primary>t']],
            'start_quick_ask': [lambda *_: self.get_application().create_quick_ask().present(), ['<primary><alt>a']],
            'model_creator_existing': [lambda *_: Widgets.models.common.prompt_existing(self)],
            'model_creator_gguf': [lambda *_: Widgets.models.common.prompt_gguf(self)],
            'preferences': [lambda *_: Widgets.preferences.PreferencesDialog().present(self), ['<primary>comma']],
            'zoom_in': [lambda *_: Widgets.preferences.zoom_in(), ['<primary>plus']],
            'zoom_out': [lambda *_: Widgets.preferences.zoom_out(), ['<primary>minus']]
        }
        for action_name, data in universal_actions.items():
            self.get_application().create_action(action_name, data[0], data[1] if len(data) > 1 else None)

        def verify_powersaver_mode():
            self.banner.set_revealed(
                Gio.PowerProfileMonitor.dup_default().get_power_saver_enabled() and
                self.settings.get_value('powersaver-warning').unpack() and
                self.get_current_instance().instance_type == 'ollama:managed'
            )
        Gio.PowerProfileMonitor.dup_default().connect("notify::power-saver-enabled", lambda *_: verify_powersaver_mode())
        self.banner.connect('button-clicked', lambda *_: self.banner.set_revealed(False))

        self.prepare_alpaca()
        if self.settings.get_value('skip-welcome').unpack():
            notice_dialog = Widgets.welcome.Notice()
            if not self.settings.get_value('last-notice-seen').unpack() == notice_dialog.get_name():
                notice_dialog.present(self)
        else:
            self.main_navigation_view.replace([Widgets.welcome.Welcome()])
