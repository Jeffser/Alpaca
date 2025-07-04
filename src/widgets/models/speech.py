# speech.py

from gi.repository import Gtk, Gio, Adw, Gdk
import logging, os
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from .. import dialog

logger = logging.getLogger(__name__)

class TextToSpeechModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaTextToSpeechModelDialog'

    def __init__(self, model):
        self.model = model

        tbv=Adw.ToolbarView()
        header_bar = Adw.HeaderBar(
            show_title=False
        )

        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: self.model.prompt_remove_model())
        header_bar.pack_start(remove_button)

        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text="https://github.com/hexgrad/kokoro"
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri("https://github.com/hexgrad/kokoro"))
        header_bar.pack_start(web_button)

        tbv.add_top_bar(header_bar)
        tbv.set_content(
            Adw.StatusPage(
                icon_name="bullhorn-symbolic",
                title=self.model.model_title,
                description=_("Local text to speech model provided by Kokoro.")
            )
        )
        super().__init__(
            child=tbv,
            title=self.model.model_title,
            width_request=360,
            height_request=240,
            follows_content_size=True
        )

class TextToSpeechModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaTextToSpeechModelButton'

    def __init__(self, name:str):
        self.model_title = name.title()
        container = Gtk.Box(
            spacing=5,
            margin_start=5,
            margin_end=5,
            margin_top=5,
            margin_bottom=5
        )

        super().__init__(
            name=name,
            child=container,
            css_classes=['p0', 'card']
        )

        image_container = Adw.Bin(
            valign=3,
            halign=3,
            overflow=1,
            child=Gtk.Image.new_from_icon_name("bullhorn-symbolic"),
            margin_start=10,
            margin_end=10
        )
        container.append(image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        container.append(text_container)
        title_label = Gtk.Label(
            label=self.model_title,
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        subtitle_label = Gtk.Label(
            label=_("Text to Speech"),
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(subtitle_label)

        self.connect('clicked', lambda btn: TextToSpeechModelDialog(self).present(self.get_root()))
        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    def remove_model(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, TextToSpeechModelDialog):
            dialog.close()
        name = '{}.pt'.format(TTS_VOICES.get(self.get_name(), ''))
        symlink_path = os.path.join(os.path.join(cache_dir, 'huggingface', 'hub'), name)

        if os.path.islink(symlink_path):
            target_path = os.readlink(symlink_path)
            os.unlink(symlink_path)
            if os.path.isfile(target_path):
                os.remove(target_path)
        self.get_parent().get_parent().remove(self)

    def prompt_remove_model(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        )

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Delete Model'),
                    'callback': self.prompt_remove_model,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()


class SpeechToTextModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaSpeechToTextModelDialog'

    def __init__(self, model):
        self.model = model

        tbv=Adw.ToolbarView()
        header_bar = Adw.HeaderBar(
            show_title=False
        )
        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: self.model.prompt_remove_model())
        header_bar.pack_start(remove_button)

        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text="https://github.com/openai/whisper"
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri("https://github.com/openai/whisper"))
        header_bar.pack_start(web_button)

        tbv.add_top_bar(header_bar)
        tbv.set_content(
            Adw.StatusPage(
                icon_name="audio-input-microphone-symbolic",
                title=self.model.model_title,
                description=_("Local speech to text model provided by OpenAI Whisper."),
                child=Gtk.Label(label=STT_MODELS.get(self.model.get_name(), '~151mb'), css_classes=["dim-label"])
            )
        )
        super().__init__(
            child=tbv,
            title=self.model.model_title,
            width_request=360,
            height_request=240,
            follows_content_size=True
        )

class SpeechToTextModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaSpeechToTextModelButton'

    def __init__(self, name:str):
        self.model_title = name.title()
        container = Gtk.Box(
            spacing=5,
            margin_start=5,
            margin_end=5,
            margin_top=5,
            margin_bottom=5
        )

        super().__init__(
            name=name,
            child=container,
            css_classes=['p0', 'card']
        )

        image_container = Adw.Bin(
            valign=3,
            halign=3,
            overflow=1,
            child=Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic"),
            margin_start=10,
            margin_end=10
        )
        container.append(image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        container.append(text_container)
        title_label = Gtk.Label(
            label=self.model_title,
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        subtitle_label = Gtk.Label(
            label=_("Speech to Text"),
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(subtitle_label)

        self.connect('clicked', lambda btn: SpeechToTextModelDialog(self).present(self.get_root()))
        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    def remove_model(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, SpeechToTextModelDialog):
            dialog.close()
        model_path = os.path.join(data_dir, 'whisper', '{}.pt'.format(self.get_name()))
        if os.path.isfile(model_path):
            os.remove(model_path)
        self.get_parent().get_parent().remove(self)

    def prompt_remove_model(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        )

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Delete Model'),
                    'callback': self.prompt_remove_model,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()
