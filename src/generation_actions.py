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
        info_button.connect('clicked', lambda *_: self.show_action_page())
        self.add_suffix(info_button)
        self.enable_switch = Gtk.Switch(active=enabled, valign=3)
        self.enable_switch.connect('state-set', lambda *_: self.enabled_changed())
        self.add_suffix(self.enable_switch)

    def enabled_changed(self):
        window.sql_instance.insert_or_update_actions_parameters(self.name, self.extract_variables_for_sql(), self.is_enabled())

    def is_enabled(self) -> bool:
        return self.enable_switch.get_active()

    def get_tool(self) -> dict:
        return {
            "type": "function",
            "function": self.tool
        }

    def extract_variables_for_sql(self) -> dict:
        variables_for_sql = {}
        for name, data in self.variables.items():
            variables_for_sql[name] = data.get('value')
        return variables_for_sql

    def save_variables(self, variables_group):
        for v in list(list(list(variables_group)[0])[1])[0]:
            if v.get_name() in list(self.variables.keys()):
                if isinstance(v, Adw.EntryRow) or isinstance(v, Adw.PasswordEntryRow):
                    self.variables[v.get_name()]['value'] = v.get_text()
                elif isinstance(v, Adw.SpinRow):
                    self.variables[v.get_name()]['value'] = v.get_value()
                elif isinstance(v, Adw.SwitchRow):
                    self.variables[v.get_name()]['value'] = v.get_active()

        window.sql_instance.insert_or_update_actions_parameters(self.name, self.extract_variables_for_sql(), self.is_enabled())
        window.main_navigation_view.pop()

    def show_action_page(self):
        action_page = Adw.PreferencesPage()
        ai_description = Adw.PreferencesGroup(
            title=_("AI Description"),
            description=_("The description the AI model will use to understand what the action does.")
        )
        ai_description.add(
            Adw.Bin(
                child=Gtk.Label(label=self.tool.get('description'), wrap=True, halign=1),
                css_classes=["card", "p10"]
            )
        )
        action_page.add(ai_description)
        arguments = Adw.PreferencesGroup(
            title=_("Arguments"),
            description=_("Variables that are filled by the AI.")
        )
        for name, data in self.tool.get('parameters', {}).get('properties', {}).items():
            arguments.add(
                Adw.ActionRow(
                    title=name.replace('_', ' ').title(),
                    subtitle=data.get('description')
                )
            )
        action_page.add(arguments)

        if len(list(self.variables)) > 0:
            variables = Adw.PreferencesGroup(
                title=_("Variables"),
                description=_("User filled values that the action uses to work, the AI does not have access to these variables at all.")
            )
            for name, data in self.variables.items():
                if data.get('type', 'string') == 'string':
                    variables.add(
                        Adw.EntryRow(
                            name=name,
                            title=name.replace('_', ' ').title(),
                            text=data.get('value', '')
                        )
                    )
                elif data.get('type') in ('int', 'float'):
                    row = Adw.SpinRow.new_with_range(min=data.get('min', 0), max=data.get('max', 100), step=data.get('step', 1 if data.get('type') == 'int' else 0.1))
                    row.set_digits(0 if data.get('type') == 'int' else 2)
                    row.set_value(float(data.get('value', data.get('min', 0) ) ) )
                    row.set_name(name)
                    row.set_title(name.replace('_', ' ').title())
                    variables.add(row)
                elif data.get('type') == 'secret':
                    variables.add(
                        Adw.PasswordEntryRow(
                            name=name,
                            title=name.replace('_', ' ').title(),
                            text=data.get('value', '')
                        )
                    )
                elif data.get('type') == 'bool':
                    variables.add(
                        Adw.SwitchRow(
                            name=name,
                            title=name.replace('_', ' ').title(),
                            active=bool(data.get('value', False))
                        )
                    )
            action_page.add(variables)

            button_container = Gtk.Box(orientation=0, spacing=10, halign=3)

            cancel_button = Gtk.Button(label=_("Cancel"), css_classes=['pill'])
            cancel_button.connect('clicked', lambda *_: window.main_navigation_view.pop())
            button_container.append(cancel_button)

            accept_button = Gtk.Button(label=_("Accept"), css_classes=['pill', 'suggested-action'])
            accept_button.connect('clicked', lambda *_: self.save_variables(variables))
            button_container.append(accept_button)

            button_group = Adw.PreferencesGroup()
            button_group.add(button_container)
            action_page.add(button_group)

        page_widget = Adw.ToolbarView()
        page_widget.add_top_bar(Adw.HeaderBar())
        page_widget.set_content(action_page)
        window.main_navigation_view.push(Adw.NavigationPage.new(child=page_widget, title=self.name))

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
        action_element = ac(actions_parameters.get(ac.name, {}).get('variables', {}))
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
