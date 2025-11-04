# added.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .common import CategoryPill, get_available_models_data, prompt_existing

logger = logging.getLogger(__name__)
model_selector_model = None

class AddedModelRow(GObject.Object):
    __gtype_name__ = 'AlpacaAddedModelRow'

    name = GObject.Property(type=str)

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.name = model.model_title

    def __str__(self):
        return self.model.model_title

class AddedModelSelector(Gtk.DropDown):
    __gtype_name__ = 'AlpacaAddedModelSelector'

    def __init__(self):
        global model_selector_model
        if not model_selector_model:
            model_selector_model = Gio.ListStore.new(AddedModelRow)
        model_selector_model.connect('notify::n-items', self.n_items_changed)

        super().__init__(
            model=model_selector_model,
            visible=len(model_selector_model) > 0
        )
        list(self)[0].add_css_class('flat')

        self.set_expression(Gtk.PropertyExpression.new(AddedModelRow, None, "name"))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_text(list_item.get_item().name))
        self.set_factory(factory)
        list(list(self)[1].get_child())[1].set_propagate_natural_width(True)

    def n_items_changed(self, model, gparam):
        self.set_enable_search(len(model) > 10)
        self.set_visible(len(model) > 0)

class InfoBox(Gtk.Box):
    __gtype_name__ = 'AlpacaInformationBox'

    def __init__(self, title:str, description:str, single_line_description:bool):
        super().__init__(
            orientation=1,
            spacing=5,
            name=title
        )
        self.append(Gtk.Label(
            label=title,
            css_classes=['subtitle', 'caption', 'dim-label'],
            hexpand=True,
            ellipsize=3,
            tooltip_text=title,
            halign=1
        ))
        if single_line_description:
            self.append(Gtk.Label(
                label=description,
                hexpand=True,
                ellipsize=3,
                tooltip_text=description,
                halign=1
            ))
        else:
            self.append(Gtk.Label(
                label=description,
                hexpand=True,
                wrap=True,
                tooltip_text=description,
                halign=1
            ))

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/added_model_dialog.ui')
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

            attachment_container = attachments.GlobalAttachmentContainer()
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

    def update_profile_picture(self):
        if self.model.image.get_visible():
            self.image.set_from_paintable(self.model.image.get_paintable())
            self.image.set_pixel_size(192)
        else:
            self.image.set_from_icon_name('image-missing-symbolic')
            self.image.set_pixel_size(-1)

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
        window = self.get_root().get_application().get_main_window(present=False)
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

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/model_button.ui')
class AddedModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaModelButton'

    image = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    subtitle_label = Gtk.Template.Child()

    def __init__(self, model_name:str, instance):
        super().__init__()
        self.instance = instance
        self.data = self.instance.get_model_info(model_name)

        self.set_name(model_name)
        self.model_title = prettify_model_name(model_name)
        self.title_label.set_label(self.model_title)

        tag = prettify_model_name(self.get_name(), True)[1]
        family = self.data.get('details', {}).get('family')
        if family and tag:
            self.set_subtitle('{} • {}'.format(prettify_model_name(family), tag))
        elif family:
            self.set_subtitle(prettify_model_name(family))
        elif tag:
            self.set_subtitle(tag)

        self.row = AddedModelRow(self)
        self.update_profile_picture()

    def set_subtitle(self, subtitle:str):
        self.subtitle_label.set_label(subtitle)
        self.subtitle_label.set_visible(subtitle)

    def get_search_string(self) -> str:
        return '{} {} {}'.format(self.get_name(), self.model_title, self.data.get('system', None))

    def get_search_categories(self) -> set:
        available_models_data = get_available_models_data()
        return set([c for c in available_models_data.get(self.get_name().split(':')[0], {}).get('categories', []) if c not in ('small', 'medium', 'big', 'huge')])

    def get_vision(self) -> bool:
        return 'vision' in self.data.get('capabilities', [])

    def update_profile_picture(self):
        b64_data = SQL.get_model_preferences(self.get_name()).get('picture')
        if b64_data:
            image_data = base64.b64decode(b64_data)
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            self.image.set_from_paintable(texture)
        self.image.set_size_request(64, 64)
        self.image.set_pixel_size(64)
        self.image.set_visible(b64_data)
        self.image.set_margin_start(0)
        self.image.set_margin_end(0)

    def prompt_create_child(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, AddedModelDialog):
            dialog.close()
        prompt_existing(self.get_root(), self.instance, self.model_title)

    def remove_model(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, AddedModelDialog):
            dialog.close()

        window = self.get_root().get_application().get_main_window(present=False)

        if self.instance.delete_model(self.get_name()):
            global model_selector_model
            found_models = [i for i, row in enumerate(list(model_selector_model)) if row.model.get_name() == self.get_name()]
            if found_models:
                model_selector_model.remove(found_models[0])

            if len(list(self.get_ancestor(Gtk.FlowBox))) == 1:
                window.local_model_stack.set_visible_child_name('no-models')

            SQL.remove_model_preferences(self.get_name())
            threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures, daemon=True).start()
            self.get_ancestor(Gtk.FlowBox).remove(self.get_parent())

    def prompt_remove_model(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        )

    @Gtk.Template.Callback()
    def on_click(self, button):
        AddedModelDialog(self).present(self.get_root())

    @Gtk.Template.Callback()
    def show_popup(self, *args):
        rect = Gdk.Rectangle()
        if len(args) == 4:
            rect.x, rect.y = args[2], args[3]
        else:
            rect.x, rect.y = args[1], args[2]

        actions = [
            [
                {
                    'label': _('Remove Model'),
                    'callback': self.prompt_remove_model,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        if self.instance.instance_type in ('ollama', 'ollama:managed'):
            actions[0].insert(0, {
                'label': _('Create Child'),
                'callback': self.prompt_create_child,
                'icon': 'list-add-symbolic'
            })

        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

class FallbackModel:
    def get_name(): return None
    def get_vision() -> bool: return False

