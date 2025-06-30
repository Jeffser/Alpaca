# quick_ask.py

"""
Handles the Quick Ask window
"""

import gi
from gi.repository import Adw, Gtk, Gdk, GLib, GtkSource, Gio, Spelling, GObject, GdkPixbuf

from . import widgets as Widgets
from .sql_manager import generate_uuid, prettify_model_name, Instance as SQL

from datetime import datetime

import threading, base64, time

class LiveChatModelRow(GObject.Object):
    __gtype_name__ = 'AlpacaLiveChatModelRow'

    name = GObject.Property(type=str)

    def __init__(self, model_name:str):
        super().__init__()
        self.model_name = model_name
        self.name = prettify_model_name(self.model_name)

    def __str__(self):
        return self.model_name

@Gtk.Template(resource_path='/com/jeffser/Alpaca/live_chat.ui')
class LiveChatWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'AlpacaLiveChatWindow'

    live_chat_background = Gtk.Template.Child()

    microphone_container = Gtk.Template.Child()

    global_footer = None
    global_footer_container = Gtk.Template.Child()

    toast_overlay = Gtk.Template.Child()
    bottom_sheet = Gtk.Template.Child()
    model_dropdown = Gtk.Template.Child()
    model_avatar = Gtk.Template.Child()
    model_avatar_spinner = Gtk.Template.Child()

    preferences_dialog = Gtk.Template.Child()
    dyanamic_background_switch = Gtk.Template.Child()
    auto_mic_switch = Gtk.Template.Child()

    model_avatar_animation:Adw.TimedAnimation = None
    animation_signals = {}

    @Gtk.Template.Callback()
    def closing_app(self, element):
        if self.get_application().main_alpaca_window.get_visible() == False:
            self.get_application().quit()

    @Gtk.Template.Callback()
    def show_messages(self, button):
        self.bottom_sheet.set_open(True)

    @Gtk.Template.Callback()
    def show_preferences(self, button):
        self.preferences_dialog.present(self)

    @Gtk.Template.Callback()
    def reload_models(self, button=None):
        self.model_dropdown.get_model().remove_all()
        current_instance = self.get_current_instance()
        if not current_instance:
            Widgets.dialog.show_toast(_("Please select an instance in Alpaca before chatting"), self)
            self.model_dropdown.set_visible(False)
            return
        models = current_instance.get_local_models()
        default_model = current_instance.properties.get('default_model')
        selected_model_index = -1
        for i, model in enumerate(models):
            self.model_dropdown.get_model().append(LiveChatModelRow(model.get('name')))
            if model.get('name') == default_model:
                selected_model_index = i
        self.model_dropdown.set_visible(len(models) > 0)
        self.model_dropdown.set_enable_search(len(models) > 10)
        if selected_model_index >= 0:
            self.model_dropdown.set_selected(selected_model_index)

    @Gtk.Template.Callback()
    def model_dropdown_changed(self, dropdown, user_data):
        if dropdown.get_selected_item():
            model_name = str(dropdown.get_selected_item())
            model_picture_data = SQL.get_model_preferences(model_name).get('picture')
            if model_picture_data:
                texture = Gdk.Texture.new_from_bytes(
                    GLib.Bytes.new(base64.b64decode(model_picture_data))
                )
                self.model_avatar.set_custom_image(texture)
                if self.settings.get_value('live-chat-dynamic-background').unpack():
                    self.live_chat_background.set_paintable(texture)
                    self.model_avatar.set_show_initials(False)
                else:
                    self.live_chat_background.set_paintable(None)
                    self.model_avatar.set_show_initials(True)
            else:
                self.model_avatar.set_custom_image(None)
                self.model_avatar.set_text(prettify_model_name(model_name))
                self.live_chat_background.set_paintable(None)
                self.model_avatar.set_show_initials(True)

    def get_current_instance(self):
        selected_instance = self.settings.get_value('selected-instance').unpack()
        instances = SQL.get_instances()
        if len(instances) > 0:
            matching_instances = [i for i in instances if i.get('id') == selected_instance]
            if len(matching_instances) > 0:
                return Widgets.instances.create_instance_row(matching_instances[0]).instance
            return Widgets.instances.create_instance_row(instances[0]).instance

    def try_turning_on_mic(self):
        tries = 0
        while tries < 6:
            if len(Widgets.voice.library_waiting_queue) == 0:
                self.global_footer.microphone_button.button.set_active(True)
                break
            else:
                tries += 1
                time.sleep(1)

    def toggle_avatar_state(self, state:bool):
        if state:
            GLib.idle_add(self.model_avatar_animation.play)
            GLib.idle_add(self.model_avatar_spinner.set_visible, False)
        else:
            GLib.idle_add(self.model_avatar_animation.reset)
            GLib.idle_add(self.global_footer.microphone_button.button.set_active, False)
            if self.settings.get_value('live-chat-auto-mic').unpack() and self.get_current_instance():
                threading.Thread(target=self.try_turning_on_mic).start()

    def send_message(self, mode:int=0):
        #Mode = 0 (normal), Mode = 1 (System), Mode = 2 (Use Tools)3
        buffer = self.global_footer.get_buffer()
        message = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        if not message:
            return

        self.global_footer.microphone_button.button.set_active(False)

        current_instance = self.get_current_instance()
        if not current_instance:
            Widgets.dialog.show_toast(_("Please select an instance in Alpaca before chatting"), self)
            return
        current_model = str(self.model_dropdown.get_selected_item())
        if not current_model:
            Widgets.dialog.show_toast(_("Please select add a model for this instance in Alpaca before chatting"), self)
            return
        if current_model not in [m.get('name') for m in current_instance.get_local_models()]:
            Widgets.dialog.show_toast(_("Selected model is not available"), self)
            return

        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())

        chat = self.bottom_sheet.get_sheet()

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

            if len(self.animation_signals) > 0:
                try:
                    for signal_id, signal_widget in self.animation_signals.items():
                        signal_widget.disconnect(signal_id)
                    self.animation_signals = {}
                except Exception as e:
                    pass

            signal_id = m_element_bot.popup.tts_button.connect("notify::visible-child", lambda mic_button, *_: self.toggle_avatar_state(True) if mic_button.get_visible_child_name() == 'button' else None)
            self.animation_signals[signal_id] = m_element_bot.popup.tts_button
            signal_id = m_element_bot.popup.tts_button.button.connect("toggled", lambda button: self.toggle_avatar_state(False) if not button.get_active() else None)
            self.animation_signals[signal_id] = m_element_bot.popup.tts_button.button

            self.model_avatar_spinner.set_visible(True)
            chat.busy = True
            if mode == 0:
                threading.Thread(target=self.get_current_instance().generate_message, args=(m_element_bot, current_model)).start()
            else:
                threading.Thread(target=self.get_current_instance().use_tools, args=(m_element_bot, current_model, Widgets.tools.get_enabled_tools(self.tool_listbox), True)).start()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Prepare Settings
        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")

        self.settings.bind('live-chat-dynamic-background', self.dyanamic_background_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('live-chat-auto-mic', self.auto_mic_switch, 'active', Gio.SettingsBindFlags.DEFAULT)

        # Prepare Chat
        self.bottom_sheet.set_sheet(Widgets.chat.Chat(chat_id='LC'))
        self.bottom_sheet.get_sheet().welcome_screen.set_icon_name('')
        self.bottom_sheet.get_sheet().welcome_screen.set_title(_('No Messages'))
        self.bottom_sheet.get_sheet().welcome_screen.set_description(_('Begin by speaking to the model'))
        self.bottom_sheet.get_sheet().welcome_screen.set_child(None)
        self.bottom_sheet.get_sheet().set_visible_child_name('welcome-screen')
        m_element = Widgets.message.Message(
            dt=datetime.now(),
            message_id=generate_uuid(),
            chat=self.bottom_sheet.get_sheet(),
            mode=2
        )
        self.bottom_sheet.get_sheet().add_message(m_element)
        m_element.block_container.set_content("Have a natural and flowing conversation with the user. Respond in a clear, engaging, and human-like manner. Keep replies concise unless more detail is needed.")

        # Prepare Model Selector
        list(self.model_dropdown)[0].add_css_class('flat')
        self.model_dropdown.set_model(Gio.ListStore.new(LiveChatModelRow))
        self.model_dropdown.set_expression(Gtk.PropertyExpression.new(LiveChatModelRow, None, "name"))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.model_dropdown.set_factory(factory)
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)

        # Prepare Global Footer
        self.global_footer = Widgets.message.GlobalFooter()
        self.global_footer.attachment_button.set_visible(False)
        self.global_footer.action_stack.set_visible(False)
        self.global_footer.microphone_button.get_parent().remove(self.global_footer.microphone_button)
        self.global_footer_container.set_child(self.global_footer)

        # Prepare Text To Speech
        self.global_footer.microphone_button.button.add_css_class('circular')
        self.global_footer.microphone_button.button.add_css_class('p20')
        self.global_footer.microphone_button.button.get_child().set_icon_size(2)
        self.global_footer.microphone_button.button.remove_css_class('br0')
        self.global_footer.microphone_button.set_halign(3)
        self.microphone_container.set_child(self.global_footer.microphone_button)

        # Prepare Avatar
        self.model_avatar_animation = Adw.TimedAnimation(
            target=Adw.PropertyAnimationTarget.new(self.model_avatar, 'size'),
            value_from=200,
            value_to=220,
            duration=1000,
            alternate=True,
            easing=6,
            widget=self.model_avatar,
            repeat_count=0
        )

        self.reload_models()
        self.toggle_avatar_state(False)
