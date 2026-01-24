# character_page.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import time
from ..message import ScrollableTextView
from .. import dialog
from ...constants import EMPTY_CHARA_CARD
from ...sql_manager import Instance as SQL

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/characters/greeting_row.ui')
class CharacterGreetingRow(Adw.ExpanderRow):
    __gtype_name__ = 'AlpacaCharacterGreetingRow'

    text_view = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def remove(self, button):
        self.get_ancestor(Adw.PreferencesGroup).remove(self)

    def get_greeting(self) -> str:
        return self.text_view.get_text()

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/characters/character_book_entry_row.ui')
class CharacterBookEntryRow(Adw.ExpanderRow):
    __gtype_name__ = 'AlpacaCharacterBookEntryRow'

    text_view = Gtk.Template.Child()
    wrap_box = Gtk.Template.Child()
    add_keyword_button = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def edit_name(self, button):
        popover = button.get_ancestor(Gtk.Popover)
        if popover:
            popover.popdown()
        dialog.simple_entry(
            parent=self.get_root(),
            heading=_("Edit Name"),
            body="",
            callback=self.set_title,
            entries={'placeholder': _("Entry Name"), 'text': self.get_title()}
        )

    @Gtk.Template.Callback()
    def remove(self, button):
        self.get_ancestor(Adw.PreferencesGroup).remove(self)

    def add_keyword(self, keyword:str):
        button = Gtk.Button(
            name=keyword,
            child=Adw.ButtonContent(
                label=keyword,
                icon_name="cross-large-symbolic"
            ),
            css_classes=["small_button", "circular"],
            tooltip_text=_("Remove Keyword")
        )
        button.connect('clicked', lambda btn: btn.unparent())
        self.wrap_box.insert_child_after(button, self.add_keyword_button)

    @Gtk.Template.Callback()
    def add_keyword_requested(self, button):
        dialog.simple_entry(
            parent=self.get_root(),
            heading=_("Add Keyword"),
            body="",
            callback=self.add_keyword,
            entries={'placeholder': _("Keyword")}
        )

    def get_entry(self, id_num:int) -> dict:
        keys = [k.get_name() for k in list(self.add_keyword_button.get_parent())[1:]]

        return {
            'keys': keys,
            'content': self.text_view.get_text(),
            'enabled': True,
            'insertion_order': 100,
            'name': self.get_title(),
            'id': id_num
        }

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/characters/character_page.ui')
class CharacterPage(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaCharacterPage'

    enable_character_row = Gtk.Template.Child()

    name_el = Gtk.Template.Child()
    description_el = Gtk.Template.Child()
    first_message_el = Gtk.Template.Child()

    greetings_group = Gtk.Template.Child()
    character_book_group = Gtk.Template.Child()

    def __init__(self, character_dict:dict):
        super().__init__()
        self.character_dict = character_dict
        char_data = self.character_dict.get('data') or {}

        # Fix Scrollbar

        self.character_book_group.get_ancestor(Gtk.ScrolledWindow).set_propagate_natural_width(True)

        # Enable Character

        self.enable_character_row.set_active(char_data.get('extensions', {}).get('com.jeffser.Alpaca', {}).get('enabled', True))

        # Name

        self.name_el.set_text((char_data.get('name') or '').strip())

        # Description

        description_content = [char_data.get('description') or '']
        additional_description_parts = ['system_prompt', 'personality', 'scenario']
        for key in additional_description_parts:
            if char_data.get(key):
                title = key.replace('_', ' ').title()
                description_content.append('# {}\n\n{}'.format(title, char_data.get(key)))
            self.character_dict['data'][key] = ""

        description_content = '\n---\n'.join(description_content)
        self.description_el.set_text((description_content or '').strip())

        # First Message

        self.first_message_el.set_text((char_data.get('first_mes') or '').strip())

        # Greetings

        for greeting in char_data.get('alternate_greetings') or []:
            greeting = greeting.strip()
            if greeting:
                row = CharacterGreetingRow()
                row.text_view.set_text(greeting)
                self.greetings_group.add(row)

        # Character Book Entries

        character_book = char_data.get('character_book') or {}
        for entry in character_book.get('entries') or []:
            name = entry.get('name').strip()
            content = entry.get('content').strip()
            if name and content:
                row = CharacterBookEntryRow()
                row.set_title(name)
                row.text_view.set_text(content)

                for keyword in entry.get('keys') or []:
                    keyword = keyword.strip()
                    if keyword:
                        row.add_keyword(keyword)

                self.character_book_group.add(row)

    def scroll_and_focus(self, scrolled_window, target_widget):
        self.get_ancestor(Adw.Dialog).set_focus(target_widget)
        content = scrolled_window.get_child()
        vadj = scrolled_window.get_vadjustment()
        success, rect = target_widget.compute_bounds(content)
        if success:
            target_y = rect.get_y()
            vadj.set_value(target_y)

    @Gtk.Template.Callback()
    def new_character_book_entry_requested(self, button):
        def create_with_name(name:str):
            row = CharacterBookEntryRow()
            row.set_title(name or _("Entry"))
            self.character_book_group.add(row)
            row.set_expanded(True)
            GLib.idle_add(self.scroll_and_focus, self.character_book_group.get_ancestor(Gtk.ScrolledWindow), row.text_view.text_view)

        dialog.simple_entry(
            parent=self.get_root(),
            heading=_("Create Entry"),
            body="",
            callback=create_with_name,
            entries={'placeholder': _("Entry Name")}
        )

    @Gtk.Template.Callback()
    def new_alternative_greeting_requested(self, button):
        row = CharacterGreetingRow()
        self.greetings_group.add(row)
        row.set_expanded(True)
        GLib.idle_add(self.scroll_and_focus, self.greetings_group.get_ancestor(Gtk.ScrolledWindow), row.text_view.text_view)

    def save(self):
        model_dialog = self.get_ancestor(Adw.Dialog)
        model_id = model_dialog.model.get_name()
        SQL.insert_or_update_model_character(model_id, self.character_dict)

        navigation_view = self.get_ancestor(Adw.NavigationView)
        navigation_view.pop_to_tag('model')

        try:
            # Update 'Use Character' visibility in current chat
            # Might fail when model dialog is invoked by an activity window but it does not matter
            current_chat = self.get_root().get_current_chat()
            GLib.idle_add(current_chat.on_model_change, self.get_root().global_footer.model_selector)
        except:
            pass

    @Gtk.Template.Callback()
    def save_requested(self, button):
        enable_character = self.enable_character_row.get_active()
        name = self.name_el.get_text()

        description = self.description_el.get_text()
        first_message = self.first_message_el.get_text()

        alternative_greetings = []
        alternative_greetings_listbox = list(list(list(self.greetings_group)[0])[1])[0]
        for greeting in list(alternative_greetings_listbox):
            alternative_greetings.append(greeting.get_greeting())

        character_book_entries = []
        character_book_listbox = list(list(list(self.character_book_group)[0])[1])[0]
        for i, entry in enumerate(list(character_book_listbox)):
            character_book_entries.append(entry.get_entry(i))

        modification_date = int(time.time() * 1000)
        creation_date = self.character_dict.get('data', {}).get('creation_date') or modification_date

        self.character_dict = dict(EMPTY_CHARA_CARD).copy()

        self.character_dict['data']['name'] = name
        self.character_dict['data']['description'] = description
        self.character_dict['data']['extensions']['com.jeffser.Alpaca']['enabled'] = enable_character
        self.character_dict['data']['first_mes'] = first_message
        self.character_dict['data']['alternate_greetings'] = alternative_greetings
        self.character_dict['data']['character_book']['entries'] = character_book_entries
        self.character_dict['data']['creation_date'] = creation_date
        self.character_dict['data']['modification_date'] = modification_date
        self.save()

        toast_overlay = self.get_ancestor(Adw.ToastOverlay)
        toast = Adw.Toast(
            title=_("Character Card Saved Successfully")
        )
        toast_overlay.add_toast(toast)

    @Gtk.Template.Callback()
    def clear_requested(self, button):
        def clear():
            self.character_dict = dict(EMPTY_CHARA_CARD).copy()
            self.save()

            toast_overlay = self.get_ancestor(Adw.ToastOverlay)
            toast = Adw.Toast(
                title=_("Character Card Cleared Successfully")
            )
            toast_overlay.add_toast(toast)

        dialog.simple(
            parent=self.get_root(),
            heading=_("Clear Character Card"),
            body=_("Are you sure you want to clear the character card?"),
            callback=clear,
            button_name=_("Clear"),
            button_appearance="destructive"
        )
