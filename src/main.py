# main.py
#
# Copyright 2024 Jeffser
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

from .window import AlpacaWindow
from .internal import cache_dir, data_dir

import sys
import logging
import os

logger = logging.getLogger(__name__)

translators = [
    'Alex K (Russian) https://github.com/alexkdeveloper',
    'Jeffry Samuel (Spanish) https://github.com/jeffser',
    'Louis Chauvet-Villaret (French) https://github.com/loulou64490',
    'Théo FORTIN (French) https://github.com/topiga',
    'Daimar Stein (Brazilian Portuguese) https://github.com/not-a-dev-stein',
    'CounterFlow64 (Norwegian) https://github.com/CounterFlow64',
    'Aritra Saha (Bengali) https://github.com/olumolu',
    'Yuehao Sui (Simplified Chinese) https://github.com/8ar10der',
    'Aleksana (Simplified Chinese) https://github.com/Aleksanaa',
    'Aritra Saha (Hindi) https://github.com/olumolu',
    'YusaBecerikli (Turkish) https://github.com/YusaBecerikli',
    'Simon (Ukrainian) https://github.com/OriginalSimon',
    'Marcel Margenberg (German) https://github.com/MehrzweckMandala'
]

class AlpacaApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self, version):
        super().__init__(application_id='com.jeffser.Alpaca',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.create_action('quit', lambda *_: self.props.active_window.closing_app(None), ['<primary>w', '<primary>q'])
        self.create_action('preferences', lambda *_: AlpacaWindow.show_preferences_dialog(self.props.active_window), ['<primary>comma'])
        self.create_action('about', self.on_about_action)
        self.version = version

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
            version=self.version,
            support_url="https://github.com/Jeffser/Alpaca/discussions/155",
            developers=['Jeffser https://jeffser.com'],
            designers=['Jeffser https://jeffser.com', 'Tobias Bernard (App Icon) https://tobiasbernard.com/'],
            translator_credits='\n'.join(translators),
            copyright='© 2024 Jeffser\n© 2024 Ollama',
            issue_url='https://github.com/Jeffser/Alpaca/issues',
            license_type=3,
            website="https://jeffser.com/alpaca",
            debug_info=open(os.path.join(data_dir, 'tmp.log'), 'r').read())
        about.add_link("Become a Sponsor", "https://github.com/sponsors/Jeffser")
        about.present(parent=self.props.active_window)

    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    if os.path.isfile(os.path.join(data_dir, 'tmp.log')):
        os.remove(os.path.join(data_dir, 'tmp.log'))
    if os.path.isdir(os.path.join(cache_dir, 'tmp')):
        os.system('rm -rf ' + os.path.join(cache_dir, "tmp/*"))
    else:
        os.mkdir(os.path.join(cache_dir, 'tmp'))
    logging.basicConfig(
        format="%(levelname)s\t[%(filename)s | %(funcName)s] %(message)s",
        level=logging.INFO,
        handlers=[logging.FileHandler(filename=os.path.join(data_dir, 'tmp.log')), logging.StreamHandler(stream=sys.stdout)]
    )
    app = AlpacaApplication(version)
    logger.info(f"Alpaca version: {app.version}")
    return app.run(sys.argv)
