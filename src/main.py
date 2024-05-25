# main.py
#
# Copyright 2024 Unknown
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

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw
from .window import AlpacaWindow

class AlpacaApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='com.jeffser.Alpaca',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('clear', lambda *_: AlpacaWindow.clear_chat_dialog(self.props.active_window), ['<primary>e'])
        self.create_action('preferences', lambda *_: AlpacaWindow.show_preferences_dialog(self.props.active_window), ['<primary>p'])
        self.create_action('about', self.on_about_action)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = AlpacaWindow(application=self)
        win.present()

    def on_about_action(self, widget, _):
        about = Adw.AboutDialog(#transient_for=self.props.active_window,
            application_name='Alpaca',
            application_icon='com.jeffser.Alpaca',
            developer_name='Jeffry Samuel Eduarte Rojas',
            version='0.8.1',
            developers=['Jeffser https://jeffser.com'],
            designers=['Jeffser https://jeffser.com'],
            translator_credits='Alex K (Russian) https://github.com/alexkdeveloper\nJeffser (Spanish) https://jeffser.com\nDaimar Stein (Brazilian Portuguese) https://github.com/not-a-dev-stein',
            copyright='© 2024 Jeffser\n© 2024 Ollama',
            issue_url='https://github.com/Jeffser/Alpaca/issues')
        about.present(parent=self.props.active_window)

    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    app = AlpacaApplication()
    return app.run(sys.argv)
