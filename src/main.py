# main.py
#
# Copyright 2025 Jeffser
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
Main script run at launch, handles actions, about dialog and the app itself (not the window)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, Gio, Adw, GtkSource
GtkSource.init()

from .constants import TRANSLATORS, cache_dir, data_dir, config_dir, source_dir
from .sql_manager import Instance as SQL

SQL.initialize()

import os
os.environ["TORCH_HOME"] = os.path.join(data_dir, "torch")

import sys
import logging
import argparse
import time

from pydbus import SessionBus
from datetime import datetime

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="Alpaca")

_loaded_window_libraries = {}

_window_loaders = {
    'alpaca': lambda: __import__('alpaca.window', fromlist=['AlpacaWindow']).AlpacaWindow,
    'quick-ask': lambda: __import__('alpaca.quick_ask', fromlist=['QuickAskWindow']).QuickAskWindow,
    'live-chat': lambda: __import__('alpaca.live_chat', fromlist=['LiveChatWindow']).LiveChatWindow,
}

def get_window_library(name: str) -> Adw.Window:
    if name not in _window_loaders:
        raise ValueError(f"Unknown window library: {name}")

    if name not in _loaded_window_libraries:
        _loaded_window_libraries[name] = _window_loaders[name]()

    return _loaded_window_libraries[name]

class AlpacaService:
    """
    <node>
        <interface name='com.jeffser.Alpaca'>
            <method name='IsRunning'>
                <arg type='s' name='result' direction='out'/>
            </method>
            <method name='Open'>
                <arg type='s' name='chat' direction='in'/>
            </method>
            <method name='Create'>
                <arg type='s' name='chat' direction='in'/>
            </method>
            <method name='Ask'>
                <arg type='s' name='message' direction='in'/>
            </method>
            <method name='Present'>
            </method>
            <method name='PresentAsk'>
            </method>
            <method name='PresentLive'>
            </method>
        </interface>
    </node>
    """

    def __init__(self, app):
        self.app = app

    def IsRunning(self):
        return 'yeah'

    def Present(self):
        self.app.props.active_window.present()

    def PresentAsk(self):
        self.app.create_quick_ask().present()

    def PresentLive(self):
        self.app.create_live_chat().present()

    def Open(self, chat_name:str):
        for chat_row in list(self.app.props.active_window.chat_list_box):
            if chat_row.chat_window.get_name() == chat_name:
                self.app.props.active_window.chat_list_box.select_row(chat_row)
                self.Present()

    def Create(self, chat_name:str):
        self.app.props.active_window.new_chat(chat_name)
        self.Present()

    def Ask(self, message:str):
        time.sleep(1)
        quick_ask_window = self.app.create_quick_ask()
        quick_ask_window.present()
        quick_ask_window.write_and_send_message(message)

class AlpacaApplication(Adw.Application):
    __gtype_name__ = 'AlpacaApplication'

    main_alpaca_window = None

    def __init__(self, version):
        super().__init__(application_id='com.jeffser.Alpaca',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.create_action('quit', lambda *_: self.props.active_window.closing_app(None), ['<primary>q'])
        self.create_action('preferences', lambda *_: self.props.active_window.preferences_dialog.present(self.props.active_window), ['<primary>comma'])
        self.create_action('about', self.on_about_action)
        self.set_accels_for_action("win.show-help-overlay", ['<primary>slash'])
        self.version = version
        self.args = parser.parse_args()
        if sys.platform in ('linux', 'linux2'):
            try:
                SessionBus().publish('com.jeffser.Alpaca', AlpacaService(self))
            except:
                # The app is probably already running so let's use dbus to interact if needed
                app_service = SessionBus().get("com.jeffser.Alpaca")
                if app_service.IsRunning() == 'yeah':
                    app_service.Present()
                else:
                    raise Exception('Alpaca not running')
                if self.args.new_chat:
                    app_service.Create(self.args.new_chat)
                elif self.args.ask:
                    app_service.Ask(self.args.ask)
                elif self.args.quick_ask:
                    app_service.PresentAsk()
                elif self.args.live_chat:
                    app_service.PresentLive()
                sys.exit(0)

    def create_quick_ask(self):
        return get_window_library('quick-ask')(application=self)

    def create_live_chat(self):
        return get_window_library('live-chat')(application=self)

    def do_activate(self):
        self.main_alpaca_window = self.props.active_window
        if not self.main_alpaca_window:
            self.main_alpaca_window = get_window_library('alpaca')(application=self)
        if self.args.quick_ask or self.args.ask:
            self.create_quick_ask().present()
        elif self.args.live_chat:
            self.create_live_chat().present()
        else:
            self.main_alpaca_window.present()

        if sys.platform == 'darwin': # MacOS
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property('gtk-xft-antialias', 1)
                settings.set_property('gtk-decoration-layout', 'close,minimize,maximize:menu')
                settings.set_property('gtk-font-name', 'Microsoft Sans Serif')
                settings.set_property('gtk-xft-dpi', 110592)
            win.add_css_class('macos')
        elif sys.platform == 'win32': # Windows
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property('gtk-font-name', 'Segoe UI')
        if sys.platform in ('win32', 'darwin'): # MacOS and Windows
            win.powersaver_warning_switch.set_visible(False)
            win.background_switch.set_visible(False)

    def on_about_action(self, widget, a):
        current_year = str(datetime.now().year)
        about = Adw.AboutDialog(
            application_name='Alpaca',
            application_icon='com.jeffser.Alpaca',
            developer_name='Jeffry Samuel Eduarte Rojas',
            version=self.version,
            release_notes_version=self.version,
            support_url="https://github.com/Jeffser/Alpaca/discussions/155",
            developers=['Jeffser https://jeffser.com'],
            designers=[
                'Jeffser https://jeffser.com', 
                'Tobias Bernard (App Icon) https://tobiasbernard.com/'
            ],
            translator_credits='\n'.join(TRANSLATORS),
            copyright=f'© {current_year} Alpaca Jeffry Samuel Eduarte Rojas\n'
                      f'© {current_year} Ollama Meta Platforms, Inc.\n'
                      f'© {current_year} ChatGPT OpenAI, Inc.\n'
                      f'© {current_year} Gemini Google Alphabet, Inc.\n'
                      f'© {current_year} Together.ai\n'
                      f'© {current_year} Venice AI\n'
                      f'© {current_year} Deepseek\n'
                      f'© {current_year} Openrouter\n'
                      f'© {current_year} Gorqcloud\n'
                      f'© {current_year} Anthropic\n'
                      f'© {current_year} Lambda.ai\n'
                      f'© {current_year} Fireworks.ai\n'
                      f'© {current_year} Microsoft',
            issue_url='https://github.com/Jeffser/Alpaca/issues',
            license_type=Gtk.License.GPL_3_0,
            website="https://jeffser.com/alpaca"
        )
        
        about.add_link(_("Documentation"), "https://github.com/Jeffser/Alpaca/wiki")
        about.add_link(_("Become a Sponsor"), "https://github.com/sponsors/Jeffser")
        about.add_link(_("Discussions"), "https://github.com/Jeffser/Alpaca/discussions")
        about.present(self.props.active_window)

    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

def main(version):
    logging.basicConfig(
        format="%(levelname)s\t[%(filename)s | %(funcName)s] %(message)s",
        level=logging.INFO,
        handlers=[logging.StreamHandler(stream=sys.stdout)]
    )

    for directory in (cache_dir, data_dir, config_dir, source_dir):
        if not os.path.isdir(directory):
            os.mkdir(directory)

    parser.add_argument('--version', action='store_true', help='Display the application version and exit.')
    parser.add_argument('--new-chat', type=str, metavar='"CHAT"', help="Start a new chat with the specified title.")
    parser.add_argument('--list-chats', action='store_true', help='Display all the current chats')
    parser.add_argument('--ask', type=str, metavar='"MESSAGE"', help="Open Quick Ask with message")
    parser.add_argument('--quick-ask', action='store_true', help='Open Quick Ask')
    parser.add_argument('--live-chat', action='store_true', help='Open Live Chat')
    args = parser.parse_args()

    if args.version:
        print(f"Alpaca version {version}")
        sys.exit(0)

    if args.list_chats:
        chats = SQL.get_chats()
        if chats:
            for chat in chats:
                print(chat[1])
        else:
            print()
        sys.exit(0)

    logger.info(f"Alpaca version: {version}")

    return AlpacaApplication(version).run([])
