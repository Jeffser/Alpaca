# model_manager.py
"""
Handles models
"""

import gi
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GdkPixbuf, GObject
import logging, os, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ..constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ..sql_manager import prettify_model_name, Instance as SQL
from . import dialog, attachments

logger = logging.getLogger(__name__)

window = None

available_models = {}
tts_model_path = ""

class LocalModelRow(GObject.Object):
    __gtype_name__ = 'AlpacaLocalModelRow'

    name = GObject.Property(type=str)

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.name = model.model_title

    def __str__(self):
        return self.model.model_title

class TextToSpeechModel(Gtk.Box):
    __gtype_name__ = 'AlpacaTextToSpeechModel'

    def __init__(self, name:str):
        self.model_title = name.title()
        super().__init__(
            spacing=10,
            css_classes=['card', 'model_box'],
            name=name
        )
        self.image_container = Adw.Bin(
            css_classes=['model_pfp'],
            valign=3,
            halign=3,
            overflow=1,
            child=Gtk.Image.new_from_icon_name("bullhorn-symbolic")
        )
        self.append(self.image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        self.append(text_container)
        title_label = Gtk.Label(
            label=self.model_title,
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        self.subtitle_label = Gtk.Label(
            label=_("Text to Speech"),
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(self.subtitle_label)
        self.page = None

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    def get_default_widget(self) -> Gtk.Widget:
        return None

    def remove_model(self):
        global tts_model_path
        name = '{}.pt'.format(TTS_VOICES.get(self.get_name(), ''))
        symlink_path = os.path.join(tts_model_path, name)

        if os.path.islink(symlink_path):
            target_path = os.readlink(symlink_path)
            os.unlink(symlink_path)
            if os.path.isfile(target_path):
                os.remove(target_path)
        window.local_model_flowbox.remove(self)

    def get_page(self):
        buttons = []
        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text="https://github.com/hexgrad/kokoro"
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri("https://github.com/hexgrad/kokoro"))
        buttons.append(web_button)

        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        ))
        buttons.append(remove_button)

        page = Adw.StatusPage(
            icon_name="bullhorn-symbolic",
            title=self.model_title,
            description=_("Local text to speech model provided by Kokoro.")
        )
        return buttons, page

class SpeechToTextModel(Gtk.Box):
    __gtype_name__ = 'AlpacaSpeechToTextModel'

    def __init__(self, name:str):
        self.model_title = name.title()
        super().__init__(
            spacing=10,
            css_classes=['card', 'model_box'],
            name=name
        )
        self.image_container = Adw.Bin(
            css_classes=['model_pfp'],
            valign=3,
            halign=3,
            overflow=1,
            child=Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        )
        self.append(self.image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        self.append(text_container)
        title_label = Gtk.Label(
            label=self.model_title,
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        self.subtitle_label = Gtk.Label(
            label=_("Speech to Text"),
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(self.subtitle_label)
        self.page = None

    def get_search_categories(self) -> set:
        return set()

    def get_search_string(self) -> str:
        return self.get_name()

    def get_default_widget(self) -> Gtk.Widget:
        return None

    def remove_model(self):
        model_path = os.path.join(data_dir, 'whisper', '{}.pt'.format(self.get_name()))
        if os.path.isfile(model_path):
            os.remove(model_path)
        window.local_model_flowbox.remove(self)

    def get_page(self):
        buttons = []
        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text="https://github.com/openai/whisper"
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri("https://github.com/openai/whisper"))
        buttons.append(web_button)

        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model')
        )
        remove_button.connect('clicked', lambda button: dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        ))
        buttons.append(remove_button)

        page = Adw.StatusPage(
            icon_name="audio-input-microphone-symbolic",
            title=self.model_title,
            description=_("Local speech to text model provided by OpenAI Whisper."),
            child=Gtk.Label(label=STT_MODELS.get(self.get_name(), '~151mb'), css_classes=["dim-label"])
        )
        return buttons, page

class PullingModelPage(Gtk.Box):
    __gtype_name__ = 'AlpacaPullingModelPage'

    def __init__(self, model):
        self.model = model
        super().__init__(
            orientation=1,
            spacing=10,
            valign=3,
            css_classes=['p10']
        )
        title_label = Gtk.Label(
            label=prettify_model_name(self.model.get_name()),
            tooltip_text=prettify_model_name(self.model.get_name()),
            css_classes=['title-1'],
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        self.append(title_label)
        self.status_label = Gtk.Label(
            wrap=True,
            wrap_mode=2,
            justify=2,
            label=_("Downloading…")
        )
        self.append(Adw.Bin(css_classes=['card', 'p10'], child=self.status_label))
        self.progressbar = Gtk.ProgressBar(show_text=self.model.cancellable, pulse_step=0.5)
        self.progressbar.pulse()
        self.append(self.progressbar)

        stop_button = Gtk.Button(
            child=Adw.ButtonContent(
                icon_name='media-playback-stop-symbolic',
                label=_('Stop Download')
            ),
            tooltip_text=_('Stop Download'),
            css_classes=['destructive-action'],
            halign=3
        )
        stop_button.connect('clicked', lambda button: dialog.simple(
            parent = self.get_root(),
            heading = _('Stop Download?'),
            body = _("Are you sure you want to stop pulling '{}'?").format(prettify_model_name(self.model.get_name())),
            callback = self.stop_download,
            button_name = _('Stop'),
            button_appearance = 'destructive'
        ))
        if self.model.cancellable:
            self.append(stop_button)

    def stop_download(self):
        window.local_model_flowbox.remove(self.model)
        if len(list(window.local_model_flowbox)) == 0:
            window.local_model_stack.set_visible_child_name('no-models')

class PullingModel(Gtk.Box):
    __gtype_name__ = 'AlpacaPullingModel'

    def __init__(self, name:str, success_callback:callable, cancellable:bool=True):
        self.model_title = prettify_model_name(name)
        super().__init__(
            orientation=1,
            spacing=5,
            css_classes=['card', 'model_box'],
            name=name,
            valign=0
        )
        title_label = Gtk.Label(
            label=prettify_model_name(name, True)[0],
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        self.append(title_label)
        if cancellable:
            subtitle_text = prettify_model_name(name, True)[1]
        else: # Probably STT
            subtitle_text = _("Speech to Text")
        subtitle_label = Gtk.Label(
            label=subtitle_text,
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1,
            visible=prettify_model_name(name, True)[1] or not cancellable
        )
        self.append(subtitle_label)
        self.progressbar = Gtk.ProgressBar(pulse_step=0.5)
        self.progressbar.pulse()
        self.append(self.progressbar)
        self.page = None
        self.digests = []
        self.success_callback = success_callback
        self.cancellable = cancellable

    def get_default_widget(self):
        return self.page

    def get_search_string(self) -> str:
        return '{} {}'.format(self.get_name(), self.model_title)

    def get_search_categories(self) -> set:
        return set([c for c in available_models.get(self.get_name().split(':')[0], {}).get('categories', []) if c not in ('small', 'medium', 'big', 'huge')])

    def update_progressbar(self, data:dict):
        if not self.get_parent():
            logger.info("Pulling of '{}' was canceled".format(self.get_name()))
            if window.get_current_instance().model_directory:
                directory = os.path.join(window.get_current_instance().model_directory, 'blobs')
                for digest in self.digests:
                    files_to_delete = glob.glob(os.path.join(directory, digest + '*'))
                    for file in files_to_delete:
                        logger.info("Deleting '{}'".format(file))
                        try:
                            os.remove(file)
                        except Exception as e:
                            logger.error(f"Can't delete file {file}: {e}")
            sys.exit()
        if 'error' in data:
            self.error = data['error']
            parent = self.get_root()
            self.get_parent().get_parent().remove(self.get_parent())
            logger.error(self.error)
            dialog.simple_error(
                parent = parent,
                title = _('Model Manager Error'),
                body = _("An error occurred whilst pulling '{}'").format(self.get_name()),
                error_log = self.error
            )
        else:

            if 'total' in data and 'completed' in data:
                GLib.idle_add(self.progressbar.set_fraction, data.get('completed', 0) / data.get('total', 0))
                if self.page:
                    GLib.idle_add(self.page.progressbar.set_fraction, data.get('completed', 0) / data.get('total', 0))
            else:
                GLib.idle_add(self.progressbar.pulse)
                if self.page:
                    GLib.idle_add(self.page.progressbar.pulse)
            if self.page:
                label_text = [line for line in self.page.status_label.get_text().split('\n') if line != '']
                if data.get('status') and (len(label_text) == 0 or label_text[-1] != data.get('status')):
                    label_text.append(data.get('status'))
                    GLib.idle_add(self.page.status_label.set_label, '\n'.join(label_text))

            if data.get('digest') and data.get('digest') not in self.digests:
                self.digests.append(data.get('digest').replace(':', '-'))

            if data.get('status') == 'success':
                root_widget = self.get_root()
                new_model = self.success_callback(self.get_name())
                GLib.idle_add(window.local_model_flowbox.remove, self.get_parent())
                GLib.idle_add(window.local_model_flowbox.select_child, new_model.get_parent())
                if len(get_local_models()) > 0:
                    GLib.idle_add(window.title_stack.set_visible_child_name, 'model-selector')
                dialog.show_notification(
                    root_widget=root_widget,
                    title=_('Download Completed'),
                    body=_("Model '{}' downloaded successfully.").format(self.model_title),
                    icon=Gio.ThemedIcon.new('document-save-symbolic')
                )

    def get_page(self):
        if not self.page:
            self.page = PullingModelPage(self)
        return [], self.page

class LocalModelPage(Gtk.Box):
    __gtype_name__ = 'AlpacaLocalModelPage'

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

    def __init__(self, model):
        self.model = model
        super().__init__(
            orientation=1,
            spacing=15,
            valign=3,
            css_classes=['p10']
        )
        image = self.model.create_profile_picture(128)
        if not image:
            image = Gtk.Image.new_from_icon_name('image-missing-symbolic')
            image.set_icon_size(2)
            image.set_size_request(128, 128)
        self.image_container = Gtk.Button(
            css_classes=['circular'],
            halign=3,
            overflow=1,
            child=image,
            tooltip_text=_('Change Profile Picture')
        )
        self.append(self.image_container)
        self.image_container.connect('clicked', lambda *_: self.model.change_profile_picture())
        title_label = Gtk.Label(
            label=prettify_model_name(self.model.get_name(), True)[0],
            tooltip_text=prettify_model_name(self.model.get_name(), True)[0],
            css_classes=['title-1'],
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        self.append(title_label)

        preferences_group = Adw.PreferencesGroup(
            visible=importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice')
        )
        self.append(preferences_group)
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

        information_container = Gtk.FlowBox(
            selection_mode=0,
            homogeneous=True,
            row_spacing=10,
            css_classes=['flowbox_no_padding']
        )
        self.append(information_container)
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
                information_container.append(self.InfoBox(name, value, True))
        if self.model.data.get('system'):
            self.append(self.InfoBox(_('Context'), self.model.data.get('system'), False))
        if self.model.data.get('description'):
            self.append(self.InfoBox(_('Description'), self.model.data.get('description'), False))

        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=5,
            child_spacing=5,
            justify=0,
            halign=1
        )
        self.append(categories_box)
        categories = available_models.get(self.model.get_name().split(':')[0], {}).get('categories', [])
        languages = available_models.get(self.model.get_name().split(':')[0], {}).get('languages', [])
        if not categories:
            categories = available_models.get(self.model.data.get('details', {}).get('parent_model', '').split(':')[0], {}).get('categories', [])
            languages = available_models.get(self.model.data.get('details', {}).get('parent_model', '').split(':')[0], {}).get('languages', [])
        for category in set(categories):
            if category not in ('small', 'medium', 'big', 'huge'):
                categories_box.append(CategoryPill(category, True))

        self.model.image_container.connect('notify::child', lambda *_: self.update_profile_picture())

    def update_profile_picture(self):
        image = self.model.create_profile_picture(128)
        if not image:
            image = Gtk.Image.new_from_icon_name('image-missing-symbolic')
            image.set_size_request(128, 128)
        self.image_container.set_child(image)

    def update_voice(self):
        if self.voice_combo.get_selected() == 0:
            SQL.insert_or_update_model_voice(self.model.get_name(), None)
        else:
            voice = TTS_VOICES.get(self.voice_combo.get_selected_item().get_string())
            SQL.insert_or_update_model_voice(self.model.get_name(), voice)

class LocalModel(Gtk.Box):
    __gtype_name__ = 'AlpacaLocalModel'

    def __init__(self, name:str):
        self.model_title = prettify_model_name(name)
        super().__init__(
            spacing=10,
            css_classes=['card', 'model_box'],
            name=name
        )
        self.image_container = Adw.Bin(
            css_classes=['model_pfp'],
            valign=3,
            halign=3,
            overflow=1,
        )
        self.append(self.image_container)
        text_container = Gtk.Box(
            orientation=1,
            spacing=5,
            valign=3
        )
        self.append(text_container)
        title_label = Gtk.Label(
            label=prettify_model_name(name, True)[0],
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        text_container.append(title_label)
        self.subtitle_label = Gtk.Label(
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1,
            visible=False
        )
        text_container.append(self.subtitle_label)
        self.page = None
        self.row = LocalModelRow(self)
        GLib.idle_add(window.model_dropdown.get_model().append, self.row)
        self.data = {}
        self.update_data()

    def get_search_string(self) -> str:
        return '{} {} {}'.format(self.get_name(), self.model_title, self.data.get('system', None))

    def get_search_categories(self) -> set:
        return set([c for c in available_models.get(self.get_name().split(':')[0], {}).get('categories', []) if c not in ('small', 'medium', 'big', 'huge')])

    def get_vision(self) -> bool:
        return 'vision' in self.data.get('capabilities', [])

    def update_subtitle(self):
        tag = prettify_model_name(self.get_name(), True)[1]
        family = self.data.get('details', {}).get('family')
        if family and tag:
            self.subtitle_label.set_label('{} • {}'.format(prettify_model_name(family), tag))
        elif family:
            self.subtitle_label.set_label(prettify_model_name(family))
        elif tag:
            self.subtitle_label.set_label(tag)
        self.subtitle_label.set_visible(self.subtitle_label.get_label())

    def update_data(self):
        try:
            self.data = window.get_current_instance().get_model_info(self.get_name())
        except Exception as e:
            self.data = {'details': {}}
        self.update_profile_picture()
        self.update_subtitle()

    def get_default_widget(self):
        return self.page.image_container

    def create_profile_picture(self, size:int):
        if self.data['profile_picture']:
            image_data = base64.b64decode(self.data['profile_picture'])
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
        self.data['profile_picture'] = SQL.get_model_preferences(self.get_name()).get('picture', None)
        picture = self.create_profile_picture(64)
        self.image_container.set_visible(picture)
        self.image_container.set_child(picture)

    def change_profile_picture(self):
        def set_profile_picture(file):
            if file:
                picture_b64 = attachments.extract_image(file.get_path(), 128)
                SQL.insert_or_update_model_picture(self.get_name(), picture_b64)
                self.update_profile_picture()
                threading.Thread(target=window.chat_list_box.get_selected_row().update_profile_pictures()).start()

        def remove_profile_picture():
            SQL.insert_or_update_model_picture(self.get_name(), None)
            self.update_profile_picture()
            threading.Thread(target=window.chat_list_box.get_selected_row().update_profile_pictures()).start()

        if self.data['profile_picture']:
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
        if window.get_current_instance().delete_model(self.get_name()):
            found_models = [i for i, row in enumerate(list(window.model_dropdown.get_model())) if row.model.get_name() == self.get_name()]
            if found_models:
                window.model_dropdown.get_model().remove(found_models[0])

            window.local_model_flowbox.remove(self)
            if len(get_local_models()) == 0:
                window.local_model_stack.set_visible_child_name('no-models')
                window.title_stack.set_visible_child_name('no-models')
            SQL.remove_model_preferences(self.get_name())
            threading.Thread(target=window.chat_list_box.get_selected_row().update_profile_pictures()).start()

    def get_page(self):
        buttons = []
        if window.model_creator_stack_page.get_visible():
            create_child_button = Gtk.Button(
                icon_name='list-add-symbolic',
                tooltip_text=_('Create Child')
            )
            create_child_button.connect('clicked', lambda button: window.model_creator_existing(button, self.get_name()))
            buttons.append(create_child_button)

        if window.available_models_stack_page.get_visible():
            remove_button = Gtk.Button(
                icon_name='user-trash-symbolic',
                tooltip_text=_('Remove Model')
            )
            remove_button.connect('clicked', lambda button: dialog.simple(
                parent = self.get_root(),
                heading = _('Remove Model?'),
                body = _("Are you sure you want to remove '{}'?").format(prettify_model_name(self.get_name())),
                callback = self.remove_model,
                button_name = _('Remove'),
                button_appearance = 'destructive'
            ))
            buttons.append(remove_button)
        if len(available_models.get(self.get_name().split(':')[0], {}).get('languages', [])) > 1:
            languages_container = Gtk.FlowBox(
                max_children_per_line=3,
                selection_mode=0
            )
            for language in ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in available_models.get(self.get_name().split(':')[0], {}).get('languages', [])]:
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
            buttons.append(languages_button)
        if not self.page:
            self.page = LocalModelPage(self)
        return buttons, self.page

class CategoryPill(Adw.Bin):
    __gtype_name__ = 'AlpacaCategoryPill'

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


class AvailableModelPage(Gtk.Box):
    __gtype_name__ = 'AlpacaAvailableModelPage'

    def __init__(self, model):
        self.model = model
        super().__init__(
            orientation=1,
            spacing=10,
            valign=3,
            css_classes=['p10'],
            vexpand=True
        )
        title_label = Gtk.Label(
            label=self.model.get_name().replace('-', ' ').title(),
            tooltip_text=self.model.get_name().replace('-', ' ').title(),
            css_classes=['title-1'],
            vexpand=True,
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        self.append(title_label)
        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=5,
            child_spacing=5,
            justify=1
        )
        self.append(categories_box)
        for category in set(self.model.data.get('categories', [])):
            categories_box.append(CategoryPill(category, True))

        self.tag_list = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=0
        )
        model_list = get_local_models()
        for tag in self.model.data.get('tags', []):
            downloaded = '{}:{}'.format(self.model.get_name(), tag[0]) in list(model_list.keys())
            row = Adw.ActionRow(
                title=tag[0],
                subtitle=tag[1],
                sensitive=not downloaded,
                name='{}:{}'.format(self.model.get_name(), tag[0])
            )
            icon = Gtk.Image.new_from_icon_name('check-plain-symbolic' if downloaded else 'folder-download-symbolic')
            row.add_suffix(icon)
            if not downloaded:
                row.connect('activate', lambda *_, row=row, icon=icon: pull_model(row, icon))
                gesture_click = Gtk.GestureClick.new()
                gesture_click.connect("pressed", lambda *_, row=row, icon=icon: pull_model(row, icon))
                row.add_controller(gesture_click)
            self.tag_list.append(row)
        self.append(self.tag_list)
        self.append(Gtk.Label(
            label=_("By downloading this model you accept the license agreement available on the model's website"),
            wrap=True,
            wrap_mode=2,
            css_classes=['dim-label', 'p10'],
            justify=2,
            use_markup=True
        ))

class AvailableModel(Gtk.Box):
    __gtype_name__ = 'AlpacaAvailableModel'

    def __init__(self, name:str, data:dict):
        self.data = data
        super().__init__(
            orientation=1,
            spacing=5,
            css_classes=['card', 'model_box'],
            name=name,
            tooltip_text=name.replace('-', ' ').title()
        )
        title_label = Gtk.Label(
            label=name.replace('-', ' ').title(),
            css_classes=['title-3'],
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            halign=1
        )
        self.append(title_label)
        description_label = Gtk.Label(
            label=self.data.get('description'),
            css_classes=['dim-label'],
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            halign=1
        )
        self.append(description_label)
        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=5,
            child_spacing=5,
            justify=0,
            halign=1,
            valign=3,
            vexpand=True
        )
        self.append(categories_box)
        for category in set(self.data.get('categories', [])):
            categories_box.append(CategoryPill(category, False))
        self.page = None

    def get_default_widget(self):
        return self.page.tag_list

    def get_page(self):
        if not self.page:
            self.page = AvailableModelPage(self)

        web_button = Gtk.Button(
            icon_name='globe-symbolic',
            tooltip_text=self.data.get('url')
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri(self.data.get('url')))

        if len(self.data.get('languages', [])) > 1:
            languages_container = Gtk.FlowBox(
                max_children_per_line=3,
                selection_mode=0
            )
            for language in ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in self.data.get('languages', [])]:
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
            return [web_button, languages_button], self.page
        return [web_button], self.page

    def get_search_string(self) -> str:
        return '{} {} {} {}'.format(self.get_name(), self.get_name().replace('-', ' ').title(), self.data.get('description'), ' '.join(self.data.get('categories')))

    def get_search_categories(self) -> set:
        return set(self.data.get('categories', []))

def add_local_model(model_name:str):
    model_element = LocalModel(model_name)
    window.local_model_flowbox.prepend(model_element)
    return model_element

def add_text_to_speech_model(model_name:str):
    model_element = TextToSpeechModel(model_name)
    window.local_model_flowbox.prepend(model_element)
    return model_element

def add_speech_to_text_model(model_name:str):
    model_element = SpeechToTextModel(model_name)
    window.local_model_flowbox.prepend(model_element)
    return model_element

def update_local_model_list():
    global tts_model_path
    window.local_model_flowbox.remove_all()
    GLib.idle_add(window.model_dropdown.get_model().remove_all)

    if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
        # Speech to Text
        if os.path.isdir(os.path.join(data_dir, 'whisper')):
            for model in os.listdir(os.path.join(data_dir, 'whisper')):
                if model.endswith('.pt') and STT_MODELS.get(model.removesuffix('.pt')):
                    add_speech_to_text_model(model.removesuffix('.pt'))

        # Text to Speech
        tts_model_path = os.path.join(cache_dir, 'huggingface', 'hub')
        if os.path.isdir(tts_model_path) and any([d for d in os.listdir(tts_model_path) if 'Kokoro' in d]):
            # Kokoro has a directory
            tts_model_path = os.path.join(tts_model_path, [d for d in os.listdir(tts_model_path) if 'Kokoro' in d][0], 'snapshots')
            if os.path.isdir(tts_model_path) and len(os.listdir(tts_model_path)) > 0:
                # Kokoro has snapshots
                tts_model_path = os.path.join(tts_model_path, os.listdir(tts_model_path)[0], 'voices')
                if os.path.isdir(tts_model_path):
                    # Kokoro has voices
                    for model in os.listdir(tts_model_path):
                        pretty_name = [k for k, v in TTS_VOICES.items() if v == model.removesuffix('.pt')]
                        if len(pretty_name) > 0:
                            pretty_name = pretty_name[0]
                            add_text_to_speech_model(pretty_name)

    # Normal Models
    threads=[]
    window.get_current_instance().local_models = None # To reset cache
    local_models = window.get_current_instance().get_local_models()
    for model in local_models:
        thread = threading.Thread(target=add_local_model, args=(model['name'], ))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    window.title_stack.set_visible_child_name('model-selector' if len(get_local_models()) > 0 else 'no-models')
    window.local_model_stack.set_visible_child_name('content' if len(list(window.local_model_flowbox)) > 0 else 'no-models')
    window.model_dropdown.set_enable_search(len(local_models) > 10)

def update_available_model_list():
    global available_models
    window.available_model_flowbox.remove_all()
    available_models = window.get_current_instance().get_available_models()

    # Category Filter
    window.model_filter_button.set_visible(len(available_models) > 0)
    container = Gtk.Box(
        orientation=1,
        spacing=5
    )
    if len(available_models) > 0:
        for name, category in CategoryPill.metadata.items():
            if category.get('name') and (name != 'embedding' or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1'):
                pill_container = Gtk.Box(
                    spacing=5,
                    halign=3
                )
                icon = Gtk.Image.new_from_icon_name(category.get('icon', 'language-symbolic'))
                icon.set_css_classes(category.get('css', []))
                pill_container.append(icon)
                pill_container.append(Gtk.Label(label=category.get('name')))
                checkbtn = Gtk.CheckButton(
                    child=pill_container,
                    name=name
                )
                checkbtn.connect('toggled', lambda *_: window.model_search_changed(window.searchentry_models))
                container.append(checkbtn)
    window.model_filter_button.set_popover(
        Gtk.Popover(
            child=container,
            has_arrow=True
        )
    )

    for name, model_info in available_models.items():
        if 'small' in model_info['categories'] or 'medium' in model_info['categories'] or 'big' in model_info['categories'] or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
            if 'embedding' not in model_info['categories'] or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
                model_element = AvailableModel(name, model_info)
                window.available_model_flowbox.append(model_element)
    window.get_application().lookup_action('download_model_from_name').set_enabled(len(available_models) > 0)
    window.available_models_stack_page.set_visible(len(available_models) > 0)
    window.model_creator_stack_page.set_visible(len(available_models) > 0)
    visible_model_manger_switch = len([p for p in window.model_manager_stack.get_pages() if p.get_visible()]) > 1
    window.model_manager_bottom_view_switcher.set_visible(visible_model_manger_switch)
    window.model_manager_top_view_switcher.set_visible(visible_model_manger_switch)

def get_local_models() -> dict:
    results = {}
    for model in [item.get_child() for item in list(window.local_model_flowbox) if isinstance(item.get_child(), LocalModel)]:
        results[model.get_name()] = model
    return results

def pull_model_confirm(model_name:str):
    if model_name:
        model_name = model_name.strip().replace('\n', '')
        if model_name not in list(get_local_models().keys()):
            model = PullingModel(model_name, add_local_model)
            window.local_model_flowbox.prepend(model)
            GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'added_models')
            GLib.idle_add(window.local_model_flowbox.select_child, model.get_parent())
            GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
            window.get_current_instance().pull_model(model_name, model.update_progressbar)

def pull_model(row, icon):
    model_name = row.get_name()
    row.remove(icon)
    row.add_suffix(Gtk.Image.new_from_icon_name('check-plain-symbolic'))
    row.set_sensitive(False)
    threading.Thread(target=pull_model_confirm, args=(model_name,)).start()

def create_model_confirm(data:dict, gguf_path:str):
    if data.get('model') and data.get('model') not in list(get_local_models().keys()):
        model = PullingModel(data.get('model'), add_local_model)
        window.local_model_flowbox.prepend(model)
        GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'added_models')
        GLib.idle_add(window.local_model_flowbox.select_child, model.get_parent())
        GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
        if gguf_path:
            try:
                with open(gguf_path, 'rb', buffering=0) as f:
                    model.update_progressbar({'status': 'Generating sha256'})
                    sha256 = hashlib.file_digest(f, 'sha256').hexdigest()

                if not window.get_current_instance().gguf_exists(sha256):
                    model.update_progressbar({'status': 'Uploading GGUF to Ollama instance'})
                    window.get_current_instance().upload_gguf(gguf_path, sha256)
                    data['files'] = {os.path.split(gguf_path)[1]: 'sha256:{}'.format(sha256)}
            except Exception as e:
                logger.error(e)
                GLib.idle_add(window.local_model_flowbox.remove, model.get_parent())
                return
        window.get_current_instance().create_model(data, model.update_progressbar)

def create_model(data:dict, gguf_path:str=None):
    threading.Thread(target=create_model_confirm, args=(data, gguf_path)).start()

class FallbackModel:
    def get_name():
        return None

    def get_vision() -> bool:
        return False

def get_selected_model():
    selected_item = window.model_dropdown.get_selected_item()
    if selected_item:
        return selected_item.model
    else:
        return FallbackModel
