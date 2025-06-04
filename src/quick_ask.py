# quick_ask.py

"""
Handles the Quick Ask window
"""

import gi
from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, Spelling

from . import widgets as Widgets
from .sql_manager import generate_uuid, Instance as SQL

from datetime import datetime

import threading

@Gtk.Template(resource_path='/com/jeffser/Alpaca/QuickAsk/window.ui')
class QuickAskWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'AlpacaQuickAskWindow'

    toast_overlay = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    message_text_view_scrolled_window = Gtk.Template.Child()

    # tts
    message_dictated = None

    @Gtk.Template.Callback()
    def save_chat(self, button):
        chat = self.toast_overlay.get_child()
        window = self.get_application().get_alpaca_window()
        new_chat = window.new_chat(chat.get_name())
        for message in list(chat.container):
            SQL.insert_or_update_message(message, new_chat.chat_id)
        window.chat_list_box.select_row(new_chat.row)
        self.close()

    def get_current_instance(self):
        selected_instance = SQL.get_preference('selected_instance')
        instances = SQL.get_instances()
        if len(instances) > 0:
            matching_instances = [i for i in instances if i.get('id') == selected_instance]
            if len(matching_instances) > 0:
                return Widgets.instance_manager.create_instance_row(matching_instances[0]).instance
            return Widgets.instance_manager.create_instance_row(instances[0]).instance

    def send_message(self, mode:int=0):
        #Mode = 0 (normal), Mode = 1 (System), Mode = 2 (Use Tools)
        message = self.message_text_view.get_buffer().get_text(self.message_text_view.get_buffer().get_start_iter(), self.message_text_view.get_buffer().get_end_iter(), False)
        if not message:
            return

        current_instance = self.get_current_instance()
        if not current_instance:
            Widgets.dialog.show_toast(_("Please select an instance in Alpaca before chatting"), self)
            return
        current_model = current_instance.get_default_model()
        if current_model is None:
            Widgets.dialog.show_toast(_("Please select add a model for this instance in Alpaca before chatting"), self)
            return

        buffer = self.message_text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())

        chat = self.toast_overlay.get_child()

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

    def write_and_send_message(self, message:str):
        buffer = self.message_text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), message, len(message.encode('utf-8')))
        self.send_message()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.message_text_view = GtkSource.View(
            css_classes=['message_text_view'],
            top_margin=10,
            bottom_margin=10,
            hexpand=True,
            wrap_mode=3,
            valign=3,
            name="main_text_view"
        )

        adapter = Spelling.TextBufferAdapter.new(self.message_text_view.get_buffer(), Spelling.Checker.get_default())
        self.message_text_view_scrolled_window.set_child(self.message_text_view)
        self.message_text_view.get_buffer().set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('adwaita'))
        self.message_text_view.set_extra_menu(adapter.get_menu_model())
        self.message_text_view.insert_action_group('spelling', adapter)
        adapter.set_enabled(True)
        self.message_text_view_scrolled_window.get_parent().append(Widgets.speech_recognition.MicrophoneButton(self.message_text_view))

        self.set_focus(self.message_text_view)

        chat = Widgets.chat.Chat(
            name=_('Quick Ask')
        )
        chat.set_visible_child_name('welcome-screen')
        self.toast_overlay.set_child(chat)
        if self.get_application().args.ask:
            self.write_and_send_message(self.get_application().args.ask)
            
