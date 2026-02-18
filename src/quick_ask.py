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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/quick_ask.ui')
class QuickAskWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'AlpacaQuickAskWindow'

    chat = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    global_footer = Gtk.Template.Child()

    # tts
    message_dictated = None

    @Gtk.Template.Callback()
    def closing_app(self, element):
        if not self.get_application().get_main_window().get_visible():
            # Use GLib.idle_add to ensure proper cleanup sequence
            GLib.idle_add(self.get_application().quit)

    @Gtk.Template.Callback()
    def save_chat(self, button):
        main_window = self.get_application().get_main_window()
        main_window.present()
        new_chat = main_window.get_chat_list_page().new_chat(self.chat.get_name())
        for message in list(self.chat.container):
            SQL.insert_or_update_message(message, force_chat_id=new_chat.chat_id)
            #for attachment in list(message.attachment_container.container) + list(message.image_attachment_container.container):
                #GLib.idle_add(SQL.insert_or_update_attachment, message, attachment)
        new_chat.load_messages()
        GLib.idle_add(new_chat.row.get_parent().select_row, new_chat.row)
        self.close()

    def get_selected_model(self):
        item = self.global_footer.model_selector.get_selected_item()
        if item:
            return item.model

        return Widgets.models.added.FallbackModel

    def get_current_instance(self):
        return self.get_application().get_main_window().get_current_instance()

    def send_message(self, mode:int=0, available_tools:dict={}): #mode 0=user 1=system
        buffer = self.global_footer.get_buffer()

        raw_message = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        if not raw_message:
            return

        current_instance = self.get_current_instance()
        if not current_instance:
            Widgets.dialog.show_toast(_("Please select an instance in Alpaca before chatting"), self)
            return
        current_instance.start()
        current_model = self.get_selected_model().get_name()
        if current_model is None:
            Widgets.dialog.show_toast(_("Please select add a model for this instance in Alpaca before chatting"), self)
            return

        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())

        m_element = Widgets.message.Message(
            dt=datetime.now(),
            message_id=generate_uuid(),
            mode=mode*2
        )
        self.chat.add_message(m_element)

        for old_attachment in list(self.global_footer.attachment_container.container):
            attachment = m_element.add_attachment(
                file_id = generate_uuid(),
                name = old_attachment.file_name,
                attachment_type = old_attachment.file_type,
                content = old_attachment.file_content
            )
            old_attachment.delete()

        m_element.block_container.set_content(raw_message)

        if mode==0:
            m_element_bot = Widgets.message.Message(
                dt=datetime.now(),
                message_id=generate_uuid(),
                mode=1,
                author=current_model
            )
            self.chat.add_message(m_element_bot)
            self.chat.busy=True
            if len(available_tools) > 0:
                GLib.idle_add(threading.Thread(target=self.get_current_instance().use_tools, args=(m_element_bot, current_model, available_tools), daemon=True).start)
            else:
                GLib.idle_add(threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model), daemon=True).start)

    def write_and_send_message(self, message:str):
        buffer = self.global_footer.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), message, len(message.encode('utf-8')))
        self.send_message()

    def get_current_chat(self) -> Gtk.Widget:
        return self.chat

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.global_footer.model_manager_shortcut.set_visible(False)

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        self.set_focus(self.global_footer.message_text_view)

        self.chat.set_visible_child_name('welcome-screen')
        if self.get_application().args.ask:
            self.write_and_send_message(self.get_application().args.ask)
            
