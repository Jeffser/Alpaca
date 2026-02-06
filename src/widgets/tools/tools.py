# tools.py

from gi.repository import GObject, GLib, Gio, Gtk
from .. import activities, dialog, attachments, chat
from ...sql_manager import Instance as SQL, generate_uuid
import os, threading

class Property:
    def __init__(self, name:str, description:str, var_type:str, required:bool=False):
        self.name = name
        self.description = description
        self.var_type = var_type
        self.required = required

class Base(GObject.Object):
    display_name:str = ''
    icon_name:str = 'wrench-wide-symbolic'

    name:str = ''
    description:str = ''
    properties:list = []

    runnable:bool = True
    enabled_by_default:bool = True
    required_libraries:list = []

    def get_metadata(self) -> dict:
        properties = {}
        required_properties = []
        for p in self.properties:
            properties[p.name] = {
                'type': p.var_type,
                'description': p.description
            }
            if p.required and p.name not in required_properties:
                required_properties.append(p.name)

        metadata = {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': {
                    'type': 'object',
                    'properties': properties,
                    'required': required_properties
                }
            }
        }

        return metadata

    def __str__(self) -> str:
        return self.display_name

class NoTool(Base):
    display_name:str = _('No Tool')
    icon_name:str = 'cross-large-symbolic'
    name:str = 'no_tool'
    runnable:bool = False

class AutoTool(Base):
    display_name:str = _('Auto Detect Tool')
    name:str = 'auto_tool'
    runnable:bool = False

class WebSearch(Base):
    display_name:str = _('Web Search')
    icon_name:str = 'globe-symbolic'

    name:str = 'web_search'
    description:str = 'Search for a term online using built-in web browser returning results'
    properties:list = [
        Property(
            name='search_term',
            description='The term to search online, be punctual and use the least possible amount of words to get general results',
            var_type='string',
            required=True
        )
    ]

    def on_search_finish(self, md_text:str):
        self.result = md_text

    def start_work(self, search_term:str, bot_message):
        page = activities.WebBrowser()
        chat_element = bot_message.get_ancestor(chat.Chat)
        activities.show_activity(
            page,
            bot_message.get_root(),
            not chat_element or not chat_element.chat_id
        )
        threading.Thread(target=page.automate_search, args=(self.on_search_finish, search_term, True), daemon=True).start()

    def run(self, arguments, messages, bot_message) -> tuple:
        self.result = 0 # 0=loading | "TEXT"=ok | None=error |
        search_term = arguments.get("search_term").strip()
        if not search_term:
            return "I could not find any results", "Error: Search term was not provided"

        GLib.idle_add(self.start_work, search_term, bot_message)
        while self.result == 0:
            continue

        if self.result:
            return None, self.result
        return "I could not find any results", 'An error occurred'

class Terminal(Base):
    display_name:str = _('Terminal')
    icon_name:str = 'terminal-symbolic'

    name:str = 'run_command'
    description:str = 'Request permission to run a command in a terminal returning its result, add sudo if root permission is needed'
    properties:list = [
        Property(
            name='command',
            description='The command to run and its parameters',
            var_type='string',
            required=True
        ),
        Property(
            name='explanation',
            description='Explain in simple words what the command will do to the system, be clear and honest',
            var_type='string',
            required=True
        )
    ]

    required_libraries:list = ['gi.repository.Vte']

    global_page = None
    current_commands = []

    def run(self, arguments, messages, bot_message) -> tuple:
        if not arguments.get('command'):
            return "I could not figure out what you want me to run", "Error: No command was provided"

        self.current_commands = [
            'clear',
            'echo -e "🦙 {}" | fold -s -w "$(tput cols)"'.format(arguments.get('explanation'), _('No explanation was provided')),
            'read -e -i "{}" cmd'.format(arguments.get('command').replace('"', '\\"')),
            'clear',
            'eval "$cmd"'
        ]

        if not self.global_page or not self.global_page.get_root():
            self.global_page = activities.Terminal(
                language='auto',
                code_getter=lambda: ';'.join(self.current_commands),
                close_callback=lambda: setattr(self, 'waiting_terminal', False)
            )
            chat_element = bot_message.get_ancestor(chat.Chat)
            GLib.idle_add(activities.show_activity, self.global_page, bot_message.get_root(), not chat_element or not chat_element.chat_id)

        self.waiting_terminal = True
        self.global_page.run()

        while self.waiting_terminal:
            continue

        return "I ran the command successfully!", '```\n{}\n```'.format(self.global_page.get_text())

class BackgroundRemover(Base):
    display_name:str = _('Background Remover')
    icon_name:str = 'image-missing-symbolic'

    name:str = 'background_remover'
    description:str = 'Requests the user to upload an image and automatically removes its background'

    required_libraries:list = ['rembg']

    def get_latest_image(self, messages, root) -> str:
        messages.reverse()
        for message in messages:
            if len(message.get('images', [])) > 0:
                return message.get('images')[0]
        self.image_requested = 0

        def on_attachment(file:Gio.File, remove_original:bool=False):
            if not file:
                self.image_requested = None
                return
            self.image_requested = attachments.extract_image(file.get_path(), root.settings.get_value('max-image-size').unpack())

        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = root,
            file_filters = [file_filter],
            callback = on_attachment
        )

        while self.image_requested == 0:
            continue

        return self.image_requested

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
        threading.Thread(target=bot_message.update_message, args=(_('Loading Image...') + '\n',), daemon=True).start()
        image_b64 = self.get_latest_image(messages, bot_message.get_root())
        if image_b64:
            self.status = 0 # 0 waiting, 1 finished, 2 canceled / empty image
            page = activities.BackgroundRemover(
                save_func=lambda data, bm=bot_message: self.on_save(data, bm),
                close_callback=self.on_close
            )
            chat_element = bot_message.get_ancestor(chat.Chat)
            GLib.idle_add(
                activities.show_activity,
                page,
                bot_message.get_root(),
                not chat_element or not chat_element.chat_id
            )
            page.load_image(image_b64)

            while self.status == 0:
                continue

            if self.status == 1:
                return "Background removed successfully!", "Successful"
            else:
                return "Sorry, an error occurred", "An error occurred"
        else:
            return "Please provide an image and try again!", "Error: User didn't attach an image"
        return "Sorry, an error occurred", "Error: Couldn't remove the background"
