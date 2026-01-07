# added.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, format_datetime, Instance as SQL
from .. import dialog, attachments
from .common import CategoryPill, get_available_models_data, InfoBox

logger = logging.getLogger(__name__)
model_selector_model = None

class AddedModelRow(GObject.Object):
    __gtype_name__ = 'AlpacaAddedModelRow'

    name = GObject.Property(type=str)

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.name = prettify_model_name(self.model.get_name())

    def __str__(self):
        return prettify_model_name(self.model.get_name())

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/character_page.ui')
class CharacterPage(Adw.PreferencesPage):
    __gtype_name__ = 'AlpacaCharacterPage'

    name_row = Gtk.Template.Child()
    creator_row = Gtk.Template.Child()
    character_version_row = Gtk.Template.Child()
    creation_date_row = Gtk.Template.Child()
    modification_date_row = Gtk.Template.Child()
    creator_notes_row = Gtk.Template.Child()

    tag_container = Gtk.Template.Child()

    description_row = Gtk.Template.Child()
    system_prompt_row = Gtk.Template.Child()
    personality_row = Gtk.Template.Child()
    scenario_row = Gtk.Template.Child()
    first_message_row = Gtk.Template.Child()

    character_book_group = Gtk.Template.Child()

    def set_simple_value(self, row:Gtk.Widget, value:str):
        value = GLib.markup_escape_text(value).strip()
        row.set_subtitle(str(value))
        row.set_visible(bool(value))
        pg = row.get_ancestor(Adw.PreferencesGroup)
        if pg and not pg.get_visible():
            pg.set_visible(row.get_visible())

        er = row.get_ancestor(Adw.ExpanderRow)
        if er and not er.get_visible():
            er.set_visible(row.get_visible())

    def add_tags(self, container:Gtk.Widget, tag_names:list):
        for tag_name in tag_names:
            category_pill = CategoryPill(tag_name, True)
            category_pill.image.set_visible(False)
            container.append(category_pill)
        pg = container.get_ancestor(Adw.PreferencesGroup)
        if pg and not pg.get_visible():
            pg.set_visible(len(tag_names) > 0)

        er = container.get_ancestor(Adw.ExpanderRow)
        if er and not er.get_visible():
            er.set_visible(len(tag_names) > 0)

    def __init__(self, chara_dict:dict):
        super().__init__()
        self.chara_data = chara_dict.get('data', {})

        # rows that just set their subtitles
        SIMPLE_ROWS = (
            self.name_row, self.creator_row, self.character_version_row,
            self.creation_date_row, self.modification_date_row, self.creator_notes_row,
            self.description_row, self.system_prompt_row, self.personality_row,
            self.scenario_row, self.first_message_row
        )
        for row in SIMPLE_ROWS:
            value = self.chara_data.get(row.get_name())
            if isinstance(value, int) and 'date' in row.get_name():
                value = format_datetime(datetime.datetime.fromtimestamp(value / 1000.0))
            self.set_simple_value(row, value)

        # Tags
        self.add_tags(self.tag_container, self.chara_data.get('tags', []))

        # Character Book
        character_book = self.chara_data.get('character_book', {})
        if len(character_book.get('entries', [])) > 0:
            self.character_book_group.set_title(character_book.get('name', ''))
            self.character_book_group.set_description(character_book.get('description', ''))

            for entry in character_book.get('entries', []):
                if entry.get('name') and entry.get('enabled'):
                    er = Adw.ExpanderRow(
                        title = entry.get('name').title(),
                        visible = False
                    )
                    self.character_book_group.add(er)

                    key_container = Adw.WrapBox(
                        hexpand = True,
                        line_spacing = 6,
                        child_spacing = 6,
                        justify = 0,
                        halign = 1,
                        css_classes = ['p10']
                    )
                    er.add_row(key_container)
                    self.add_tags(key_container, entry.get('keys', []))

                    content_row = Adw.ActionRow()
                    er.add_row(content_row)
                    self.set_simple_value(content_row, entry.get('content'))


@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/added_selector.ui')
class AddedModelSelector(Gtk.Stack):
    __gtype_name__ = 'AlpacaAddedModelSelector'

    selector = Gtk.Template.Child()

    def __init__(self):
        global model_selector_model
        if not model_selector_model:
            model_selector_model = Gio.ListStore.new(AddedModelRow)
        model_selector_model.connect('notify::n-items', self.n_items_changed)

        super().__init__()

        self.selector.set_model(model_selector_model)
        list(self.selector)[0].add_css_class('flat')
        self.selector.set_expression(Gtk.PropertyExpression.new(AddedModelRow, None, "name"))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.selector.set_factory(factory)
        list(list(self.selector)[1].get_child())[1].set_propagate_natural_width(True)
        GLib.idle_add(self.n_items_changed, self.selector.get_model())

    def get_model(self):
        return self.selector.get_model()

    def n_items_changed(self, model, gparam=None):
        self.selector.set_enable_search(len(model) > 10)
        self.set_visible_child_name('selector' if len(model) > 0 else 'no-models')

    def set_selected(self, index:int):
        self.selector.set_selected(index)

    def get_selected_item(self):
        return self.selector.get_selected_item()

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/added_dialog.ui')
class AddedModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaAddedModelDialog'

    create_child_button = Gtk.Template.Child()
    language_button = Gtk.Template.Child()
    language_flowbox = Gtk.Template.Child()
    image = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    preferences_group = Gtk.Template.Child()
    voice_combo = Gtk.Template.Child()
    metadata_container = Gtk.Template.Child()
    information_container = Gtk.Template.Child()
    description_container = Gtk.Template.Child()
    context_attachment_container = Gtk.Template.Child()
    context_system_container = Gtk.Template.Child()
    categories_container = Gtk.Template.Child()
    character_page_container = Gtk.Template.Child()
    view_stack = Gtk.Template.Child()
    view_switcher = Gtk.Template.Child()

    def __init__(self, model):
        super().__init__()
        self.model = model

        self.create_child_button.set_visible(self.model.instance.instance_type in ('ollama', 'ollama:managed'))

        self.update_profile_picture()

        self.title_label.set_label(prettify_model_name(self.model.get_name(), True)[0])

        self.preferences_group.set_visible(importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'))

        selected_voice = SQL.get_model_preferences(self.model.get_name()).get('voice', None)
        selected_index = 0
        for i, (name, value) in enumerate(TTS_VOICES.items()):
            if value == selected_voice:
                selected_index = i + 1
            self.voice_combo.get_model().append(name)
        self.voice_combo.set_selected(selected_index)

        parent_model = self.model.data.get('details', {}).get('parent_model')
        metadata={
            _('Tag'): prettify_model_name(self.model.get_name(), True)[1],
            _('Family'): prettify_model_name(self.model.data.get('details', {}).get('family')),
            _('Parameter Size'): self.model.data.get('details', {}).get('parameter_size'),
            _('Quantization Level'): self.model.data.get('details', {}).get('quantization_level')
        }
        if parent_model and '/' not in parent_model:
            metadata[_('Parent Model')] = prettify_model_name(parent_model)

        if 'modified_at' in self.model.data:
            metadata[_('Modified At')] = datetime.datetime.strptime(':'.join(self.model.data['modified_at'].split(':')[:2]), '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
        else:
            metadata[_('Modified At')] = None

        for name, value in metadata.items():
            if value:
                self.information_container.append(InfoBox(name, value, True))

        if self.model.data.get('description'):
            self.description_container.set_child(InfoBox(_('Description'), self.model.data.get('description'), False))

        if self.model.data.get('system'):
            system = self.model.data.get('system')

            attachment_container = attachments.AttachmentContainer()
            self.context_attachment_container.set_child(attachment_container)

            pattern = re.compile(r"```(.+?)\n(.*?)```", re.DOTALL)
            matches = pattern.finditer(system)
            for match in matches:
                attachment = attachments.Attachment(
                    file_id='-1',
                    file_name=match.group(1).strip(),
                    file_type='model_context',
                    file_content=match.group(2).strip()
                )
                attachment_container.add_attachment(attachment)

            self.context_attachment_container.get_parent().set_visible(len(list(attachment_container.container)) > 0)

            system = pattern.sub('', system).strip()
            self.context_system_container.set_child(InfoBox(_('Context'), system, False))

        available_models_data = get_available_models_data()
        categories = available_models_data.get(self.model.get_name().split(':')[0], {}).get('categories', [])
        languages = available_models_data.get(self.model.get_name().split(':')[0], {}).get('languages', [])
        if not categories:
            categories = available_models_data.get(self.model.data.get('details', {}).get('parent_model', '').split(':')[0], {}).get('categories', [])
            languages = available_models_data.get(self.model.data.get('details', {}).get('parent_model', '').split(':')[0], {}).get('languages', [])
        for category in set(categories):
            if category not in ('small', 'medium', 'big', 'huge'):
                self.categories_container.append(CategoryPill(category, True))

        for language in ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in languages]:
            self.language_flowbox.append(CategoryPill(language, True))
        self.language_button.set_visible(len(languages) > 1)

    def check_for_character(self):
        self.view_switcher.set_reveal(len(self.model.character_data.keys()) > 0)
        self.view_stack.set_visible_child_name('model')
        if len(self.model.character_data.keys()) > 0:
            self.character_page_container.set_child(CharacterPage(self.model.character_data))
        else:
            self.character_page_container.set_child()

    def update_profile_picture(self):
        if self.model.image.get_visible():
            self.image.set_from_paintable(self.model.image.get_paintable())
            self.image.set_pixel_size(192)
        else:
            self.image.set_from_icon_name('image-missing-symbolic')
            self.image.set_pixel_size(-1)
        self.check_for_character()

    @Gtk.Template.Callback()
    def prompt_remove_model(self, button):
        self.model.prompt_remove_model()

    @Gtk.Template.Callback()
    def prompt_create_child(self, button):
        self.model.prompt_create_child()

    @Gtk.Template.Callback()
    def update_voice(self, comborow, gparam):
        if comborow.get_selected() == 0:
            SQL.insert_or_update_model_voice(self.model.get_name(), None)
        else:
            voice = TTS_VOICES.get(comborow.get_selected_item().get_string())
            SQL.insert_or_update_model_voice(self.model.get_name(), voice)

    @Gtk.Template.Callback()
    def pfp_clicked(self, button):
        window = self.get_root().get_application().get_main_window()
        def set_profile_picture(file):
            if file:
                picture_b64 = attachments.extract_image(file.get_path(), 480)
                SQL.insert_or_update_model_picture(self.model.get_name(), picture_b64)
                self.model.update_profile_picture()
                self.update_profile_picture()
                threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures, daemon=True).start()

        def remove_profile_picture():
            SQL.insert_or_update_model_picture(self.model.get_name(), None)
            self.model.update_profile_picture()
            self.update_profile_picture()
            threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures, daemon=True).start()

        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        if self.model.image.get_visible():
            options = {
                _('Cancel'): {},
                _('Remove'): {'callback': remove_profile_picture, 'appearance': 'destructive'},
                _('Change'): {'callback': lambda: dialog.simple_file(
                    parent = self.get_root(),
                    file_filters = [file_filter],
                    callback = set_profile_picture
                ), 'appearance': 'suggested', 'default': True},
            }

            dialog.Options(
                heading = _("Model Profile Picture"),
                body = _("What do you want to do with the model's profile picture?"),
                close_response = list(options.keys())[0],
                options = options
            ).show(self.get_root())
        else:
            dialog.simple_file(
                parent = self.get_root(),
                file_filters = [file_filter],
                callback = set_profile_picture
            )

class FallbackModel:
    def get_name(): return None
    def get_vision() -> bool: return False

def append_to_model_selector(row):
    global model_selector_model
    model_selector_model.append(row)

def delete_from_model_selector(model_name:str):
    global model_selector_model
    found_models = [i for i, row in enumerate(list(model_selector_model)) if row.model.get_name() == model_name]
    if found_models:
        model_selector_model.remove(found_models[0])

def empty_model_selector():
    global model_selector_model
    model_selector_model.remove_all()

def list_from_selector() -> dict:
    global model_selector_model
    return {m.model.get_name(): m.model for m in list(model_selector_model)}

def get_model():
    global model_selector_model
    return model_selector_model
