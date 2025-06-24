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

    toast_overlay = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    global_footer_container = Gtk.Template.Child()

    # tts
    message_dictated = None

    @Gtk.Template.Callback()
    def closing_app(self, element):
        if self.get_application().main_alpaca_window.get_visible() == False:
            self.get_application().quit()

    @Gtk.Template.Callback()
    def save_chat(self, button):
        chat = self.toast_overlay.get_child()
        new_chat = self.get_application().main_alpaca_window.new_chat(chat.get_name())
        for message in list(chat.container):
            SQL.insert_or_update_message(message, new_chat.chat_id)
            for attachment in list(message.attachment_container.container) + list(message.image_attachment_container.container):
                SQL.insert_or_update_attachment(message, attachment)
        self.get_application().main_alpaca_window.chat_list_box.select_row(new_chat.row)
        self.get_application().main_alpaca_window.present()
        self.close()

    def get_current_instance(self):
        selected_instance = self.settings.get_value('selected-instance').unpack()
        instances = SQL.get_instances()
        if len(instances) > 0:
            matching_instances = [i for i in instances if i.get('id') == selected_instance]
            if len(matching_instances) > 0:
                return Widgets.instances.create_instance_row(matching_instances[0]).instance
            return Widgets.instances.create_instance_row(instances[0]).instance

    def send_message(self, mode:int=0):
        #Mode = 0 (normal), Mode = 1 (System), Mode = 2 (Use Tools)3
        buffer = self.global_footer.get_buffer()
        message = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
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

        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())

        chat = self.toast_overlay.get_child()

        m_element = Widgets.message.Message(
            dt=datetime.now(),
            message_id=generate_uuid(),
            chat=chat,
            mode=0 if mode in (0,2) else 2
        )
        chat.add_message(m_element)

        for old_attachment in list(self.global_footer.attachment_container.container):
            attachment = m_element.add_attachment(
                file_id = generate_uuid(),
                name = old_attachment.file_name,
                attachment_type = old_attachment.file_type,
                content = old_attachment.file_content
            )
            old_attachment.delete()

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
        buffer = self.global_footer.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), message, len(message.encode('utf-8')))
        self.send_message()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.global_footer = Widgets.message.GlobalFooter()
        self.global_footer.action_stack.set_visible(False)
        self.global_footer_container.set_child(self.global_footer)

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        self.set_focus(self.global_footer.message_text_view)

        chat = Widgets.chat.Chat(
            name=_('Quick Ask')
        )
        chat.set_visible_child_name('welcome-screen')
        self.toast_overlay.set_child(chat)
        if self.get_application().args.ask:
            self.write_and_send_message(self.get_application().args.ask)
            
