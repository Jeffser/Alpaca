# added.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .common import CategoryPill, get_available_models_data, prompt_existing

logger = logging.getLogger(__name__)

class AddedModelRow(GObject.Object):
    __gtype_name__ = 'AlpacaAddedModelRow'

    name = GObject.Property(type=str)

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.name = model.model_title

    def __str__(self):
        return self.model.model_title

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

class AddedModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaAddedModelDialog'

    def __init__(self, model):
        self.model = model

        main_container = Gtk.Box(
            spacing=10,
            hexpand=True,
            vexpand=True,
            css_classes=['p10'],
            orientation=1
        )

        main_page = Gtk.Box(
            orientation=1,
            spacing=20,
            hexpand=True
        )

        image = self.model.create_profile_picture(192)
        if not image:
            image = Gtk.Image.new_from_icon_name('image-missing-symbolic')
            image.set_icon_size(2)
            image.set_size_request(192, 192)
        self.image_container = Gtk.Button(
            css_classes=['circular'],
            halign=3,
            overflow=1,
            child=image,
            tooltip_text=_('Change Profile Picture')
        )
        main_page.append(self.image_container)
        self.image_container.connect('clicked', lambda *_: self.model.change_profile_picture())
        self.model.image_container.connect('notify::child', lambda *_: self.update_profile_picture())

        title_label = Gtk.Label(
            label=prettify_model_name(self.model.get_name(), True)[0],
            tooltip_text=prettify_model_name(self.model.get_name(), True)[0],
            css_classes=['title-1'],
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        main_page.append(title_label)

        preferences_group = Adw.PreferencesGroup(
            visible=importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice')
        )
        main_page.append(preferences_group)
        self.voice_combo = Adw.ComboRow(
            title=_("Voice")
        )
        selected_voice = SQL.get_model_preferences(self.model.get_name()).get('voice', None)
        selected_index = 0
        string_list = Gtk.StringList()
        string_list.append(_("Default"))
        for i, (name, value) in enumerate(TTS_VOICES.items()):
            if value == selected_voice:
                selected_index = i + 1
            string_list.append(name)
        self.voice_combo.set_model(string_list)
        self.voice_combo.set_selected(selected_index)
        self.voice_combo.connect("notify::selected", lambda *_: self.update_voice())
        preferences_group.add(self.voice_combo)

        main_container.append(main_page)

        metadata_container = Gtk.Box(
            orientation=1,
            spacing=10,
            hexpand=False
        )

        information_container = Gtk.FlowBox(
            selection_mode=0,
            homogeneous=True,
            row_spacing=10,
            max_children_per_line=2
        )
        metadata_container.append(information_container)
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
                information_container.append(InfoBox(name, value, True))
        if self.model.data.get('description'):
            metadata_container.append(InfoBox(_('Description'), self.model.data.get('description'), False))
        if self.model.data.get('system'):
            system = self.model.data.get('system')

            context_attachment_box = Gtk.Box(
                orientation=1,
                spacing=5
            )
            metadata_container.append(context_attachment_box)

            context_attachment_box.append(Gtk.Label(
                label=_('Files'),
                css_classes=['subtitle', 'caption', 'dim-label'],
                hexpand=True,
                ellipsize=3,
                tooltip_text=_('Files'),
                halign=1
            ))

            context_attachment_container = attachments.GlobalAttachmentContainer()
            context_attachment_box.append(context_attachment_container)

            pattern = re.compile(r"```(.+?)\n(.*?)```", re.DOTALL)
            matches = pattern.finditer(system)
            for match in matches:
                attachment = attachments.Attachment(
                    file_id='-1',
                    file_name=match.group(1).strip(),
                    file_type='model_context',
                    file_content=match.group(2).strip()
                )
                context_attachment_container.add_attachment(attachment)

            system = pattern.sub('', system).strip()
            metadata_container.append(InfoBox(_('Context'), system, False))

        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=5,
            child_spacing=5,
            justify=0,
            halign=1
        )
        metadata_container.append(categories_box)
        available_models_data = get_available_models_data()
        categories = available_models_data.get(self.model.get_name().split(':')[0], {}).get('categories', [])
        languages = available_models_data.get(self.model.get_name().split(':')[0], {}).get('languages', [])
        if not categories:
            categories = available_models_data.get(self.model.data.get('details', {}).get('parent_model', '').split(':')[0], {}).get('categories', [])
            languages = available_models_data.get(self.model.data.get('details', {}).get('parent_model', '').split(':')[0], {}).get('languages', [])
        for category in set(categories):
            if category not in ('small', 'medium', 'big', 'huge'):
                categories_box.append(CategoryPill(category, True))

        main_container.append(metadata_container)

        tbv=Adw.ToolbarView()
        header_bar = Adw.HeaderBar(
            show_title=False
        )
        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: self.model.prompt_remove_model())
        header_bar.pack_start(remove_button)

        if 'ollama' in self.model.instance.instance_type:
            create_child_button = Gtk.Button(
                icon_name='list-add-symbolic',
                tooltip_text=_('Create Child')
            )
            create_child_button.connect('clicked', lambda button: self.model.create_child())
            header_bar.pack_start(create_child_button)

        if len(available_models_data.get(self.model.get_name().split(':')[0], {}).get('languages', [])) > 1:
            languages_container = Gtk.FlowBox(
                max_children_per_line=3,
                selection_mode=0
            )
            for language in ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in available_models_data.get(self.model.get_name().split(':')[0], {}).get('languages', [])]:
                languages_container.append(CategoryPill(language, True))
            languages_scroller = Gtk.ScrolledWindow(
                child=languages_container,
                propagate_natural_width=True,
                propagate_natural_height=True
            )

            languages_button = Gtk.MenuButton(
                icon_name='language-symbolic',
                tooltip_text=_('Languages'),
                popover=Gtk.Popover(child=languages_scroller)
            )
            header_bar.pack_start(languages_button)

        tbv.add_top_bar(header_bar)
        tbv.set_content(
            Gtk.ScrolledWindow(
                child=main_container,
                propagate_natural_height=True,
                max_content_width=500
            )
        )
        super().__init__(
            child=tbv,
            title=self.model.model_title,
            width_request=360,
            height_request=240,
            follows_content_size=True,
            default_widget=self.image_container
        )

    def update_profile_picture(self):
        image = self.model.create_profile_picture(192)
        if not image:
            image = Gtk.Image.new_from_icon_name('image-missing-symbolic')
            image.set_size_request(192, 192)
        self.image_container.set_child(image)

    def update_voice(self):
        if self.voice_combo.get_selected() == 0:
            SQL.insert_or_update_model_voice(self.model.get_name(), None)
        else:
            voice = TTS_VOICES.get(self.voice_combo.get_selected_item().get_string())
            SQL.insert_or_update_model_voice(self.model.get_name(), voice)

class AddedModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaAddedModelButton'

    def __init__(self, model_name:str, instance):
        self.instance = instance
        self.data = self.instance.get_model_info(model_name)
        self.model_title = prettify_model_name(model_name)
        container = Gtk.Box(
            spacing=5,
            margin_start=5,
            margin_end=5,
            margin_top=5,
            margin_bottom=5
        )

        super().__init__(
            name=model_name,
            child=container,
            css_classes=['p0', 'card']
        )

        self.image_container = Adw.Bin(
            css_classes=['r10'],
            valign=3,
            halign=3,
            overflow=1,
        )
        container.append(self.image_container)

        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3,
            margin_start=5,
            margin_end=5,
            margin_top=5,
            margin_bottom=5
        )
        container.append(text_container)
        title_label = Gtk.Label(
            label=prettify_model_name(model_name, True)[0],
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        subtitle_label = Gtk.Label(
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1,
            visible=False
        )
        tag = prettify_model_name(self.get_name(), True)[1]
        family = self.data.get('details', {}).get('family')
        if family and tag:
            subtitle_label.set_label('{} • {}'.format(prettify_model_name(family), tag))
        elif family:
            subtitle_label.set_label(prettify_model_name(family))
        elif tag:
            subtitle_label.set_label(tag)
        subtitle_label.set_visible(subtitle_label.get_label())
        text_container.append(subtitle_label)

        self.row = AddedModelRow(self)

        self.connect('clicked', lambda btn: AddedModelDialog(self).present(self.get_root()))
        GLib.idle_add(self.update_profile_picture)

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def get_search_string(self) -> str:
        return '{} {} {}'.format(self.get_name(), self.model_title, self.data.get('system', None))

    def get_search_categories(self) -> set:
        available_models_data = get_available_models_data()
        return set([c for c in available_models_data.get(self.get_name().split(':')[0], {}).get('categories', []) if c not in ('small', 'medium', 'big', 'huge')])

    def get_vision(self) -> bool:
        return 'vision' in self.data.get('capabilities', [])

    def create_profile_picture(self, size:int):
        profile_picture = SQL.get_model_preferences(self.get_name()).get('picture', None)
        if profile_picture:
            image_data = base64.b64decode(profile_picture)
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            image = Gtk.Image.new_from_paintable(texture)
            image.set_size_request(size, size)
            image.set_pixel_size(size)
            return image

    def update_profile_picture(self):
        picture = self.create_profile_picture(64)
        self.image_container.set_visible(picture)
        self.image_container.set_child(picture)

    def change_profile_picture(self):
        window = self.get_root().get_application().main_alpaca_window
        def set_profile_picture(file):
            if file:
                picture_b64 = attachments.extract_image(file.get_path(), 480)
                SQL.insert_or_update_model_picture(self.get_name(), picture_b64)
                self.update_profile_picture()
                threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures()).start()

        def remove_profile_picture():
            SQL.insert_or_update_model_picture(self.get_name(), None)
            self.update_profile_picture()
            threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures()).start()

        if SQL.get_model_preferences(self.get_name()).get('picture', None):
            file_filter = Gtk.FileFilter()
            file_filter.add_pixbuf_formats()

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
            file_filter = Gtk.FileFilter()
            file_filter.add_pixbuf_formats()

            dialog.simple_file(
                parent = self.get_root(),
                file_filters = [file_filter],
                callback = set_profile_picture
            )

    def remove_model(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, AddedModelDialog):
            dialog.close()

        window = self.get_root().get_application().main_alpaca_window

        if self.instance.delete_model(self.get_name()):
            found_models = [i for i, row in enumerate(list(window.model_dropdown.get_model())) if row.model.get_name() == self.get_name()]
            if found_models:
                window.model_dropdown.get_model().remove(found_models[0])

            if len(list(self.get_parent().get_parent())) == 1:
                window.local_model_stack.set_visible_child_name('no-models')
                window.title_stack.set_visible_child_name('no-models')
            self.get_parent().get_parent().remove(self)
            SQL.remove_model_preferences(self.get_name())
            threading.Thread(target=window.chat_bin.get_child().row.update_profile_pictures()).start()

    def prompt_remove_model(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        )

    def create_child(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, AddedModelDialog):
            dialog.close()
        prompt_existing(self.get_root(), self.instance, self.model_title)

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Remove Model'),
                    'callback': self.prompt_remove_model,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        if 'ollama' in self.instance.instance_type:
            actions[0].insert(0, {
                'label': _('Create Child'),
                'callback': self.create_child,
                'icon': 'list-add-symbolic'
            })

        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

class FallbackModel:
    def get_name(): return None
    def get_vision() -> bool: return False

class LiteAddedModel: #For LiveChat and QuickChat

    def __init__(self, name:str, vision:bool):
        self.name = name
        self.vision = vision
        self.model_title = prettify_model_name(self.name)

    def get_name(self) -> str:
        return self.name

    def get_vision(self) -> bool:
        return self.vision
