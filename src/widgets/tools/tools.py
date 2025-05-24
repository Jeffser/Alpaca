# tools.py

from gi.repository import Adw, Gtk

import datetime, time, random, requests, json, os
from html2text import html2text

from gi.repository import Adw

from .. import terminal, attachments
from ...constants import data_dir
from ...sql_manager import generate_uuid, Instance as SQL

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
        info_button.connect('clicked', lambda *_: self.show_tool_page())
        self.add_prefix(info_button)
        self.enable_switch = Gtk.Switch(active=enabled, valign=3)
        self.enable_switch.connect('state-set', lambda *_: self.enabled_changed())
        self.add_suffix(self.enable_switch)

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

    def save_variables(self, variables_group):
        for v in list(list(list(variables_group)[0])[1])[0]:
            if v.get_name() in list(self.variables.keys()):
                if isinstance(v, Adw.EntryRow) or isinstance(v, Adw.PasswordEntryRow):
                    self.variables[v.get_name()]['value'] = v.get_text()
                elif isinstance(v, Adw.SpinRow):
                    self.variables[v.get_name()]['value'] = v.get_value()
                elif isinstance(v, Adw.SwitchRow):
                    self.variables[v.get_name()]['value'] = v.get_active()

        SQL.insert_or_update_tool_parameters(self.name, self.extract_variables_for_sql(), self.is_enabled())
        window.main_navigation_view.pop()

    def show_tool_page(self):
        tool_page = Adw.PreferencesPage()
        ai_description = Adw.PreferencesGroup(
            title=_("AI Description"),
            description=_("The description the AI model will use to understand what the tool does.")
        )
        ai_description.add(
            Adw.Bin(
                child=Gtk.Label(label=self.tool_metadata.get('description'), wrap=True, halign=1),
                css_classes=["card", "p10"]
            )
        )
        tool_page.add(ai_description)
        if len(list(self.tool_metadata.get('parameters'))) > 0:
            arguments = Adw.PreferencesGroup(
                title=_("Arguments"),
                description=_("Variables that are filled by the AI.")
            )
            for name, data in self.tool_metadata.get('parameters', {}).get('properties', {}).items():
                arguments.add(
                    Adw.ActionRow(
                        title=name.replace('_', ' ').title(),
                        subtitle=data.get('description')
                    )
                )
            tool_page.add(arguments)

        if len(list(self.variables)) > 0:
            variables = Adw.PreferencesGroup(
                title=_("Variables"),
                description=_("User filled values that the tool uses to work, the AI does not have access to these variables at all.")
            )
            for name, data in self.variables.items():
                if data.get('type', 'string') == 'string':
                    variables.add(
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
                    variables.add(row)
                elif data.get('type') == 'secret':
                    variables.add(
                        Adw.PasswordEntryRow(
                            name=name,
                            title=data.get('display_name'),
                            text=data.get('value', '')
                        )
                    )
                elif data.get('type') == 'bool':
                    variables.add(
                        Adw.SwitchRow(
                            name=name,
                            title=data.get('display_name'),
                            active=bool(data.get('value', False))
                        )
                    )
            tool_page.add(variables)

            button_container = Gtk.Box(orientation=0, spacing=10, halign=3)

            cancel_button = Gtk.Button(label=_("Cancel"), css_classes=['pill'])
            cancel_button.connect('clicked', lambda *_: window.main_navigation_view.pop())
            button_container.append(cancel_button)

            accept_button = Gtk.Button(label=_("Accept"), css_classes=['pill', 'suggested-action'])
            accept_button.connect('clicked', lambda *_: self.save_variables(variables))
            button_container.append(accept_button)

            button_group = Adw.PreferencesGroup()
            button_group.add(button_container)
            tool_page.add(button_group)

        page_widget = Adw.ToolbarView()
        page_widget.add_top_bar(Adw.HeaderBar())
        page_widget.set_content(tool_page)
        window.main_navigation_view.push(Adw.NavigationPage.new(child=page_widget, title=self.name))

    def attach_online_image(self, bot_message, image_title:str, image_url:str):
        attachment = bot_message.add_attachment(
            file_id = generate_uuid(),
            name = image_title,
            attachment_type = 'image',
            content = attachments.extract_online_image(image_url, 640)
        )
        SQL.add_attachment(bot_message, attachment)

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
        },
        "strict": True
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
        },
        "strict": True
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
                        SQL.add_attachment(bot_message, attachment)
                    if meal.get("strSource"):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = _("Source"),
                            attachment_type = "link",
                            content = meal.get("strSource")
                        )
                        SQL.add_attachment(bot_message, attachment)
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
        },
        "strict": True
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

                        SQL.add_attachment(bot_message, attachment)
                    if meal.get("strSource"):
                        attachment = bot_message.add_attachment(
                            file_id = generate_uuid(),
                            name = _("Source"),
                            attachment_type = "link",
                            content = meal.get("strSource")
                        )

                        SQL.add_attachment(bot_message, attachment)
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
        },
        "strict": True
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
        },
        "strict": True
    }
    name = _("Online Search")
    description = _("Search for a term online using DuckDuckGo")
    variables = {}

    def run(self, arguments, messages, bot_message) -> str:
        search_term = arguments.get("search_term")
        if not search_term:
            return "Error: Search term was not provided"

        response = requests.get('https://api.duckduckgo.com/?q={}&format=json'.format(search_term.replace(' ', '+')))
        data = response.json()

        result_md = [
            "# {}".format(data.get('Heading', 'Abstract'))
        ]

        if data.get("AbstractURL"):
            attachment = bot_message.add_attachment(
                file_id = generate_uuid(),
                name = data.get("AbstractSource", _("Abstract Source")),
                attachment_type = "link",
                content = data.get("AbstractURL")
            )
            SQL.add_attachment(bot_message, attachment)

        if data.get("AbstractText"):
            result_md.append(data.get("AbstractText"))

        if data.get("Image"):
            self.attach_online_image(bot_message, data.get("Heading", "Web Result Image"), "https://duckduckgo.com{}".format(data.get("Image")))

        if data.get("Infobox") and len(data.get("Infobox", {}).get("content")) > 0:
            info_block = ""
            for info in data.get("Infobox").get("content"):
                if info.get("data_type") == "string" and info.get("label") and info.get("value"):
                    info_block += "- **{}**: {}\n".format(info.get("label"), info.get("value"))
            if len(info_block) > 0:
                result_md.append("## General Information")
                result_md.append(info_block)

        if data.get("OfficialWebsite"):
            attachment = bot_message.add_attachment(
                file_id = generate_uuid(),
                name = _("Official Website"),
                attachment_type = "link",
                content = data.get("OfficialWebsite")
            )
            SQL.add_attachment(bot_message, attachment)

        if len(result_md) == 1 and len(data.get("RelatedTopics", [])) > 0:
            result_md.append("No direct results were found but there are some related topics.")
            result_md.append("## Related Topics")
            result_md.append("### Main Results")
            for topic in data.get("RelatedTopics"):
                if topic.get("FirstURL"):
                    title = topic.get("FirstURL").split("/")[-1].replace("_", " ").title()
                    result_md.append("#### {}".format(title))
                    result_md.append(topic.get("Text"))
                elif topic.get("Name"):
                    result_md.append("### {}".format(topic.get("Name")))
                    for topic2 in topic.get("Topics"):
                        title = topic2.get("FirstURL").split("/")[-1].replace("_", " ").title()
                        result_md.append("#### {}".format(title))
                        result_md.append(topic2.get("Text"))

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
        },
        "strict": True
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
