# tools.py

from gi.repository import Adw, Gtk, Gio, Gdk, GdkPixbuf, GLib

import datetime, time, random, requests, json, os, threading, base64, importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from html2text import html2text

from .. import terminal, attachments, dialog
from ...constants import data_dir
from ...sql_manager import generate_uuid, Instance as SQL

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
                css_classes=["card", "p10", "dim-label"]
            )
        )
        pp.add(ai_description)

        if len(list(self.tool.tool_metadata.get('parameters'))) > 0:
            arguments = Adw.PreferencesGroup(
                title=_("Arguments"),
                description=_("Variables that are filled by the AI.")
            )
            for name, data in self.tool.tool_metadata.get('parameters', {}).get('properties', {}).items():
                arguments.add(
                    Adw.ActionRow(
                        title=name.replace('_', ' ').title(),
                        subtitle=data.get('description')
                    )
                )
            pp.add(arguments)

        if len(list(self.tool.variables)) > 0:
            self.variables = Adw.PreferencesGroup(
                title=_("Variables"),
                description=_("User filled values that the tool uses to work, the AI does not have access to these variables at all.")
            )
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
                        title=data.get('display_name')
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
        self.enable_switch = Gtk.Switch(active=enabled, valign=3)
        self.enable_switch.connect('state-set', lambda *_: self.enabled_changed())
        self.add_suffix(self.enable_switch)

    def show_dialog(self):
        ToolPreferencesDialog(self).present(self.get_root())

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
        attachment = bot_message.add_attachment(
            file_id = generate_uuid(),
            name = image_title,
            attachment_type = 'image',
            content = attachments.extract_online_image(image_url, 640)
        )
        SQL.insert_or_update_attachment(bot_message, attachment)

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

    def run(self, arguments, messages, bot_message) -> str:
        formats = {
            "date": "%A, %B %d %Y",
            "time": "%H:%M %p",
            "date and time": "%A, %B %d %Y, %H:%M %p"
        }
        type_to_get = arguments.get("type", "date and time")
        format_to_get = formats.get(arguments.get("type", "date and time"), "%b %d %Y, %H:%M %p")
        current_datetime = datetime.datetime.now().strftime(format_to_get)
        return current_datetime

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

    def run(self, arguments, messages, bot_message) -> str:
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
                    return json.dumps(meal, indent=2)
                else:
                    return "{'error': '404: Not Found'}"

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

    def run(self, arguments, messages, bot_message) -> str:
        category = arguments.get('category', 'Random')
        if category == 'Random':
            category = random.choice(self.tool_metadata.get('parameters', {}).get('properties', {}).get('category', {}).get('enum', [])[1:])
        response = requests.get('https://www.themealdb.com/api/json/v1/1/filter.php?c={}'.format(category))
        if response.status_code == 200:
            data = []
            for meal in response.json().get("meals", []):
                data.append('- {}'.format(meal.get("strMeal")))

            if arguments.get("mode", "list of meals") == "single recipe":
                response2 = requests.get('www.themealdb.com/api/json/v1/1/lookup.php?i={}'.format(random.choice(data).get('id')))
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
            return '\n'.join(data)

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

    def run(self, arguments, messages, bot_message) -> str:
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
            return "Error: No results found"

        return '\n\n'.join(result_md)

if importlib.util.find_spec('duckduckgo_search'):
    from duckduckgo_search import DDGS
    class OnlineSearch(Base):
        tool_metadata = {
            "name": "online_search",
            "description": "Search for a term online using DuckDuckGo returning results",
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
        name = _("Online Search")
        description = _("Search for a term online using DuckDuckGo")
        variables = {
            'safesearch': {
                'display_name': _("Safe Search"),
                'value': 1,
                'type': 'options',
                'options': [
                    _('On'),
                    _('Moderate'),
                    _('Off')
                ]
            },
            'max_results': {
                'display_name': _("Max Results"),
                'value': 1,
                'type': 'int',
                'min': 1,
                'max': 5
            }
        }

        def run(self, arguments, messages, bot_message) -> str:
            search_term = arguments.get("search_term")
            if not search_term:
                return "Error: Search term was not provided"

            result_md = []

            text_results = DDGS().text(
                keywords=search_term,
                max_results=self.variables.get('max_results', {}).get('value', 1),
                safesearch=('on', 'moderate', 'off')[self.variables.get('safesearch', {}).get('value', 1)]
            )

            for text_result in text_results:
                attachment = bot_message.add_attachment(
                    file_id = generate_uuid(),
                    name = _("Abstract Source"),
                    attachment_type = "link",
                    content = text_result.get('href')
                )
                SQL.insert_or_update_attachment(bot_message, attachment)
                result_md.append('### {}'.format(text_result.get('title')))
                result_md.append(text_result.get('body'))

            images = DDGS().images(
                keywords=search_term,
                max_results=self.variables.get('max_results', {}).get('value', 1),
                safesearch=('on', 'moderate', 'off')[self.variables.get('safesearch', {}).get('value', 1)],
                size='Medium',
                layout='Square'
            )

            for image_result in images:
                self.attach_online_image(bot_message, text_result.get('title', _('Web Result Image')), image_result.get('image'))

            if len(result_md) == 1:
                return "Error: No results found"

            return '\n\n'.join(result_md)

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
    name = _("Run Command (Testing)")
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

    def run(self, arguments, messages, bot_message) -> str:
        if os.path.isfile(os.path.join(data_dir, "ssh_output.txt")):
            os.remove(os.path.join(data_dir, "ssh_output.txt"))

        if not arguments.get('command'):
            return "Error: No command was provided"

        commands = [
            'echo -e "🦙 {}\n\n- {}\n{}\n\n- {}\n{}\n\n⚠️ {}\n\n"'.format(
                _('Model Requested to Run Command'),
                _('Command'),
                arguments.get('command'),
                _('Explanation'),
                arguments.get('explanation', _('No explanation was provided')),
                _('Make sure you understand what the command does before running it.')
            ),
            "ssh -t -p {} {}@{} -- '{}' 2>&1 | tee '{}'".format(
               self.variables.get('port', {}).get('value', 22),
               self.variables.get('username', {}).get('value', os.getenv('USER')),
               self.variables.get('ip', {}).get('value', '127.0.0.1'),
               arguments.get('command').replace("'", "\\'"),
               os.path.join(data_dir, "ssh_output.txt")
            )
        ]

        terminal_dialog = terminal.TerminalDialog()
        terminal_dialog.present(self.get_root())
        terminal_dialog.run(
            code_language='ssh',
            file_content=';'.join(commands)
        )

        while isinstance(self.get_root().get_visible_dialog(), terminal.TerminalDialog):
            time.sleep(1)

        command_result = '(No Output)'
        if os.path.isfile(os.path.join(data_dir, "ssh_output.txt")):
            with open(os.path.join(data_dir, "ssh_output.txt"), 'r') as f:
                command_result = f.read()

        return '```\n{}\n```'.format(command_result)

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
                    loader = GdkPixbuf.PixbufLoader.new()
                    loader.write(image_data)
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
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
        threading.Thread(target=server.handle_request).start()

        SCOPE="user-read-playback-state user-modify-playback-state user-read-currently-playing"
        auth_url = (
            "https://accounts.spotify.com/authorize"
            f"?client_id={self.variables.get('client_id').get('value')}"
            f"&response_type=code"
            f"&redirect_uri=http://127.0.0.1:8888"
            f"&scope={SCOPE.replace(' ', '%20')}"
        )
        Gio.AppInfo.launch_default_for_uri(auth_url)

    def run(self, arguments, messages, bot_message) -> str:
        if not arguments.get('action'):
            return 'Error: No action was specified'
        if arguments.get('action') not in self.tool_metadata.get('parameters').get('properties').get('action').get('enum'):
            return 'Error: Invalid action'

        access_token = self.get_access_token()
        if not access_token:
            return 'Error: Spotify account is not logged in'
        headers = {"Authorization": f"Bearer {access_token}"}

        if arguments.get('action') == 'next':
            response = requests.post("https://api.spotify.com/v1/me/player/next", headers=headers)
            if response.status_code == 204:
                return 'Success: Skipped to the next track'
            elif response.status_code == 403:
                return response.json().get('error').get('message')
        elif arguments.get('action') == 'previous':
            response = requests.post("https://api.spotify.com/v1/me/player/previous", headers=headers)
            if response.status_code == 204:
                return 'Success: Skipped to the previous track'
            elif response.status_code == 403:
                return response.json().get('error').get('message')
        elif arguments.get('action') == 'get_track':
            response = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
            if response.status_code == 204 or not response.content:
                return 'Nothing is playing'

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
                    return '\n'.join(track_information)
                return 'Nothing is playing'
        return 'Error: Could not do action'

