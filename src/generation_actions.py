# generation_actions.py

import logging, json, os
logger = logging.getLogger(__name__)

import datetime, time, random, threading

from gi.repository import Adw, Gtk

window = None

"""
VARIABLE EXAMPLE
variables = {
    NAME: {
        "value": VALUE,
        "type": TYPE (str, bool, int, float)
    }
}
"""


class action(Adw.ActionRow):

    variables = {}

    def __init__(self, variables:dict, enabled:bool=True):
        for name, data in self.variables.items():
            self.variables[name]['value'] = variables.get(name, data.get('value'))

        super().__init__(
            title = self.name,
            subtitle = self.description
        )

        info_button = Gtk.Button(icon_name='edit-symbolic', css_classes=['flat', 'accent'], valign=3)
        self.add_suffix(info_button)
        self.enable_switch = Gtk.Switch(active=enabled, valign=3)
        self.add_suffix(self.enable_switch)

    def is_enabled(self) -> bool:
        return self.enable_switch.get_active()

    def get_tool(self) -> dict:
        return {
            "type": "function",
            "function": self.tool
        }

class get_current_datetime(action):
    tool = {
        "name": "get_current_datetime",
        "description": "Gets the current date and/or time.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Whether to get date and/or time",
                    "enum": [
                        "date",
                        "time",
                        "date and time"
                    ]
                }
            },
            "required": [
                "type"
            ],
        },
        "strict": True
    }
    name = _("Get Current Datetime")
    description = _("Gets the current date and/or time.")
    variables = {}

    def run(self, arguments, messages, bot_message) -> dict:
        formats = {
            "date": "%A, %B %d %Y",
            "time": "%H:%M %p",
            "date and time": "%A, %B %d %Y, %H:%M %p"
        }
        type_to_get = arguments.get("type", "date and time")
        format_to_get = formats.get(arguments.get("type", "date and time"), "%b %d %Y, %H:%M %p")
        log_to_message('Getting {} using {} format...'.format(type_to_get, format_to_get), bot_message, True)
        current_datetime = datetime.datetime.now().strftime(format_to_get)
        return current_datetime

available_actions = [get_current_datetime]

def update_available_tools():
    actions_parameters = window.sql_instance.get_actions_parameters()
    for ac in available_actions:
        action_element = ac(actions_parameters.get(ac.tool.get('name'), {}).get('variables', {}))
        window.action_listbox.prepend(action_element)

def get_enabled_tools() -> list:
    tools = []
    for ac in list(window.action_listbox):
        if ac.is_enabled():
            tools.append(ac.get_tool())
    return tools

def run_tool(action_name:str, arguments:dict, messages:list, bot_message):
    actions = [a for a in list(window.action_listbox) if a.tool.get('name') == action_name]
    if actions:
        action = actions[0]
        response = action.run(arguments, messages, bot_message)
        return response

def log_to_message(text:str, bot_message, animate:bool):
    for s in text.split(' '):
        bot_message.update_message({"content": '{} '.format(s)})
        if animate:
            time.sleep(round(random.random()/4, 2))
    bot_message.update_message({"content": "\n"})
