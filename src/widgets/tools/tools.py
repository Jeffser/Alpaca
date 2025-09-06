# tools.py

from gi.repository import Adw, Gtk, Gio, Gdk, GLib

import datetime, time, random, requests, json, os, threading, base64, importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from html2text import html2text

from PIL import Image
from io import BytesIO

from .. import activities, attachments, dialog, models, chat, message
from ...constants import data_dir, REMBG_MODELS
from ...sql_manager import generate_uuid, Instance as SQL

class ToolRunDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaToolRunDialog'

    def __init__(self, tool):
        self.tool = tool
        self.main_stack = Gtk.Stack(
            transition_type=1
        )
        pp = Adw.PreferencesPage(valign=3)
        self.main_stack.add_named(pp, 'arguments')
        tool_properties = self.tool.tool_metadata.get('parameters', {}).get('properties', {})
        self.parameter_elements = []
        if len(tool_properties) > 0:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
            factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))

            pg = Adw.PreferencesGroup(
                title=_("Arguments"),
                description=_("Variables that are filled by the AI.")
            )
            pp.add(pg)
            for name, data in self.tool.tool_metadata.get('parameters', {}).get('properties', {}).items():
                if data.get('enum'):
                    combo = Adw.ComboRow(
                        name=name,
                        title=name.replace('_', ' ').title(),
                        factory=factory
                    )
                    string_list = Gtk.StringList()
                    for option in data.get('enum'):
                        string_list.append(option)
                    combo.set_model(string_list)
                    self.parameter_elements.append(combo)
                    pg.add(combo)
                else:
                    entry = Adw.EntryRow(
                        name=name,
                        title=name.replace('_', ' ').title()
                    )
                    self.parameter_elements.append(entry)
                    pg.add(entry)

        pg = Adw.PreferencesGroup()
        pp.add(pg)
        run_button = Gtk.Button(
            label=_('Run Tool'),
            css_classes=['pill', 'suggested-action']
        )
        run_button.connect('clicked', lambda *_: self.run_tool())
        pg.add(run_button)

        temp_chat = chat.Chat()
        self.m_element_bot = message.Message(
            dt=datetime.datetime.now(),
            message_id=generate_uuid(),
            chat=temp_chat,
            mode=1,
            author='Tool Tester'
        )
        self.m_element_bot.block_container.prepare_generating_block()
        self.m_element_bot.block_container.add_css_class('dim-label')
        self.m_element_bot.options_button.set_visible(False)
        self.m_element_bot.image_attachment_container.force_dialog = True
        self.m_element_bot.attachment_container.force_dialog = True
        temp_chat.add_message(self.m_element_bot)
        self.main_stack.add_named(temp_chat, 'chat')

        tbv=Adw.ToolbarView()
        tbv.add_top_bar(Adw.HeaderBar())
        tbv.set_content(self.main_stack)
        super().__init__(
            child=tbv,
            title=self.tool.name,
            content_width=500
        )
        self.connect('closed', lambda *_: self.on_close())
        if len(self.parameter_elements) == 0:
            self.run_tool()

    def on_close(self):
        SQL.delete_message(self.m_element_bot)

    def start(self, arguments):
        gen_request, response = self.tool.run(arguments, [], self.m_element_bot)
        attachment_content = []
        if len(arguments) > 0:
            attachment_content += [
                '## {}'.format(_('Arguments')),
                '| {} | {} |'.format(_('Argument'), _('Value')),
                '| --- | --- |'
            ]
            attachment_content += ['| {} | {} |'.format(k, v) for k, v in arguments.items()]

        attachment_content += [
            '## {}'.format(_('Result')),
            response
        ]

        self.m_element_bot.add_attachment(
            file_id = generate_uuid(),
            name = self.tool.name,
            attachment_type = 'tool',
            content = '\n'.join(attachment_content)
        )
        self.m_element_bot.block_container.clear()
        self.m_element_bot.update_message(_('The tool would have generated a message in a chat.') if gen_request else _('The tool did not request to generate a message.'))
        GLib.idle_add(self.m_element_bot.main_stack.set_visible_child_name, 'content')

    def run_tool(self):
        arguments = {}
        for el in self.parameter_elements:
            if isinstance(el, Adw.ComboRow):
                arguments[el.get_name()] = el.get_selected_item().get_string()
            elif isinstance(el, Adw.EntryRow):
                arguments[el.get_name()] = el.get_text()
        self.main_stack.set_visible_child_name('chat')
        threading.Thread(target=self.start, args=(arguments,)).start()


class ToolPreferencesDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaToolPreferencesDialog'

    def __init__(self, tool):
        self.tool = tool
        pp = Adw.PreferencesPage()
        ai_description = Adw.PreferencesGroup(
            title=_("AI Description"),
            description=_("The description the AI model will use to understand what the tool does.")
        )
        ai_description.add(
            Adw.Bin(
                child=Gtk.Label(label=self.tool.tool_metadata.get('description'), wrap=True, halign=1),
                css_classes=["card", "p10"]
            )
        )
        pp.add(ai_description)

        if len(list(self.tool.tool_metadata.get('parameters'))) > 0:
            arguments = Adw.PreferencesGroup(
                title=_("Arguments"),
                description=_("Variables that are filled by the AI.")
            )
            for name, data in self.tool.tool_metadata.get('parameters', {}).get('properties', {}).items():
                if data.get('enum'):
                    expander_row = Adw.ExpanderRow(
                        title=name.replace('_', ' ').title(),
                        subtitle=data.get('description'),
                        expanded=True
                    )
                    arguments.add(expander_row)
                    for opt in data.get('enum'):
                        expander_row.add_row(Adw.ActionRow(
                            title=opt.replace('_', ' ').title()
                        ))
                else:
                    arguments.add(Adw.ActionRow(
                        title=name.replace('_', ' ').title(),
                        subtitle=data.get('description')
                    ))

            pp.add(arguments)

        if len(list(self.tool.variables)) > 0:
            self.variables = Adw.PreferencesGroup(
                title=_("Variables"),
                description=_("User filled values that the tool uses to work, the AI does not have access to these variables at all.")
            )
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
            factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))
            for name, data in self.tool.variables.items():
                if data.get('type') == 'string':
                    self.variables.add(
                        Adw.EntryRow(
                            name=name,
                            title=data.get('display_name'),
                            text=data.get('value', '')
                        )
                    )
                elif data.get('type') in ('int', 'float'):
                    row = Adw.SpinRow.new_with_range(min=data.get('min', 0), max=data.get('max', 100), step=data.get('step', 1 if data.get('type') == 'int' else 0.1))
                    row.set_digits(0 if data.get('type') == 'int' else 2)
                    row.set_value(float(data.get('value', data.get('min', 0) ) ) )
                    row.set_name(name)
                    row.set_title(data.get('display_name'))
                    self.variables.add(row)
                elif data.get('type') == 'secret':
                    self.variables.add(
                        Adw.PasswordEntryRow(
                            name=name,
                            title=data.get('display_name'),
                            text=data.get('value', '')
                        )
                    )
                elif data.get('type') == 'bool':
                    self.variables.add(
                        Adw.SwitchRow(
                            name=name,
                            title=data.get('display_name'),
                            active=bool(data.get('value', False))
                        )
                    )
                elif data.get('type') == 'options':
                    combo = Adw.ComboRow(
                        name=name,
                        title=data.get('display_name'),
                        factory=factory
                    )
                    string_list = Gtk.StringList()
                    for option in data.get('options'):
                        string_list.append(option)
                    combo.set_model(string_list)
                    combo.set_selected(data.get('value'))
                    self.variables.add(combo)
            pp.add(self.variables)

            cancel_button = Gtk.Button(
                label=_('Cancel'),
                tooltip_text=_('Cancel'),
                css_classes=['raised']
            )
            cancel_button.connect('clicked', lambda button: self.close())

            save_button = Gtk.Button(
                label=_('Save'),
                tooltip_text=_('Save'),
                css_classes=['suggested-action']
            )
            save_button.connect('clicked', lambda button: self.save_variables())

            hb = Adw.HeaderBar(
                show_start_title_buttons=False,
                show_end_title_buttons=False
            )
            hb.pack_start(cancel_button)
            hb.pack_end(save_button)

        else:
            hb = Adw.HeaderBar()

        tbv=Adw.ToolbarView()
        tbv.add_top_bar(hb)
        tbv.set_content(pp)
        super().__init__(
            child=tbv,
            title=self.tool.name,
            content_width=500
        )

    def save_variables(self):
        for v in list(list(list(self.variables)[0])[1])[0]:
            if v.get_name() in list(self.tool.variables.keys()):
                if isinstance(v, Adw.EntryRow) or isinstance(v, Adw.PasswordEntryRow):
                    self.tool.variables[v.get_name()]['value'] = v.get_text()
                elif isinstance(v, Adw.SpinRow):
                    self.tool.variables[v.get_name()]['value'] = v.get_value()
                elif isinstance(v, Adw.SwitchRow):
                    self.tool.variables[v.get_name()]['value'] = v.get_active()
                elif isinstance(v, Adw.ComboRow):
                    self.tool.variables[v.get_name()]['value'] = v.get_selected()

        SQL.insert_or_update_tool_parameters(self.tool.tool_metadata.get('name'), self.tool.extract_variables_for_sql(), self.tool.is_enabled())
        self.close()

class Base(Adw.ActionRow):
    __gtype_name__ = 'AlpacaToolRow'

    variables = {}

    def __init__(self, variables:dict, enabled:bool):
        for name, data in self.variables.items():
            self.variables[name]['value'] = variables.get(name, data.get('value'))

        super().__init__(
            title = self.name,
            subtitle = self.description
        )

        info_button = Gtk.Button(icon_name='info-outline-symbolic', css_classes=['flat'], valign=3)
        info_button.connect('clicked', lambda *_: self.show_dialog())
        self.add_prefix(info_button)

        run_button = Gtk.Button(icon_name='media-playback-start-symbolic', css_classes=['flat'], valign=3)
        run_button.connect('clicked', lambda *_: self.show_run_dialog())
        self.add_prefix(run_button)

        self.enable_switch = Gtk.Switch(active=enabled, valign=3)
        self.enable_switch.connect('state-set', lambda *_: self.enabled_changed())
        self.add_suffix(self.enable_switch)

    def show_dialog(self):
        ToolPreferencesDialog(self).present(self.get_root())

    def show_run_dialog(self):
        ToolRunDialog(self).present(self.get_root())

    def enabled_changed(self):
        SQL.insert_or_update_tool_parameters(self.tool_metadata.get('name'), self.extract_variables_for_sql(), self.is_enabled())

    def is_enabled(self) -> bool:
        return self.enable_switch.get_active()

    def get_tool(self) -> dict:
        return {
            "type": "function",
            "function": self.tool_metadata
        }

    def extract_variables_for_sql(self) -> dict:
        variables_for_sql = {}
        for name, data in self.variables.items():
            variables_for_sql[name] = data.get('value')
        return variables_for_sql

    def attach_online_image(self, bot_message, image_title:str, image_url:str):
        image_data = attachments.extract_online_image(image_url, 640)
        if image_data:
            attachment = bot_message.add_attachment(
                file_id = generate_uuid(),
                name = image_title,
                attachment_type = 'image',
                content = image_data
            )
            SQL.insert_or_update_attachment(bot_message, attachment)

    def get_latest_image(self, messages) -> str:
        messages.reverse()
        for message in messages:
            if len(message.get('images', [])) > 0:
                return message.get('images')[0]
        self.image_requested = 0

        def on_attachment(file:Gio.File, remove_original:bool=False):
            if not file:
                self.image_requested = None
                return
            self.image_requested = attachments.extract_image(file.get_path(), self.get_root().settings.get_value('max-image-size').unpack())

        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = [file_filter],
            callback = on_attachment
        )

        while self.image_requested == 0:
            continue

        return self.image_requested

class GetCurrentDatetime(Base):
    tool_metadata = {
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
        }
    }
    name = _("Get Current Datetime")
    description = _("Gets the current date and/or time.")
    variables = {}

    def run(self, arguments, messages, bot_message) -> tuple:
        formats = {
            "date": "%A, %B %d %Y",
            "time": "%H:%M",
            "date and time": "%A, %B %d %Y, %H:%M"
        }
        type_to_get = arguments.get("type", "date and time")
        format_to_get = formats.get(type_to_get, "%b %d %Y, %H:%M")
        current_datetime = datetime.datetime.now().strftime(format_to_get)
        return True, current_datetime

class GetRecipeByName(Base):
    tool_metadata = {
        "name": "get_recipe_by_name",
        "description": "Gets the recipe of a meal in JSON format by its name",
        "parameters": {
            "type": "object",
            "properties": {
                "meal": {
                    "type": "string",
                    "description": "The name of a meal"
                }
            },
            "required": [
                "meal"
            ]
        }
    }
    name = _("Get Recipe by Name")
    description = _("Gets a recipe by the meal's name")
    variables = {}

    def run(self, arguments, messages, bot_message) -> tuple:
        meal = arguments.get('meal', '').replace('_', ' ').title()
        if meal:
            response = requests.get('https://www.themealdb.com/api/json/v1/1/search.php?s={}'.format(meal))
            if response.status_code == 200:
                meals = response.json().get('meals', [])
                if len(meals) > 0:
                    meal = meals[0]
                    self.attach_online_image(bot_message, meal.get('strMeal', 'Meal'), meal.get('strMealThumb'))
                    if meal.get("strYoutube"):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = _("YouTube Video"),
                            attachment_type = "link",
                            content = meal.get("strYoutube")
                        )
                        SQL.insert_or_update_attachment(bot_message, attachment)
                    if meal.get("strSource"):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = _("Source"),
                            attachment_type = "link",
                            content = meal.get("strSource")
                        )
                        SQL.insert_or_update_attachment(bot_message, attachment)
                    return True, json.dumps(meal, indent=2)
                else:
                    return True, "{'error': '404: Not Found'}"

class GetRecipesByCategory(Base):
    tool_metadata = {
        "name": "get_recipes_by_category",
        "description": "Gets a list of food recipes names filtered by category",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The category of food to filter recipes by",
                    "enum": [
                        "Random", "Beef", "Chicken", "Dessert", "Lamb", "Miscellaneous", "Pasta", "Pork", "Seafood", "Side", "Starter", "Vegan", "Vegetarian", "Breakfast", "Goat"
                    ]
                },
                "mode": {
                    "type": "string",
                    "description": "Whether to get a single meal with it's recipe or a list of recipe names",
                    "enum": [
                        "single recipe", "list of meals"
                    ]
                }
            },
            "required": [
                "category", "mode"
            ]
        }
    }
    name = _("Get Recipes by Category")
    description = _("Gets a list of food recipes by a specified category")
    variables = {}

    def run(self, arguments, messages, bot_message) -> tuple:
        category = arguments.get('category', 'Random')
        if category == 'Random':
            category = random.choice(self.tool_metadata.get('parameters', {}).get('properties', {}).get('category', {}).get('enum', [])[1:])
        response = requests.get('https://www.themealdb.com/api/json/v1/1/filter.php?c={}'.format(category))
        if response.status_code == 200:
            data = []
            for meal in response.json().get("meals", []):
                data.append('- {}'.format(meal.get("strMeal")))

            if arguments.get("mode", "list of meals") == "single recipe":
                response2 = requests.get('https://www.themealdb.com/api/json/v1/1/lookup.php?i={}'.format(random.choice(response.json().get('meals')).get('idMeal')))
                if response2.json().get("meals", [False])[0]:
                    data = response2.json().get("meals")[0]
                    self.attach_online_image(bot_message, data.get('strMeal', 'Meal'), data.get('strMealThumb'))
                    if meal.get("strYoutube"):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = _("YouTube Video"),
                            attachment_type = "link",
                            content = meal.get("strYoutube")
                        )

                        SQL.insert_or_update_attachment(bot_message, attachment)
                    if meal.get("strSource"):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = _("Source"),
                            attachment_type = "link",
                            content = meal.get("strSource")
                        )

                        SQL.insert_or_update_attachment(bot_message, attachment)
            return True, '\n'.join(['**{}: **{}'.format(key, value) for key, value in data.items() if value])

class ExtractWikipedia(Base):
    tool_metadata = {
        "name": "extract_wikipedia",
        "description": "Extract an article from Wikipedia from it's title",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the Wikipedia Article"
                }
            },
            "required": [
                "title"
            ]
        }
    }
    name = _("Extract Wikipedia Article")
    description = _("Extracts an article from Wikipedia by it's title")
    variables = {}

    def run(self, arguments, messages, bot_message) -> tuple:
        article_title = arguments.get("title")
        if not article_title:
            return "Error: Article title was not provided"

        response = requests.get("https://api.wikimedia.org/core/v1/wikipedia/en/search/title?q={}&limit=1".format(article_title))
        data = response.json()

        result_md = []

        if len(data.get("pages", [])) > 0:
            page = requests.get("https://api.wikimedia.org/core/v1/wikipedia/en/page/{}/html".format(data.get("pages")[0].get("key")))
            result_md.append("# {}".format(data.get("pages")[0].get("key")))
            result_md.append(html2text(page.text))

        else:
            return True, "Error: No results found"

        return True, '\n\n'.join(result_md)

class WebSearch(Base):
    tool_metadata = {
        "name": "web_search",
        "description": "Search for a term online using built-in web browser returning results",
        "parameters": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "The term to search online, be punctual and use the least possible amount of words to get general results"
                }
            },
            "required": [
                "search_term"
            ]
        }
    }
    name = _("Web Search")
    description = _("Search for a term online using built-in web browser")
    variables = {
        'auto_choice': {
            'display_name': "Automatically Decide Which Result to Use",
            'value': True,
            'type': 'bool'
        }
    }

    def on_search_finish(self, md_text:str):
        self.result = md_text

    def start_work(self, search_term:str, bot_message):
        page = activities.WebBrowser()
        activities.show_activity(
            page,
            bot_message.get_root(),
            not bot_message.chat.chat_id
        )
        threading.Thread(target=page.automate_search, args=(self.on_search_finish, search_term, self.variables.get('auto_choice').get('value'))).start()

    def run(self, arguments, messages, bot_message) -> tuple:
        self.result = 0 # | 0=loading | "TEXT"=search went ok | None=ohno |
        search_term = arguments.get("search_term").strip()
        if not search_term:
            return False, "Error: Search term was not provided"

        GLib.idle_add(self.start_work, search_term, bot_message)
        while self.result == 0:
            continue

        if self.result:
            return True, self.result
        return False, 'An error occurred'

class RunCommand(Base):
    tool_metadata = {
        "name": "run_command",
        "description": "Request permission to run a command in a terminal returning it's result",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run and it's parameters"
                },
                "explanation": {
                    "type": "string",
                    "description": "Explain in simple words what the command will do to the system, be clear and honest"
                }
            },
            "required": [
                "command",
                "explanation"
            ]
        }
    }
    name = _("Run Command")
    description = _("Request to run a command using SSH to connect to the device")
    variables = {
        'ip': {
            'display_name': _("IP Address"),
            'value': '127.0.0.1',
            'type': 'string'
        },
        'username': {
            'display_name': _("Username"),
            'value': os.getenv('USER'),
            'type': 'string'
        },
        'port': {
            'display_name': _('Network Port'),
            'value': 22,
            'type': 'int',
            'min': 1,
            'max': 65535
        }
    }

    def run(self, arguments, messages, bot_message) -> tuple:
        if os.path.isfile(os.path.join(data_dir, "ssh_output.txt")):
            os.remove(os.path.join(data_dir, "ssh_output.txt"))

        if not arguments.get('command'):
            return True, "Error: No command was provided"

        commands = [
            'echo -e "🦙 {}\n\n- {}\n{}\n\n- {}\n{}\n\n⚠️ {}\n\n"'.format(
                _('Model Requested to Run Command'),
                _('Command'),
                arguments.get('command'),
                _('Explanation'),
                arguments.get('explanation', _('No explanation was provided')),
                _('Make sure you understand what the command does before running it.')
            ),
            "ssh -t -p {} {}@{} -- '{}'".format(
               self.variables.get('port', {}).get('value', 22),
               self.variables.get('username', {}).get('value', os.getenv('USER')),
               self.variables.get('ip', {}).get('value', '127.0.0.1'),
               'clear;' + arguments.get('command').replace("'", "\\'"),
            )
        ]

        self.waiting_terminal = True
        term = activities.Terminal(
            language='ssh',
            code_getter=lambda:';'.join(commands),
            close_callback=lambda: setattr(self, 'waiting_terminal', False)
        )
        GLib.idle_add(activities.show_activity, term, bot_message.get_root(), not bot_message.chat.chat_id)
        term.run()

        while self.waiting_terminal:
            time.sleep(1)

        command_result = term.get_text() or '(No Output)'
        term = None
        return False, '```\n{}\n```'.format(command_result)

class SpotifyController(Base):
    tool_metadata = {
        "name": "spotify_controller",
        "description": "Control the user's music playback and retrieve information about the song playing and it's status",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to be done in Spotify",
                    "enum": ["next", "previous", "get_track"]
                }
            },
            "required": [
                "action"
            ]
        }
    }
    name = _("Spotify Controller")
    description = _("Control your music's playback")
    variables = {
        'client_id': {
            'display_name': "Client ID",
            'value': '',
            'type': 'secret'
        },
        'client_secret': {
            'display_name': "Client Secret",
            'value': '',
            'type': 'secret'
        },
        'refresh_token': {
            'display_name': '',
            'value': '',
            'type': 'hidden'
        }
    }
    access_token = ''
    token_expiration = 0
    login_row = None
    pfp_widget = None

    def refresh_access_token(self):
        self.access_token = ''
        self.token_expiration = 0
        if self.variables.get('refresh_token').get('value'):
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.variables.get('refresh_token').get('value'),
                "client_id": self.variables.get('client_id').get('value'),
                "client_secret": self.variables.get('client_secret').get('value')
            }

            response = requests.post('https://accounts.spotify.com/api/token', data=payload)
            if response.status_code == 200:
                self.access_token = response.json().get('access_token')
                self.token_expiration = int(time.time()) + response.json().get("expires_in", 3600)

    def get_access_token(self):
        if int(time.time()) >= self.token_expiration:
            self.refresh_access_token()
        return self.access_token

    def show_dialog(self):
        self.dialog = ToolPreferencesDialog(self)

        login_button = Gtk.Button(
            icon_name='view-refresh-symbolic',
            valign=3,
            css_classes=['flat'],
            tooltip_text=_('Log Back In')
        )
        login_button.connect('clicked', lambda button: self.login_request())
        self.login_row = Adw.ActionRow(
            title=_('Not logged in')
        )
        self.login_row.add_suffix(login_button)

        self.dialog.variables.add(self.login_row)
        self.dialog.variables.add(Gtk.LinkButton(
            uri='https://github.com/Jeffser/Alpaca/wiki/Tools#spotify-controller',
            label=_('Tutorial'),
            margin_top=10
        ))

        self.dialog.present(self.get_root())
        self.refresh_user()

    def refresh_user(self):
        access_token = self.get_access_token()
        if access_token:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            response = requests.get("https://api.spotify.com/v1/me", headers=headers)
            if response.status_code != 200:
                return

            if self.login_row:
                self.login_row.set_title(response.json().get('display_name'))

                product = response.json().get('product')
                if product:
                    if product == 'premium':
                        self.login_row.set_subtitle('Spotify Premium')
                    else:
                        self.login_row.set_subtitle('Spotify Free')
                else:
                    self.login_row.set_subtitle(_('Spotify User'))

                image_url = response.json().get('images', [{}])[0].get('url')
                if image_url:
                    image_data = base64.b64decode(attachments.extract_online_image(image_url, 64))
                    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
                    if self.pfp_widget:
                        self.pfp_widget.get_parent().remove(self.pfp_widget)
                    self.pfp_widget = Gtk.Picture.new_for_paintable(texture)
                    self.pfp_widget.set_margin_top(5)
                    self.pfp_widget.set_margin_bottom(5)
                    self.pfp_widget.add_css_class('model_pfp')
                    self.login_row.add_prefix(self.pfp_widget)

    def on_login(self, code):
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://127.0.0.1:8888",
            "client_id": self.variables.get('client_id').get('value'),
            "client_secret": self.variables.get('client_secret').get('value')
        }
        response = requests.post("https://accounts.spotify.com/api/token", data=payload)
        if response.status_code != 200:
            logger.error(response.json())
            return

        self.access_token = response.json().get('access_token') # Doesn't save to SQL
        self.variables['refresh_token']['value'] = response.json().get('refresh_token')
        SQL.insert_or_update_tool_parameters(self.tool_metadata.get('name'), self.extract_variables_for_sql(), self.is_enabled())

        self.refresh_user()
        GLib.idle_add(self.dialog.present, self.get_root())

    def make_handler_class(self):
        outer_self = self
        class SpotifyAuthHandler(BaseHTTPRequestHandler):
            def do_GET(server):
                query = urlparse(server.path).query
                params = parse_qs(query)
                if "code" in params:
                    server.send_response(200)
                    server.send_header("Content-type", "text/html")
                    server.end_headers()
                    server.wfile.write(b"<h1>Authentication complete. You can close this window.</h1>")
                    outer_self.on_login(params["code"][0])
                else:
                    server.send_response(400)
                    server.end_headers()
                    server.wfile.write(b"<h1>Error during authentication</h1>")
        return SpotifyAuthHandler

    def login_request(self):
        self.dialog.save_variables()
        if not self.variables.get('client_id').get('value') or not self.variables.get('client_secret').get('value'):
            dialog.simple_error(
                parent=self.get_root(),
                title=_('Login Error'),
                body=_("Couldn't log in to Spotify"),
                error_log=_("Specify a Client ID and Client Secret")
            )
            return
        server = HTTPServer(("127.0.0.1", 8888), self.make_handler_class())
        threading.Thread(target=server.handle_request, daemon=True).start()

        SCOPE="user-read-playback-state user-modify-playback-state user-read-currently-playing"
        auth_url = (
            "https://accounts.spotify.com/authorize"
            f"?client_id={self.variables.get('client_id').get('value')}"
            f"&response_type=code"
            f"&redirect_uri=http://127.0.0.1:8888"
            f"&scope={SCOPE.replace(' ', '%20')}"
        )
        Gio.AppInfo.launch_default_for_uri(auth_url)

    def run(self, arguments, messages, bot_message) -> tuple:
        if not arguments.get('action'):
            return True, 'Error: No action was specified'
        if arguments.get('action') not in self.tool_metadata.get('parameters').get('properties').get('action').get('enum'):
            return True, 'Error: Invalid action'

        access_token = self.get_access_token()
        if not access_token:
            return True, 'Error: Spotify account is not logged in'
        headers = {"Authorization": f"Bearer {access_token}"}

        if arguments.get('action') == 'next':
            response = requests.post("https://api.spotify.com/v1/me/player/next", headers=headers)
            if response.status_code == 204:
                return True, 'Success: Skipped to the next track'
            elif response.status_code == 403:
                return True, response.json().get('error').get('message')
        elif arguments.get('action') == 'previous':
            response = requests.post("https://api.spotify.com/v1/me/player/previous", headers=headers)
            if response.status_code == 204:
                return True, 'Success: Skipped to the previous track'
            elif response.status_code == 403:
                return True, response.json().get('error').get('message')
        elif arguments.get('action') == 'get_track':
            response = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
            if response.status_code == 204 or not response.content:
                return True, 'Nothing is playing'

            if response.status_code == 200:
                data = response.json()
                item = data.get("item")
                if item:
                    if item.get('album').get('images'):
                        self.attach_online_image(bot_message, item.get('album', {}).get('name', _('Album Art')), item.get('album').get('images')[0].get('url'))
                    if item.get('external_urls', {}).get('spotify'):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = item.get("name"),
                            attachment_type = "link",
                            content = item.get('external_urls', {}).get('spotify')
                        )
                        SQL.insert_or_update_attachment(bot_message, attachment)

                    track_information = [
                        f'- Name: {item.get("name")}',
                        f'- Artists: {", ".join([artist["name"] for artist in item.get("artists", [])])}',
                        f'- Album: {item.get("album", {}).get("name")}'
                    ]
                    return True, '\n'.join(track_information)
                return True, 'Nothing is playing'
        return True, 'Error: Could not do action'

if importlib.util.find_spec('rembg'):
    class BackgroundRemover(Base):
        tool_metadata = {
            "name": "background_remover",
            "description": "Removes the background of the image provided by the user",
            "parameters": {}
        }
        name = _("Image Background Remover")
        description = _("Removes the background of the last image sent")
        variables = {
            'model': {
                'display_name': _("Background Remover Model"),
                'value': 0,
                'type': 'options',
                'options': ['{} ({})'.format(m.get('display_name'), m.get('size')) for m in REMBG_MODELS.values()]
            }
        }

        def on_save(self, data:str, bot_message):
            if data:
                attachment = bot_message.add_attachment(
                    file_id=generate_uuid(),
                    name=_('Output'),
                    attachment_type='image',
                    content=data
                )
                SQL.insert_or_update_attachment(bot_message, attachment)
                self.status = 1
            else:
                self.status = 2

        def on_close(self):
            self.status = 2

        def run(self, arguments, messages, bot_message) -> tuple:
            threading.Thread(target=bot_message.update_message, args=(_('Loading Image...') + '\n',)).start()
            image_b64 = self.get_latest_image(messages)
            if image_b64:
                self.status = 0 # 0 waiting, 1 finished, 2 canceled / empty image
                model_index = self.variables.get('model', {}).get('value', 0)
                page = activities.BackgroundRemoverPage(
                    save_func=lambda data, bm=bot_message: self.on_save(data, bm),
                    close_callback=self.on_close
                )
                page.model_dropdown.set_selected(model_index)
                GLib.idle_add(
                    activities.show_activity,
                    page,
                    bot_message.get_root(),
                    not bot_message.chat.chat_id
                )
                page.load_image(image_b64)

                while self.status == 0:
                    continue

                if self.status == 1:
                    return False, "**Model Used: **{}\n**Status: **Background removed successfully!".format(list(REMBG_MODELS)[model_index])
                else:
                    return False, "An error occurred"
            else:
                return False, "Error: User didn't attach an image"
            return False, "Error: Couldn't remove the background"

