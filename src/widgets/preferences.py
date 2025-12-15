# preferences.py

from gi.repository import Adw, Gtk, Gio, GLib
import importlib.util, icu, sys, os
from ..constants import TTS_VOICES, STT_MODELS, SPEACH_RECOGNITION_LANGUAGES, REMBG_MODELS, IN_FLATPAK
from . import dialog
from ..sql_manager import Instance as SQL

@Gtk.Template(resource_path='/com/jeffser/Alpaca/preferences.ui')
class PreferencesDialog(Adw.PreferencesDialog):
    __gtype_name__ = 'AlpacaPreferencesDialog'

    #GENERAL
    background_switch = Gtk.Template.Child()
    powersaver_warning_switch = Gtk.Template.Child()
    show_model_manager_shortcut_switch = Gtk.Template.Child()
    folder_search_mode_switch = Gtk.Template.Child()
    zoom_spin = Gtk.Template.Child()
    regenerate_after_edit = Gtk.Template.Child()
    image_size_spin = Gtk.Template.Child()

    #AUDIO
    mic_group = Gtk.Template.Child()
    mic_model_combo = Gtk.Template.Child()
    mic_language_combo = Gtk.Template.Child()
    mic_auto_send_switch = Gtk.Template.Child()
    tts_group = Gtk.Template.Child()
    tts_voice_combo = Gtk.Template.Child()
    tts_auto_mode_combo = Gtk.Template.Child()
    tts_speed_spin = Gtk.Template.Child()
    audio_page = Gtk.Template.Child()

    #ACTIVITIES
    activity_mode = Gtk.Template.Child()
    default_tool = Gtk.Template.Child()

    activity_web_browser_engine = Gtk.Template.Child()
    activity_web_browser_query_url = Gtk.Template.Child()
    activity_web_browser_homepage_url = Gtk.Template.Child()
    search_engine_presets = [
        ['https://startpage.com/sp/search?query={}', 'https://startpage.com'],
        ['https://duckduckgo.com/?q={}', 'https://duckduckgo.com/'],
        ['https://google.com/search?q={}', 'https://google.com']
    ]

    activity_terminal_type = Gtk.Template.Child()
    activity_terminal_ssh_user = Gtk.Template.Child()
    activity_terminal_ssh_ip = Gtk.Template.Child()
    activity_terminal_flatpak_warning = Gtk.Template.Child()
    activity_terminal_flatpak_warning_command = Gtk.Template.Child()

    activity_background_remover_default_model = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def zoom_changed(self, spinner):
        set_zoom(int(spinner.get_value()))

    @Gtk.Template.Callback()
    def delete_all_chats_button_pressed(self, button):
        root = self.get_root()
        def delete_all_chats():
            SQL.factory_reset()
            root_folder = list(root.chat_list_navigationview.get_navigation_stack())[0]
            GLib.idle_add(root.chat_list_navigationview.pop_to_page, root_folder)
            root_folder.update()

        dialog.simple(
            parent=root,
            heading=_("Delete All Chats"),
            body=_("Are you sure you want to delete every chat and folder?"),
            callback=delete_all_chats,
            button_appearance='destructive'
        )
        self.close()

    @Gtk.Template.Callback()
    def activity_web_browser_engine_changed(self, dropdown, gparam=None):
        selected_index = dropdown.get_selected()
        self.activity_web_browser_query_url.set_visible(selected_index == 3)
        self.activity_web_browser_homepage_url.set_visible(selected_index == 3)

        if selected_index < 3:
            self.activity_web_browser_query_url.set_text(self.search_engine_presets[selected_index][0])
            self.activity_web_browser_homepage_url.set_text(self.search_engine_presets[selected_index][1])

    @Gtk.Template.Callback()
    def activity_terminal_type_changed(self, dropdown, gparam=None):
        selected_index = dropdown.get_selected()
        self.activity_terminal_ssh_user.set_visible(selected_index == 1)
        self.activity_terminal_ssh_ip.set_visible(selected_index == 1)
        self.activity_terminal_flatpak_warning.set_visible(selected_index == 0 and IN_FLATPAK)
        self.activity_terminal_flatpak_warning_command.set_visible(selected_index == 0 and IN_FLATPAK)

    def __init__(self):
        super().__init__()

        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")

        dropdown_factory = Gtk.SignalListItemFactory()
        dropdown_factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=0, xalign=0)))
        dropdown_factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().get_string()))

        # GENERAL
        self.settings.bind('hide-on-close', self.background_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('powersaver-warning', self.powersaver_warning_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('show-model-manager-shortcut', self.show_model_manager_shortcut_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('folder-search-mode', self.folder_search_mode_switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('zoom', self.zoom_spin, 'value', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('regenerate-after-edit', self.regenerate_after_edit, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.mic_group.set_visible(importlib.util.find_spec('whisper'))

        if sys.platform in ('win32', 'darwin'): # MacOS and Windows
            self.powersaver_warning_switch.set_visible(False)
            self.background_switch.set_visible(False)

        self.settings.bind('max-image-size', self.image_size_spin, 'value', Gio.SettingsBindFlags.DEFAULT)

        # AUDIO
        for model, size in STT_MODELS.items():
            self.mic_model_combo.get_model().append('{} ({})'.format(model.title(), size))
        self.mic_model_combo.set_factory(dropdown_factory)
        self.settings.bind('stt-model', self.mic_model_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        for lan in SPEACH_RECOGNITION_LANGUAGES:
            self.mic_language_combo.get_model().append('{} ({})'.format(icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title(), lan))
        self.mic_language_combo.set_factory(dropdown_factory)
        self.settings.bind('stt-language', self.mic_language_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('stt-auto-send', self.mic_auto_send_switch, 'active', Gio.SettingsBindFlags.DEFAULT)

        self.tts_group.set_visible(importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'))

        self.audio_page.set_visible(importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice') and importlib.util.find_spec('whisper'))

        for name in TTS_VOICES:
            self.tts_voice_combo.get_model().append(name)
        self.tts_voice_combo.set_factory(dropdown_factory)
        self.settings.bind('tts-model', self.tts_voice_combo, 'selected', Gio.SettingsBindFlags.DEFAULT)

        self.settings.bind('tts-auto-dictate', self.tts_auto_mode_combo, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('tts-speed', self.tts_speed_spin, 'value', Gio.SettingsBindFlags.DEFAULT)

        # ACTIVITIES
        self.settings.bind('activity-mode', self.activity_mode, 'selected', Gio.SettingsBindFlags.DEFAULT)
        self.activity_mode.set_factory(dropdown_factory)
        self.settings.bind('default-tool', self.default_tool, 'selected', Gio.SettingsBindFlags.DEFAULT)
        self.default_tool.set_factory(dropdown_factory)
        self.settings.bind('activity-webbrowser-query-url', self.activity_web_browser_query_url , 'text', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('activity-webbrowser-homepage-url', self.activity_web_browser_homepage_url , 'text', Gio.SettingsBindFlags.DEFAULT)
        selected_index=3
        for i, preset in enumerate(self.search_engine_presets):
            if preset[0] == self.settings.get_value('activity-webbrowser-query-url').unpack() and preset[1] == self.settings.get_value('activity-webbrowser-homepage-url').unpack():
                selected_index=i
        self.activity_web_browser_engine.set_selected(selected_index)
        self.activity_web_browser_engine.set_factory(dropdown_factory)
        self.activity_web_browser_engine_changed(self.activity_web_browser_engine)

        self.settings.bind('activity-terminal-type', self.activity_terminal_type, 'selected', Gio.SettingsBindFlags.DEFAULT)
        self.activity_terminal_type.set_factory(dropdown_factory)
        self.settings.bind('activity-terminal-username', self.activity_terminal_ssh_user, 'text', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('activity-terminal-ip', self.activity_terminal_ssh_ip, 'text', Gio.SettingsBindFlags.DEFAULT)

        if not self.settings.get_value('activity-terminal-username').unpack():
            self.settings.set_string('activity-terminal-username', os.getenv('USER'))
        if not self.settings.get_value('activity-terminal-ip').unpack():
            self.settings.set_string('activity-terminal-ip', '127.0.0.1')
        self.activity_terminal_type_changed(self.activity_terminal_type)

        for m in REMBG_MODELS.values():
            self.activity_background_remover_default_model.get_model().append('{} ({})'.format(m.get('display_name'), m.get('size')))
        self.activity_background_remover_default_model.set_factory(dropdown_factory)
        self.settings.bind('activity-background-remover-model', self.activity_background_remover_default_model, 'selected', Gio.SettingsBindFlags.DEFAULT)


def get_zoom():
    settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
    return settings.get_value('zoom').unpack() or 100

def set_zoom(new_value):
    new_value = max(100, min(200, new_value))
    new_value = (new_value // 10) * 10  # Snap to nearest 10
    settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
    settings.set_int('zoom', new_value)

    # Baseline DPI is 96*1024 (at 100%)
    # Always recalculate from baseline
    gtk_settings = Gtk.Settings.get_default()
    gtk_settings.reset_property('gtk-xft-dpi')
    dpi = (96 * 1024) + (new_value - 100) * 400
    gtk_settings.set_property('gtk-xft-dpi', dpi)

def zoom_in(*_):
    set_zoom(get_zoom() + 10)

def zoom_out(*_):
    set_zoom(get_zoom() - 10)
