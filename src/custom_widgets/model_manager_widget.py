# model_manager_widget.py
"""
Handles models
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk, GdkPixbuf
import logging, os, datetime, re, shutil, threading, json, sys, glob, icu, base64, hashlib
from ..internal import config_dir, data_dir, cache_dir, source_dir
from .. import available_models_descriptions
from . import dialog_widget

logger = logging.getLogger(__name__)

window = None

available_models = None

class local_model_row(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaLocalModelRow'

    def __init__(self, model):
        self.model = model
        model_title = window.convert_model_name(self.model.get_name(), 0)
        super().__init__(
            child=Gtk.Label(
                label=model_title,
                use_markup=True,
                halign=1,
                hexpand=True
            ),
            halign=0,
            hexpand=True,
            name=self.model.get_name(),
            tooltip_text=model_title
        )

class local_model_selector(Adw.Bin):
    __gtype_name__ = 'AlpacaLocalModelSelector'

    def __init__(self):
        self.local_model_list = Gtk.ListBox(
            css_classes=['navigation-sidebar', 'model_list_box'],
            height_request=0,
            selection_mode=1
        )
        scroller = Gtk.ScrolledWindow(
            max_content_height=300,
            propagate_natural_width=True,
            propagate_natural_height=True,
            child=self.local_model_list
        )
        popover = Gtk.Popover(
            css_classes=['model_popover'],
            has_arrow=False,
            child=scroller
        )

        self.local_model_list.connect('row-selected', lambda listbox, row: self.on_row_selected(row))
        self.local_model_list.connect('row-activated', lambda *_: popover.hide())
        manage_models_button = Gtk.Button(
            tooltip_text=_('Manage Models'),
            icon_name='brain-augemnted-symbolic',
            css_classes=['flat']
        )
        manage_models_button.set_action_name("app.model_manager")

        button_container = Gtk.Box(spacing=5)
        self.button_label = Gtk.Label(use_markup=True, ellipsize=3)
        button_container.append(self.button_label)
        button_container.append(Gtk.Image.new_from_icon_name("down-symbolic"))
        selector_button = Gtk.MenuButton(
            child=button_container,
            popover=popover,
            css_classes=['flat']
        )
        container = Gtk.Box(css_classes=['card', 'local_model_selector'], halign=3)
        container.append(manage_models_button)
        container.append(selector_button)
        super().__init__(child=container)

    def on_row_selected(self, row):
        if row:
            self.button_label.set_label(row.get_child().get_label())
        elif len(list(self.local_model_list)) > 0:
            self.local_model_list.select_row(list(self.local_model_list)[0])

    def get_selected_model(self):
        return self.local_model_list.get_selected_row().model

    def get_model_by_name(self, name:str):
        results = [value for key, value in get_local_models().items() if key == name]
        if len(results) > 0:
            return results[0]

class pulling_model_page(Gtk.Box):
    __gtype_name__ = 'AlpacaPullingModelPage'

    def __init__(self, model):
        self.model = model
        model_title = window.convert_model_name(self.model.get_name(), 0)
        super().__init__(
            orientation=1,
            spacing=10,
            valign=3,
            css_classes=['p10']
        )
        title_label = Gtk.Label(
            label=model_title.split(' (')[0],
            tooltip_text=model_title.split(' (')[0],
            css_classes=['title-1'],
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        self.append(title_label)
        self.status_label = Gtk.Label(
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        self.append(Adw.Bin(css_classes=['card', 'p10'], child=self.status_label))
        self.progressbar = Gtk.ProgressBar()
        self.append(self.progressbar)

class pulling_model(Gtk.Box):
    __gtype_name__ = 'NewAlpacaPullingModel'

    def __init__(self, name:str):
        self.model_title = window.convert_model_name(name, 0)
        super().__init__(
            orientation=1,
            spacing=5,
            css_classes=['card', 'model_box'],
            name=name
        )
        title_label = Gtk.Label(
            label=self.model_title.split(' (')[0],
            css_classes=['title-3'],
            vexpand=True,
            ellipsize=3
        )
        self.append(title_label)
        subtitle_label = Gtk.Label(
            label=self.model_title.split(' (')[1][:-1],
            css_classes=['dim-label'],
            vexpand=True,
            ellipsize=3
        )
        self.append(subtitle_label)
        self.progressbar = Gtk.ProgressBar()
        self.append(self.progressbar)
        self.page = None
        self.digests = []

    def get_default_widget(self):
        return self.page

    def get_search_string(self) -> str:
        return '{} {}'.format(self.get_name(), self.model_title)

    def update_progressbar(self, data:dict):
        if not self.get_parent():
            logger.info("Pulling of '{}' was canceled".format(self.get_name()))
            directory = os.path.join(window.ollama_instance.model_directory, 'blobs')
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
            logger.error(self.error)
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
                new_model = add_local_model(self.get_name())
                GLib.idle_add(window.local_model_flowbox.remove, self.get_parent())
                GLib.idle_add(window.local_model_flowbox.select_child, new_model.get_parent())
                GLib.idle_add(window.title_stack.set_visible_child_name, 'model-selector')

    def get_page(self):
        def stop_download():
            window.local_model_flowbox.remove(self)
            if len(list(window.local_model_flowbox)) == 0:
                window.local_model_stack.set_visible_child_name('no-models')

        actionbar = Gtk.ActionBar()
        stop_button = Gtk.Button(
            child=Adw.ButtonContent(
                icon_name='media-playback-stop-symbolic',
                label=_('Stop Download')
            ),
            tooltip_text=_('Stop Download'),
            css_classes=['destructive-action']
        )
        stop_button.connect('clicked', lambda button: dialog_widget.simple(
            _('Stop Download?'),
            _("Are you sure you want to stop pulling '{}'?").format(window.convert_model_name(self.get_name(), 0)),
            stop_download,
            _('Stop'),
            'destructive'
        ))
        actionbar.set_center_widget(stop_button)
        if not self.page:
            self.page = pulling_model_page(self)
        elif self.page.get_parent():
            self.page.get_parent().remove(self.page)
        return actionbar, Gtk.ScrolledWindow(child=self.page, css_classes=['undershoot-bottom'])

class local_model_page(Gtk.Box):
    __gtype_name__ = 'AlpacaLocalModelPage'

    def __init__(self, model):
        self.model = model
        model_title = window.convert_model_name(self.model.get_name(), 0)
        super().__init__(
            orientation=1,
            spacing=10,
            valign=3,
            css_classes=['p10']
        )
        image = self.model.create_profile_picture(128)
        if not image:
            image = Gtk.Image.new_from_icon_name('image-missing-symbolic')
            image.set_size_request(128, 128)
        self.image_container = Gtk.Button(
            css_classes=['circular'],
            halign=3,
            overflow=1,
            child=image,
            tooltip_text=_('Change Profile Picture')
        )
        self.append(self.image_container)
        self.image_container.connect('clicked', lambda *_: self.change_profile_picture())
        title_label = Gtk.Label(
            label=model_title.split(' (')[0],
            tooltip_text=model_title.split(' (')[0],
            css_classes=['title-1'],
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        self.append(title_label)
        information_container = Gtk.FlowBox(
            selection_mode=0
        )
        self.append(information_container)
        parent_model = self.model.data.get('details', {}).get('parent_model')
        metadata={
            _('Tag'): model_title.split(' (')[-1][:-1],
            _('Parent Model'): parent_model if '/' not in parent_model else 'GGUF',
            _('Family'): self.model.data.get('details', {}).get('family'),
            _('Parameter Size'): self.model.data.get('details', {}).get('parameter_size'),
            _('Quantization Level'): self.model.data.get('details', {}).get('quantization_level')
        }

        if 'modified_at' in self.model.data:
            metadata[_('Modified At')] = datetime.datetime.strptime(':'.join(self.model.data['modified_at'].split(':')[:2]), '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
        else:
            metadata[_('Modified At')] = None

        for name, value in metadata.items():
            info_box = Gtk.Box(
                orientation=1,
                spacing=5,
                css_classes=['card'],
                name=name
            )
            title_label = Gtk.Label(
                label=name,
                css_classes=['subtitle', 'caption', 'dim-label'],
                hexpand=True,
                margin_top=10,
                margin_start=0,
                margin_end=0,
                ellipsize=3,
                tooltip_text=name
            )
            info_box.append(title_label)
            subtitle_label = Gtk.Label(
                label=value if value else _('Not Available'),
                css_classes=['heading'],
                hexpand=True,
                margin_bottom=10,
                margin_start=0,
                margin_end=0,
                ellipsize=3,
                tooltip_text=value if value else _('Not Available')
            )
            info_box.append(subtitle_label)
            information_container.append(info_box)

        system_label = Adw.Bin(
            css_classes=['card', 'p10'],
            child = Gtk.Label(
                label=self.model.data['system'] if 'system' in self.model.data and self.model.data['system'] else _('(No system message available)'),
                hexpand=True,
                halign=0,
                wrap=True,
                wrap_mode=2,
                justify=2,
            ),
            focusable=True
        )
        self.append(system_label)

    def change_profile_picture(self):
        def set_profile_picture(file):
            if file:
                picture_b64 = window.get_content_of_file(file.get_path(), 'profile_picture')
                window.sql_instance.insert_or_update_model_picture(self.model.get_name(), picture_b64)
                self.model.update_profile_picture()

        def remove_profile_picture():
            window.sql_instance.delete_model_picture(self.model.get_name())
            self.model.update_profile_picture()

        file_filter = Gtk.FileFilter()
        for suffix in ('png', 'jpg', 'jpeg', 'webp'):
            file_filter.add_suffix(suffix)
        if self.model.data['profile_picture']:
            options = {
                _('Cancel'): {'callback': lambda: None},
                _('Remove'): {'callback': remove_profile_picture, 'appearance': 'destructive'},
                _('Change'): {'callback': lambda: dialog_widget.simple_file(file_filter, set_profile_picture), 'appearance': 'suggested'},
            }

            dialog_widget.Options(_("Model Profile Picture"), _("What do you want to do with the model's profile picture?"), list(options.keys())[0], options)
        else:
            dialog_widget.simple_file(file_filter, set_profile_picture)

class local_model(Gtk.Box):
    __gtype_name__ = 'NewAlpacaLocalModel'

    def __init__(self, name:str):
        self.model_title = window.convert_model_name(name, 0)
        super().__init__(
            orientation=1,
            spacing=5,
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
        title_label = Gtk.Label(
            label=self.model_title.split(' (')[0],
            css_classes=['title-3'],
            vexpand=True,
            ellipsize=3
        )
        self.append(title_label)
        subtitle_label = Gtk.Label(
            label=self.model_title.split(' (')[1][:-1],
            css_classes=['dim-label'],
            vexpand=True,
            ellipsize=3
        )
        self.append(subtitle_label)
        self.page = None
        self.row = local_model_row(self)
        window.model_selector.local_model_list.prepend(self.row)
        self.data = {}
        self.update_data()

    def get_search_string(self) -> str:
        return '{} {} {}'.format(self.get_name(), self.model_title, self.data.get('system', None))

    def get_vision(self) -> bool:
        return self.data.get('projector_info', None) is not None

    def update_data(self):
        try:
            response = window.ollama_instance.request("POST", "api/show", json.dumps({"name": self.get_name()}))
            self.data = json.loads(response.text)
        except Exception as e:
            self.data = {'details': {}}
        self.update_profile_picture()

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
        self.data['profile_picture'] = window.sql_instance.get_model_picture(self.get_name())
        self.image_container.set_child(self.create_profile_picture(64))
        if self.page:
            image = self.create_profile_picture(128)
            if not image:
                image = Gtk.Image.new_from_icon_name('image-missing-symbolic')
                image.set_size_request(128, 128)
            self.page.image_container.set_child(image)

    def remove_model(self):
        response = window.ollama_instance.request("DELETE", "api/delete", json.dumps({"name": self.get_name()}))
        if response.status_code == 200:
            window.model_selector.local_model_list.remove(self.row)
            window.local_model_flowbox.remove(self)
            if len(list(window.local_model_flowbox)) == 0:
                window.local_model_stack.set_visible_child_name('no-models')
                window.title_stack.set_visible_child_name('no-models')
            window.sql_instance.delete_model_picture(self.get_name())

    def get_page(self):
        actionbar = Gtk.ActionBar()
        create_child_button = Gtk.Button(
            icon_name='list-add-symbolic',
            tooltip_text=_('Create Child'),
            css_classes=['accent']
        )
        actionbar.pack_start(create_child_button)

        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            tooltip_text=_('Remove Model'),
            css_classes=['destructive-action']
        )
        remove_button.connect('clicked', lambda button: dialog_widget.simple(
            _('Remove Model?'),
            _("Are you sure you want to remove '{}'?").format(window.convert_model_name(self.get_name(), 0)),
            self.remove_model,
            _('Remove'),
            'destructive'
        ))
        actionbar.pack_end(remove_button)
        if not self.page:
            self.page = local_model_page(self)
        elif self.page.get_parent():
            self.page.get_parent().remove(self.page)
        return actionbar, Gtk.ScrolledWindow(child=self.page, css_classes=['undershoot-bottom'])

class category_pill(Gtk.Button):
    __gtype_name__ = 'NewAlpacaCategoryPill'

    metadata = {
        'multilingual': {'name': _('Multilingual'), 'css': ['accent'], 'icon': 'language-symbolic'},
        'code': {'name': _('Code'), 'css': ['accent'], 'icon': 'code-symbolic'},
        'math': {'name': _('Math'), 'css': ['accent'], 'icon': 'accessories-calculator-symbolic'},
        'vision': {'name': _('Vision'), 'css': ['accent'], 'icon': 'eye-open-negative-filled-symbolic'},
        'embedding': {'name': _('Embedding'), 'css': ['error'], 'icon': 'brain-augemnted-symbolic'},
        'small': {'name': _('Small'), 'css': ['success'], 'icon': 'leaf-symbolic'},
        'medium': {'name': _('Medium'), 'css': ['success'], 'icon': 'sprout-symbolic'},
        'big': {'name': _('Big'), 'css': ['warning'], 'icon': 'tree-circle-symbolic'},
        'huge': {'name': _('Huge'), 'css': ['error'], 'icon': 'weight-symbolic'},
        'language': {'css': [], 'icon': 'language-symbolic'}
    }

    def __init__(self, name_id:str, show_label:bool):
        if 'language:' in name_id:
            self.metadata['language']['name'] = name_id.split(':')[1]
            name_id = 'language'
        button_content = Adw.ButtonContent(
            icon_name=self.metadata[name_id]['icon']
        )
        if show_label:
            button_content.set_label(self.metadata[name_id]['name'])
        super().__init__(
            css_classes=['subtitle', 'category_pill'] + self.metadata[name_id]['css'] + (['pill'] if show_label else ['circular']),
            tooltip_text=self.metadata[name_id]['name'],
            child=button_content,
            halign=1,
            focusable=False
        )

class available_model_page(Gtk.Box):
    __gtype_name__ = 'AlpacaAvailableModelPage'

    def __init__(self, model):
        self.model = model
        super().__init__(
            orientation=1,
            spacing=10,
            valign=3,
            css_classes=['p10']
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
        categories_box = Gtk.FlowBox(
            hexpand=True,
            selection_mode=0
        )
        for category in self.model.data.get('categories', []) + ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in self.model.data.get('languages', [])]:
            categories_box.append(category_pill(category, True))
        self.append(categories_box)

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

class available_model(Gtk.Box):
    __gtype_name__ = 'NewAlpacaAvailableModel'

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
            ellipsize=3,
            halign=1
        )
        self.append(title_label)
        description_label = Gtk.Label(
            label=available_models_descriptions.descriptions[name],
            css_classes=['dim-label'],
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            halign=1
        )
        self.append(description_label)
        self.page = None

    def get_default_widget(self):
        return self.page.tag_list

    def get_page(self):
        self.page = available_model_page(self)
        self.page.set_vexpand(True)

        disclaimer = Gtk.Label(
            label=_("By downloading this model you accept the license agreement available on the model's website"),
            wrap=True,
            wrap_mode=2,
            css_classes=['dim-label', 'p10'],
            justify=2,
            use_markup=True
        )

        container = Gtk.Box(orientation=1, spacing=5)
        container.append(Gtk.ScrolledWindow(child=self.page, css_classes=['undershoot-bottom']))
        container.append(disclaimer)

        actionbar = Gtk.ActionBar()
        web_button = Gtk.Button(
            child=Adw.ButtonContent(
                icon_name='globe-symbolic',
                label=_('Visit Website')
            ),
            tooltip_text=self.data.get('url'),
            css_classes=['raised']
        )
        web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri(self.data.get('url')))
        actionbar.set_center_widget(web_button)

        return actionbar, container

    def get_search_string(self) -> str:
        return '{} {} {} {}'.format(self.get_name(), self.get_name().replace('-', ' ').title(), available_models_descriptions.descriptions[self.get_name()], ' '.join(self.data.get('categories')))

def add_local_model(model_name:str):
    model_element = local_model(model_name)
    window.local_model_flowbox.prepend(model_element)
    return model_element

def update_local_model_list():
    string_list = Gtk.StringList()
    window.local_model_flowbox.remove_all()
    window.model_selector.local_model_list.remove_all()
    try:
        response = window.ollama_instance.request("GET", "api/tags")
        if response.status_code == 200:
            threads = []
            data = json.loads(response.text)
            for model in data.get('models'):
                string_list.append(model.get('name'))
                thread = threading.Thread(target=add_local_model, args=(model['name'], ))
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
        else:
            window.connection_error()
    except Exception as e:
        logger.error(e)
        window.connection_error()
    window.title_stack.set_visible_child_name('model-selector' if len(get_local_models()) > 0 else 'no-models')
    window.local_model_stack.set_visible_child_name('content' if len(get_local_models()) > 0 else 'no-models')
    window.default_model_combo.set_model(string_list)

def update_available_model_list():
    global available_models
    try:
        with open(os.path.join(source_dir, 'available_models.json'), 'r', encoding="utf-8") as f:
            available_models = json.load(f)
    except Exception as e:
        available_models = {}
    window.available_model_flowbox.remove_all()
    for name, model_info in available_models.items():
        if 'small' in model_info['categories'] or 'medium' in model_info['categories'] or 'big' in model_info['categories'] or os.getenv('ALPACA_SHOW_HUGE_MODELS', '0') == '1':
            if 'embedding' not in model_info['categories'] or os.getenv('ALPACA_SHOW_EMBEDDING_MODELS', '0') == '1':
                model_element = available_model(name, model_info)
                window.available_model_flowbox.append(model_element)

def get_local_models() -> dict:
    results = {}
    for model in [item.get_child() for item in list(window.local_model_flowbox) if isinstance(item.get_child(), local_model)]:
        results[model.get_name()] = model
    return results

def pull_model_confirm(model_name:str):
    if model_name not in list(get_local_models().keys()):
        model = pulling_model(model_name)
        window.local_model_flowbox.prepend(model)
        GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'local_models')
        GLib.idle_add(window.local_model_flowbox.select_child, model.get_parent())
        GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
        response = window.ollama_instance.request("POST", "api/pull", json.dumps({'name': model_name, 'stream': True}), lambda result_data: model.update_progressbar(result_data))

def pull_model(row, icon):
    model_name = row.get_name()
    row.remove(icon)
    row.add_suffix(Gtk.Image.new_from_icon_name('check-plain-symbolic'))
    row.set_sensitive(False)
    threading.Thread(target=pull_model_confirm, args=(model_name,)).start()

def create_model_confirm(data:dict, gguf_path:str):
    if data.get('model') and data.get('model') not in list(get_local_models().keys()):
        model = pulling_model(data.get('model'))
        window.local_model_flowbox.prepend(model)
        GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'local_models')
        GLib.idle_add(window.local_model_flowbox.select_child, model.get_parent())
        GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
        if gguf_path:
            try:
                with open(gguf_path, 'rb', buffering=0) as f:
                    model.update_progressbar({'status': 'Generating sha256'})
                    sha256 = hashlib.file_digest(f, 'sha256').hexdigest()

                with open(gguf_path, 'rb') as f:
                    response = window.ollama_instance.request('GET', 'api/blobs/sha256:{}'.format(sha256))
                    if response.status_code == 404:
                        print('a')
                        model.update_progressbar({'status': 'Uploading GGUF to Ollama instance'})
                        response = window.ollama_instance.request('POST', 'api/blobs/sha256:{}'.format(sha256), f)
                    data['files'] = {os.path.split(gguf_path)[1]: 'sha256:{}'.format(sha256)}
            except Exception as e:
                logger.error(e)
                GLib.idle_add(window.local_model_flowbox.remove, model.get_parent())
                return
        response = window.ollama_instance.request("POST", "api/create", json.dumps(data), lambda result_data: model.update_progressbar(result_data))

def create_model(data:dict, gguf_path:str=None):
    threading.Thread(target=create_model_confirm, args=(data, gguf_path)).start()

