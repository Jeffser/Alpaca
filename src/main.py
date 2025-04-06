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
from gi.repository import Gtk, Gio, Adw, GLib

from .constants import TRANSLATORS, Platforms
from .window import AlpacaWindow
from .internal import cache_dir, data_dir

import sys
import logging
import os
import argparse
import json
import time
import sqlite3

from pydbus import SessionBus
from datetime import datetime

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="Alpaca")

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
        </interface>
    </node>
    """

    def __init__(self, app):
        self.app = app

    def IsRunning(self):
        return 'yeah'

    def Present(self):
        self.app.props.active_window.present()

    def Open(self, chat_name:str):
        for chat_row in self.app.props.active_window.chat_list_box.tab_list:
            if chat_row.chat_window.get_name() == chat_name:
                self.app.props.active_window.chat_list_box.select_row(chat_row)
                self.Present()

    def Create(self, chat_name:str):
        self.app.props.active_window.chat_list_box.new_chat(chat_name)
        self.Present()

    def Ask(self, message:str):
        time.sleep(1)
        self.app.props.active_window.quick_chat(message)

class AlpacaApplication(Adw.Application):
    __gtype_name__ = 'AlpacaApplication'
    """The main application singleton class."""

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
                elif self.args.select_chat:
                    app_service.Open(self.args.select_chat)
                elif self.args.ask:
                    app_service.Ask(self.args.ask)
                sys.exit(0)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = AlpacaWindow(application=self)
        win.present()
        if sys.platform == Platforms.mac_os: # MacOS
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property('gtk-xft-antialias', 1)
                settings.set_property('gtk-decoration-layout', 'close,minimize,maximize:menu')
                settings.set_property('gtk-font-name', 'Microsoft Sans Serif')
                settings.set_property('gtk-xft-dpi', 110592)
            win.add_css_class('macos')
        elif sys.platform == Platforms.windows: # Windows
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property('gtk-font-name', 'Segoe UI')
        if sys.platform in Platforms.ported: # MacOS and Windows
            win.powersaver_warning_switch.set_visible(False)
            win.background_switch.set_visible(False)

    def on_about_action(self, widget, _):
        current_year = str(datetime.now().year)
        about = Adw.AboutDialog(
            transient_for=self.props.active_window,
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
                      f'© {current_year} Fireworks.ai',
            issue_url='https://github.com/Jeffser/Alpaca/issues',
            license_type=Gtk.License.GPL_3_0,
            website="https://jeffser.com/alpaca"
        )
        
        about.add_link(_("Website"), "https://jeffser.com/alpaca")
        about.add_link(_("Documentation"), "https://github.com/Jeffser/Alpaca/wiki")
        about.add_link(_("Become a Sponsor"), "https://github.com/sponsors/Jeffser")
        about.add_link(_("Discussions"), "https://github.com/Jeffser/Alpaca/discussions")
        about.present()

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

    parser.add_argument('--version', action='store_true', help='Display the application version and exit.')
    parser.add_argument('--new-chat', type=str, metavar='"CHAT"', help="Start a new chat with the specified title.")
    parser.add_argument('--list-chats', action='store_true', help='Display all the current chats')
    parser.add_argument('--select-chat', type=str, metavar='"CHAT"', help="Select a chat on launch")
    parser.add_argument('--ask', type=str, metavar='"MESSAGE"', help="Open quick ask with message")
    args = parser.parse_args()

    if args.version:
        print(f"Alpaca version {version}")
        sys.exit(0)

    if args.list_chats:
        sqlite_con = sqlite3.connect(os.path.join(data_dir, "alpaca.db"))
        cursor = sqlite_con.cursor()
        chats = cursor.execute('SELECT chat.name, MAX(message.date_time) AS latest_message_time FROM chat LEFT JOIN message ON chat.id = message.chat_id GROUP BY chat.id ORDER BY latest_message_time DESC').fetchall()
        if chats:
            for chat in chats:
                print(chat[0])
        else:
            print()
        sqlite_con.close()
        sys.exit(0)

    if args.select_chat:
        sqlite_con = sqlite3.connect(os.path.join(data_dir, "alpaca.db"))
        cursor = sqlite_con.cursor()
        cursor.execute("UPDATE preferences SET value=? WHERE id=?", (args.select_chat, 'selected_chat'))
        sqlite_con.commit()
        sqlite_con.close()

    cache_dir_path: str = os.path.join(cache_dir, 'tmp')
    if os.path.isdir(cache_dir_path):
        # TODO: Change this, this is error-prone.
        # And very dangerous, if bwrap doesn't do a good job.
        os.system('rm -rf ' + os.path.join(cache_dir, "tmp/*"))
    else:
        os.mkdir(cache_dir_path)

    app = AlpacaApplication(version)
    logger.info(f"Alpaca version: {app.version}")
    return app.run([])
