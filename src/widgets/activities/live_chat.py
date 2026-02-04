# live_chat.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from ...constants import IN_FLATPAK, data_dir, REMBG_MODELS
from .. import dialog, attachments, models, chat, message, instances, voice
from ...sql_manager import generate_uuid, prettify_model_name, Instance as SQL
import base64, os, threading, datetime

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/live_chat.ui')
class LiveChat(Adw.Bin):
    __gtype_name__ = 'AlpacaLiveChat'

    animation_signals = {}

    sheet = Gtk.Template.Child()
    chat = Gtk.Template.Child()
    overlay = Gtk.Template.Child()
    background = Gtk.Template.Child()
    pfp_avatar = Gtk.Template.Child()
    pfp_spinner = Gtk.Template.Child()
    global_footer = Gtk.Template.Child()

    show_messages_button = Gtk.Template.Child()
    close_button = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

        self.chat.chat_id='LiveChat'
        self.chat.welcome_screen.set_icon_name('')
        self.chat.welcome_screen.set_title(_('No Messages'))
        self.chat.welcome_screen.set_description(_('Begin by speaking to the model'))
        self.chat.welcome_screen.set_child(None)
        self.chat.set_visible_child_name('welcome-screen')

        m_element = message.Message(
            dt=datetime.datetime.now(),
            message_id=generate_uuid(),
            mode=2
        )
        self.chat.add_message(m_element)
        m_element.block_container.set_content("Have a natural and flowing conversation with the user. Respond in a clear, engaging, and human-like manner. Keep replies concise unless more detail is needed.")
        list(self.sheet)[2].set_margin_start(10)
        list(self.sheet)[2].set_margin_end(10)

        # Prepare Global Footer
        self.global_footer.model_manager_shortcut.set_visible(False)
        self.global_footer.wrap_box.set_wrap_policy(0)
        self.global_footer.attachment_button.set_visible(False)
        self.global_footer.action_stack.set_visible(False)
        self.global_footer.tool_selector.set_visible(False)
        self.global_footer.wrap_box.prepend(self.show_messages_button)
        self.global_footer.wrap_box.append(self.close_button)
        self.global_footer.model_selector.selector.connect('notify::selected', self.model_dropdown_changed)
        GLib.idle_add(self.model_dropdown_changed, self.global_footer.model_selector.selector)
        self.global_footer.model_selector.set_halign(3)

        # Prepare Text To Speech
        self.global_footer.microphone_button.button.add_css_class('circular')
        self.global_footer.microphone_button.button.add_css_class('p20')
        self.global_footer.microphone_button.button.get_child().set_icon_size(2)
        self.global_footer.microphone_button.button.remove_css_class('br0')
        self.global_footer.microphone_button.set_halign(3)
        self.global_footer.microphone_button.unparent()
        self.global_footer.prepend(self.global_footer.microphone_button )

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

        GLib.idle_add(self.update_close_visibility)

        # Activity
        self.title=_('Live Chat')
        self.activity_icon='headset-symbolic'
        self.buttons={}
        self.extend_to_edge = True

    @Gtk.Template.Callback()
    def show_messages_requested(self, button):
        self.sheet.set_open(True)

    @Gtk.Template.Callback()
    def requested_close(self, button):
        tabview = self.get_ancestor(Adw.TabView)
        if tabview:
            tabview.close_page(tabview.get_selected_page())

    def update_close_visibility(self):
        self.close_button.set_visible(self.get_ancestor(Adw.TabView))

    def toggle_avatar_state(self, state:bool):
        if state:
            GLib.idle_add(self.model_avatar_animation.play)
            GLib.idle_add(self.pfp_spinner.set_visible, False)
        else:
            GLib.idle_add(self.model_avatar_animation.reset)
            GLib.idle_add(self.global_footer.microphone_button.button.set_active, False)
            if self.get_current_instance():
                threading.Thread(target=self.try_turning_on_mic, daemon=True).start()

    def model_dropdown_changed(self, dropdown, user_data=None):
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
        selected_item = self.global_footer.model_selector.get_selected_item()
        if selected_item:
            return selected_item.model
        else:
            return models.added.FallbackModel

    # Use Different Thread
    def try_turning_on_mic(self):
        tries = 0
        while tries < 6:
            if len(voice.library_waiting_queue) == 0:
                self.global_footer.microphone_button.button.set_active(True)
                break
            else:
                tries += 1
                time.sleep(1)

    def send_message(self, mode:int=0, available_tools:dict={}): #mode 0=user 1=system
        buffer = self.global_footer.get_buffer()
        raw_message = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()
        if not raw_message:
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

        chat = self.chat
        if len(list(chat.container)) == 0 or (len(list(chat.container)) == 1 and list(chat.container)[0].mode == 2): # chat is just starting
            chat.use_character(
                button=None,
                ignore_greetings=True,
                model_name=current_model
            )

        m_element = message.Message(
            dt=datetime.datetime.now(),
            message_id=generate_uuid(),
            mode=mode*2
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

        m_element.block_container.set_content(raw_message)

        if mode == 0:
            m_element_bot = message.Message(
                dt=datetime.datetime.now(),
                message_id=generate_uuid(),
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
            if len(available_tools) > 0:
                GLib.idle_add(threading.Thread(target=current_instance.use_tools, args=(m_element_bot, current_model, available_tools, True), daemon=True).start)
            else:
                GLib.idle_add(threading.Thread(target=current_instance.generate_message, args=(m_element_bot, current_model), daemon=True).start)

    def get_current_instance(self):
        return self.get_root().get_application().get_main_window().get_current_instance()

    def on_close(self):
        self.chat.busy = False

    def on_reload(self):
        pass
