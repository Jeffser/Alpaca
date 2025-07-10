# preferences.py

from gi.repository import Adw, Gtk, Gio
import importlib.util, icu, sys
from ..constants import TTS_VOICES, STT_MODELS, SPEACH_RECOGNITION_LANGUAGES

@Gtk.Template(resource_path='/com/jeffser/Alpaca/preferences.ui')
class PreferencesDialog(Adw.PreferencesDialog):
    __gtype_name__ = 'AlpacaPreferencesDialog'

    background_switch = Gtk.Template.Child()
    powersaver_warning_switch = Gtk.Template.Child()
    zoom_spin = Gtk.Template.Child()
    mic_group = Gtk.Template.Child()
    mic_model_combo = Gtk.Template.Child()
    mic_language_combo = Gtk.Template.Child()
    mic_auto_send_switch = Gtk.Template.Child()
    tts_group = Gtk.Template.Child()
    tts_voice_combo = Gtk.Template.Child()
    tts_auto_mode_combo = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def zoom_changed(self, spinner):
        settings = Gtk.Settings.get_default()
        settings.reset_property('gtk-xft-dpi')
        settings.set_property('gtk-xft-dpi',  settings.get_property('gtk-xft-dpi') + (int(spinner.get_value()) - 100) * 400)

    def __init__(self):
        super().__init__()

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")

        self.settings.bind('hide-on-close', self.background_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('powersaver-warning', self.powersaver_warning_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('zoom', self.zoom_spin, 'value', Gio.SettingsBindFlags.DEFAULT)
        self.mic_group.set_visible(importlib.util.find_spec('whisper'))

        string_list = Gtk.StringList()
        for model, size in STT_MODELS.items():
            string_list.append('{} ({})'.format(model.title(), size))
        self.mic_model_combo.set_model(string_list)
        self.settings.bind('stt-model', self.mic_model_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        string_list = Gtk.StringList()
        for lan in SPEACH_RECOGNITION_LANGUAGES:
            string_list.append('{} ({})'.format(icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title(), lan))
        self.mic_language_combo.set_model(string_list)
        self.settings.bind('stt-language', self.mic_language_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('stt-auto-send', self.mic_auto_send_switch, 'active', Gio.SettingsBindFlags.DEFAULT)

        self.tts_group.set_visible(importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'))

        string_list = Gtk.StringList()
        for name in TTS_VOICES:
            string_list.append(name)
        self.tts_voice_combo.set_model(string_list)
        self.settings.bind('tts-model', self.tts_voice_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('tts-auto-dictate', self.tts_auto_mode_combo, 'active', Gio.SettingsBindFlags.DEFAULT)

        if sys.platform in ('win32', 'darwin'): # MacOS and Windows
            self.powersaver_warning_switch.set_visible(False)
            self.background_switch.set_visible(False)
