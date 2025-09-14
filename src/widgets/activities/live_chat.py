# live_chat.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ...constants import IN_FLATPAK, data_dir, REMBG_MODELS
from .. import dialog, attachments, models, chat, message, models, instances, voice
from ...sql_manager import generate_uuid, prettify_model_name, Instance as SQL
import base64, os, threading, datetime

class LiveChatPage(Adw.Bin):
    __gtype_name__ = 'AlpacaLiveChatPage'

    animation_signals = {}

    def __init__(self):
        super().__init__(
            child=Adw.BottomSheet(
                can_open=True,
                can_close=True,
                open=False,
                show_drag_handle=True,
            )
        )

        # Prepare Chat
        self.get_child().set_sheet(
            chat.Chat(chat_id='LiveChat', name=_('Live Chat'))
        )
        self.get_child().get_sheet().welcome_screen.set_icon_name('')
        self.get_child().get_sheet().welcome_screen.set_title(_('No Messages'))
        self.get_child().get_sheet().welcome_screen.set_description(_('Begin by speaking to the model'))
        self.get_child().get_sheet().welcome_screen.set_child(None)
        self.get_child().get_sheet().set_visible_child_name('welcome-screen')
        m_element = message.Message(
            dt=datetime.datetime.now(),
            message_id=generate_uuid(),
            chat=self.get_child().get_sheet(),
            mode=2
        )
        self.get_child().get_sheet().add_message(m_element)
        m_element.block_container.set_content("Have a natural and flowing conversation with the user. Respond in a clear, engaging, and human-like manner. Keep replies concise unless more detail is needed.")
        list(self.get_child())[2].set_margin_start(10)
        list(self.get_child())[2].set_margin_end(10)

        self.background = Gtk.Picture(
            vexpand=True,
            hexpand=True,
            content_fit=0,
            css_classes=['live_chat_background']
        )

        self.overlay = Gtk.Overlay(
            child=self.background
        )

        show_messages_button = Gtk.Button(
            icon_name='chat-bubble-text-symbolic',
            tooltip_text=_('Show Messages')
        )
        show_messages_button.connect('clicked', lambda btn: self.get_child().set_open(True))

        container = Gtk.Box(
            orientation=1
        )
        clamp = Adw.Clamp(
            maximum_size=1000,
            tightening_threshold=800,
            child=container
        )
        scrolled_window = Gtk.ScrolledWindow(
            child=clamp
        )
        self.overlay.add_overlay(scrolled_window)
        self.get_child().set_content(self.overlay)

        self.pfp_avatar=Adw.Avatar(
            valign=3,
            size=200
        )
        pfp_overlay=Gtk.Overlay(
            margin_top=20,
            margin_bottom=20,
            valign=3,
            halign=3,
            css_classes=['model_pfp'],
            overflow=1,
            child=self.pfp_avatar
        )
        self.pfp_spinner = Adw.Spinner(
            visible=False,
            overflow=1,
            css_classes=['osd']
        )
        pfp_overlay.add_overlay(
            self.pfp_spinner
        )
        pfp_bin=Adw.Bin(
            child=pfp_overlay,
            vexpand=True
        )
        container.append(pfp_bin)

        microphone_container=Adw.Bin(
            valign=2
        )
        container.append(microphone_container)
        global_footer_container=Adw.Bin(
            valign=2
        )
        container.append(global_footer_container)

        # Prepare Model Selector
        self.model_dropdown = Gtk.DropDown()
        self.model_dropdown.connect('notify::selected', self.model_dropdown_changed)
        list(self.model_dropdown)[0].add_css_class('flat')
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.model_dropdown.set_factory(factory)
        self.model_dropdown.set_expression(Gtk.PropertyExpression.new(models.added.AddedModelRow, None, "name"))
        list(list(self.model_dropdown)[1].get_child())[1].set_propagate_natural_width(True)

        # Prepare Global Footer
        self.global_footer = message.GlobalFooter(self.send_message)
        self.global_footer.attachment_button.set_visible(False)
        self.global_footer.action_stack.set_visible(False)
        self.global_footer.microphone_button.get_parent().remove(self.global_footer.microphone_button)
        global_footer_container.set_child(self.global_footer)

        # Prepare Text To Speech
        self.global_footer.microphone_button.button.add_css_class('circular')
        self.global_footer.microphone_button.button.add_css_class('p20')
        self.global_footer.microphone_button.button.get_child().set_icon_size(2)
        self.global_footer.microphone_button.button.remove_css_class('br0')
        self.global_footer.microphone_button.set_halign(3)
        microphone_container.set_child(self.global_footer.microphone_button)

        # Prepare Avatar
        self.model_avatar_animation = Adw.TimedAnimation(
            target=Adw.PropertyAnimationTarget.new(self.pfp_avatar, 'size'),
            value_from=200,
            value_to=220,
            duration=1000,
            alternate=True,
            easing=6,
            widget=self.pfp_avatar,
            repeat_count=0
        )


        # Activity
        self.title=_('Live Chat')
        self.activity_icon='headset-symbolic'
        self.buttons=[self.model_dropdown, show_messages_button]

        self.connect('map', lambda *_: self.on_map())

    def on_map(self):
        self.model_dropdown.set_model(self.get_root().get_application().main_alpaca_window.model_dropdown.get_model())

    def toggle_avatar_state(self, state:bool):
        if state:
            GLib.idle_add(self.model_avatar_animation.play)
            GLib.idle_add(self.pfp_spinner.set_visible, False)
        else:
            GLib.idle_add(self.model_avatar_animation.reset)
            GLib.idle_add(self.global_footer.microphone_button.button.set_active, False)
            if self.get_current_instance():
                threading.Thread(target=self.try_turning_on_mic, daemon=True).start()

    def model_dropdown_changed(self, dropdown, user_data):
        if dropdown.get_selected_item():
            model_name = dropdown.get_selected_item().model.get_name()
            model_picture_data = SQL.get_model_preferences(model_name).get('picture')
            if model_picture_data:
                texture = Gdk.Texture.new_from_bytes(
                    GLib.Bytes.new(base64.b64decode(model_picture_data))
                )
                self.pfp_avatar.set_custom_image(texture)
                self.background.set_paintable(texture)
                self.pfp_avatar.set_show_initials(False)
            else:
                self.pfp_avatar.set_custom_image(None)
                self.pfp_avatar.set_text(prettify_model_name(model_name).split(' (')[0])
                self.background.set_paintable(None)
                self.pfp_avatar.set_show_initials(True)

    def get_selected_model(self):
        selected_item = self.model_dropdown.get_selected_item()
        if selected_item:
            return selected_item.model
        else:
            return models.added.FallbackModel

    def try_turning_on_mic(self):
        tries = 0
        while tries < 6:
            if len(voice.library_waiting_queue) == 0:
                self.global_footer.microphone_button.button.set_active(True)
                break
            else:
                tries += 1
                time.sleep(1)

    def send_message(self, mode:int=0):
        #Mode = 0 (normal), Mode = 1 (System), Mode = 2 (Use Tools)
        buffer = self.global_footer.get_buffer()
        message_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        if not message_text:
            return

        self.global_footer.microphone_button.button.set_active(False)

        current_instance = self.get_current_instance()
        if not current_instance:
            dialog.show_toast(_("Please select an instance in Alpaca before chatting"), self.get_root())
            return
        current_model = self.get_selected_model().get_name()
        if not current_model:
            dialog.show_toast(_("Please select add a model for this instance in Alpaca before chatting"), self.get_root())
            return
        if current_model not in [m.get('name') for m in current_instance.get_local_models()]:
            dialog.show_toast(_("Selected model is not available"), self.get_root())
            return

        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())

        chat = self.get_child().get_sheet()

        m_element = message.Message(
            dt=datetime.datetime.now(),
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

        m_element.block_container.set_content(message_text)

        if mode in (0, 2):
            m_element_bot = message.Message(
                dt=datetime.datetime.now(),
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

            self.pfp_spinner.set_visible(True)
            chat.busy = True
            current_instance = self.get_current_instance()
            if mode == 0:
                threading.Thread(target=current_instance.generate_message, args=(m_element_bot, current_model), daemon=True).start()
            else:
                threading.Thread(target=current_instance.use_tools, args=(m_element_bot, current_model, Widgets.tools.get_enabled_tools(self.get_application().main_alpaca_window.tool_listbox), True), daemon=True).start()

    def get_current_instance(self):
        return self.get_root().get_application().main_alpaca_window.get_current_instance()

    def on_close(self):
        self.get_child().get_sheet().busy = False

    def on_reload(self):
        pass
