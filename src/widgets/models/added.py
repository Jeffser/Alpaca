# added.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf, GObject
import logging, os, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments

logger = logging.getLogger(__name__)

available_models = {}

class CategoryPill(Adw.Bin):
    __gtype_name__ = 'AlpacaCategoryPillNEW'

    metadata = {
        'multilingual': {'name': _('Multilingual'), 'css': ['accent'], 'icon': 'language-symbolic'},
        'code': {'name': _('Code'), 'css': ['accent'], 'icon': 'code-symbolic'},
        'math': {'name': _('Math'), 'css': ['accent'], 'icon': 'accessories-calculator-symbolic'},
        'vision': {'name': _('Vision'), 'css': ['accent'], 'icon': 'eye-open-negative-filled-symbolic'},
        'embedding': {'name': _('Embedding'), 'css': ['error'], 'icon': 'brain-augemnted-symbolic'},
        'tools': {'name': _('Tools'), 'css': ['accent'], 'icon': 'wrench-wide-symbolic'},
        'reasoning': {'name': _('Reasoning'), 'css': ['accent'], 'icon': 'brain-augemnted-symbolic'},
        'small': {'name': _('Small'), 'css': ['success'], 'icon': 'leaf-symbolic'},
        'medium': {'name': _('Medium'), 'css': ['brown'], 'icon': 'sprout-symbolic'},
        'big': {'name': _('Big'), 'css': ['warning'], 'icon': 'tree-circle-symbolic'},
        'huge': {'name': _('Huge'), 'css': ['error'], 'icon': 'weight-symbolic'},
        'language': {'css': [], 'icon': 'language-symbolic'}
    }

    def __init__(self, name_id:str, show_label:bool):
        if 'language:' in name_id:
            self.metadata['language']['name'] = name_id.split(':')[1]
            name_id = 'language'
        button_content = Gtk.Box(
            spacing=5,
            halign=3
        )
        button_content.append(Gtk.Image.new_from_icon_name(self.metadata.get(name_id, {}).get('icon', 'language-symbolic')))
        if show_label:
            button_content.append(Gtk.Label(
                label='<span weight="bold">{}</span>'.format(self.metadata.get(name_id, {}).get('name')),
                use_markup=True
            ))
        super().__init__(
            css_classes=['subtitle', 'category_pill'] + self.metadata.get(name_id, {}).get('css', []) + ([] if show_label else ['circle']),
            tooltip_text=self.metadata.get(name_id, {}).get('name'),
            child=button_content,
            halign=0 if show_label else 1,
            focusable=False,
            hexpand=True
        )

class InfoBox(Gtk.Box):
    __gtype_name__ = 'AlpacaInformationBoxNEW'

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
            spacing=10,
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
        main_container.append(Gtk.Separator(
            margin_top=5,
            margin_bottom=5,
            margin_start=5,
            margin_end=5
        ))

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
        parent_model = self.model.details.get('details', {}).get('parent_model')
        metadata={
            _('Tag'): prettify_model_name(self.model.get_name(), True)[1],
            _('Family'): prettify_model_name(self.model.details.get('details', {}).get('family')),
            _('Parameter Size'): self.model.details.get('details', {}).get('parameter_size'),
            _('Quantization Level'): self.model.details.get('details', {}).get('quantization_level')
        }
        if parent_model and '/' not in parent_model:
            metadata[_('Parent Model')] = prettify_model_name(parent_model)

        if 'modified_at' in self.model.details:
            metadata[_('Modified At')] = datetime.datetime.strptime(':'.join(self.model.details['modified_at'].split(':')[:2]), '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
        else:
            metadata[_('Modified At')] = None

        for name, value in metadata.items():
            if value:
                information_container.append(InfoBox(name, value, True))
        if self.model.details.get('system'):
            metadata_container.append(InfoBox(_('Context'), self.model.details.get('system'), False))
        if self.model.details.get('description'):
            metadata_container.append(InfoBox(_('Description'), self.model.details.get('description'), False))

        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=5,
            child_spacing=5,
            justify=0,
            halign=1
        )
        metadata_container.append(categories_box)
        categories = available_models.get(self.model.get_name().split(':')[0], {}).get('categories', [])
        languages = available_models.get(self.model.get_name().split(':')[0], {}).get('languages', [])
        if not categories:
            categories = available_models.get(self.model.details.get('details', {}).get('parent_model', '').split(':')[0], {}).get('categories', [])
            languages = available_models.get(self.model.details.get('details', {}).get('parent_model', '').split(':')[0], {}).get('languages', [])
        for category in set(categories):
            if category not in ('small', 'medium', 'big', 'huge'):
                categories_box.append(CategoryPill(category, True))

        main_container.append(metadata_container)

        tbv=Adw.ToolbarView()
        tbv.add_top_bar(Adw.HeaderBar(show_title=False))
        tbv.set_content(Gtk.ScrolledWindow(child=main_container,propagate_natural_height=True, propagate_natural_width=True))
        super().__init__(
            child=tbv,
            title=self.model.model_title,
            width_request=360,
            height_request=240,
            follows_content_size=True
        )

class AddedModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaAddedModelButton'

    def __init__(self, data:dict, instance):
        self.data = data
        self.instance = instance
        self.model_title = prettify_model_name(data.get('name'))
        container = Gtk.Box(
            spacing=5,
            margin_start=5,
            margin_end=5,
            margin_top=5,
            margin_bottom=5
        )

        super().__init__(
            name=data.get('name'),
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
            label=prettify_model_name(data.get('name'), True)[0],
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

        self.dialog = None
        #self.row = LocalModelRow(self)

        self.connect('clicked', lambda btn: self.get_dialog().present(self.get_root()))
        self.update_profile_picture()
        self.details = self.instance.get_model_info(self.get_name())

    def create_profile_picture(self, size:int):
        profile_picture = SQL.get_model_preferences(self.get_name()).get('picture', None)
        print(self.get_name(), bool(profile_picture))
        if profile_picture:
            image_data = base64.b64decode(profile_picture)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image = Gtk.Image.new_from_paintable(texture)
            image.set_size_request(size, size)
            image.set_pixel_size(size)
            return image

    def update_profile_picture(self):
        picture = self.create_profile_picture(64)
        self.image_container.set_visible(picture)
        self.image_container.set_child(picture)

    def change_profile_picture(self):
        def set_profile_picture(file):
            if file:
                picture_b64 = attachments.extract_image(file.get_path(), 480)
                SQL.insert_or_update_model_picture(self.get_name(), picture_b64)
                self.update_profile_picture()
                threading.Thread(target=window.chat_list_box.get_selected_row().update_profile_pictures()).start()

        def remove_profile_picture():
            SQL.insert_or_update_model_picture(self.get_name(), None)
            self.update_profile_picture()
            threading.Thread(target=window.chat_list_box.get_selected_row().update_profile_pictures()).start()

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
        #TODO port so it doesn't use window
        if self.instance.delete_model(self.get_name()):
            found_models = [i for i, row in enumerate(list(window.model_dropdown.get_model())) if row.model.get_name() == self.get_name()]
            if found_models:
                window.model_dropdown.get_model().remove(found_models[0])

            self.get_parent().get_parent().remove(self)
            if len(get_local_models()) == 0:
                window.local_model_stack.set_visible_child_name('no-models')
                window.title_stack.set_visible_child_name('no-models')
            SQL.remove_model_preferences(self.get_name())
            threading.Thread(target=window.chat_list_box.get_selected_row().update_profile_pictures()).start()

    def get_dialog(self):
        if not self.dialog:
            self.dialog = AddedModelDialog(self)
        return self.dialog
