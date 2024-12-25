#model_widget.py
"""
Handles the model widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk
import logging, os, datetime, re, shutil, threading, json, sys, glob
from ..internal import config_dir, data_dir, cache_dir, source_dir
from .. import available_models_descriptions
from . import dialog_widget

logger = logging.getLogger(__name__)

window = None

available_models = None

class model_selector_popup(Gtk.Popover):
    __gtype_name__ = 'AlpacaModelSelectorPopup'

    def __init__(self):
        manage_models_button = Gtk.Button(
            tooltip_text=_('Manage Models'),
            child=Gtk.Label(label=_('Manage Models'), halign=1),
            hexpand=True,
            css_classes=['manage_models_button', 'flat']
        )
        manage_models_button.set_action_name("app.manage_models")
        manage_models_button.connect("clicked", lambda *_: self.hide())
        self.model_list_box = Gtk.ListBox(
            css_classes=['navigation-sidebar', 'model_list_box'],
            height_request=0
        )
        container = Gtk.Box(
            orientation=1,
            spacing=5
        )
        container.append(self.model_list_box)
        container.append(Gtk.Separator())
        container.append(manage_models_button)

        scroller = Gtk.ScrolledWindow(
            max_content_height=300,
            propagate_natural_width=True,
            propagate_natural_height=True,
            child=container
        )

        super().__init__(
            css_classes=['model_popover'],
            has_arrow=False,
            child=scroller
        )

class model_selector_row(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaModelSelectorRow'

    def __init__(self, model_name:str, data:dict):
        super().__init__(
            child = Gtk.Label(
                label=window.convert_model_name(model_name, 0),
                halign=1,
                hexpand=True
            ),
            halign=0,
            hexpand=True,
            name=model_name,
            tooltip_text=window.convert_model_name(model_name, 0)
        )
        self.data = data
        self.image_recognition = 'projector_info' in self.data

class model_selector_button(Gtk.MenuButton):
    __gtype_name__ = 'AlpacaModelSelectorButton'

    def __init__(self):
        self.popover = model_selector_popup()
        self.popover.model_list_box.connect('selected-rows-changed', self.model_changed)
        self.popover.model_list_box.connect('row-activated', lambda *_: self.get_popover().hide())
        container = Gtk.Box(
            orientation=0,
            spacing=5
        )
        self.label = Gtk.Label()
        container.append(self.label)
        container.append(Gtk.Image.new_from_icon_name("down-symbolic"))
        super().__init__(
            child=container,
            popover=self.popover,
            halign=3
        )

    def change_model(self, model_name:str):
        for model_row in list(self.get_popover().model_list_box):
            if model_name == model_row.get_name():
                self.get_popover().model_list_box.select_row(model_row)
                break

    def model_changed(self, listbox:Gtk.ListBox):
        row = listbox.get_selected_row()
        if row:
            model_name = row.get_name()
            self.label.set_label(window.convert_model_name(model_name, 0))
            self.set_tooltip_text(window.convert_model_name(model_name, 0))
        elif len(list(listbox)) == 0:
            window.title_stack.set_visible_child_name('no_models')
        window.model_manager.verify_if_image_can_be_used()

    def add_model(self, model_name:str, data:dict):
        model_row = model_selector_row(model_name, data)
        GLib.idle_add(self.get_popover().model_list_box.append, model_row)
        GLib.idle_add(self.change_model, model_name)
        GLib.idle_add(window.title_stack.set_visible_child_name, 'model_selector')

    def remove_model(self, model_name:str):
        self.get_popover().model_list_box.remove(next((model for model in list(self.get_popover().model_list_box) if model.get_name() == model_name), None))
        self.model_changed(self.get_popover().model_list_box)
        window.title_stack.set_visible_child_name('model_selector' if len(window.model_manager.get_model_list()) > 0 else 'no_models')

    def clear_list(self):
        self.get_popover().model_list_box.remove_all()

class pulling_model(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaPullingModel'

    def __init__(self, model_name:str):
        model_label = Gtk.Label(
            css_classes=["heading"],
            label=model_name.split(":")[0].replace("-", " ").title(),
            hexpand=True,
            halign=1
        )
        tag_label = Gtk.Label(
            css_classes=["subtitle"],
            label=model_name.split(":")[1]
        )
        self.prc_label = Gtk.Label(
            css_classes=["subtitle", "numeric"],
            label='50%',
            hexpand=True,
            halign=2
        )
        subtitle_box = Gtk.Box(
            hexpand=True,
            spacing=5,
            orientation=0
        )
        subtitle_box.append(tag_label)
        subtitle_box.append(self.prc_label)
        self.progress_bar = Gtk.ProgressBar(
            valign=2,
            show_text=False,
            css_classes=["horizontal"],
            fraction=.5
        )
        description_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=5,
            orientation=1
        )
        description_box.append(model_label)
        description_box.append(subtitle_box)
        description_box.append(self.progress_bar)

        stop_button = Gtk.Button(
            icon_name = "media-playback-stop-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["error", "circular"],
            tooltip_text = _("Stop Pulling '{}'").format(window.convert_model_name(model_name, 0))
        )
        stop_button.connect('clicked', lambda *i: dialog_widget.simple(
            _('Stop Download?'),
            _("Are you sure you want to stop pulling '{}'?").format(window.convert_model_name(self.get_name(), 0)),
            self.stop,
            _('Stop'),
            'destructive'
        ))

        container_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=10,
            orientation=0,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10
        )

        container_box.append(description_box)
        container_box.append(stop_button)

        super().__init__(
            child=container_box,
            name=model_name
        )
        self.error = None
        self.digests = []

    def stop(self):
        if len(list(self.get_parent())) == 1:
            self.get_parent().set_visible(False)
        self.get_parent().remove(self)

    def update(self, data):
        if 'digest' in data and data['digest'] not in self.digests:
            self.digests.append(data['digest'].replace(':', '-'))
        if not self.get_parent():
            logger.info("Pulling of '{}' was canceled".format(self.get_name()))
            directory = os.path.join(data_dir, '.ollama', 'models', 'blobs')
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
        if 'total' in data and 'completed' in data:
            fraction = round(data['completed'] / data['total'], 4)
            GLib.idle_add(self.prc_label.set_label, f"{fraction:05.2%}")
            GLib.idle_add(self.progress_bar.set_fraction, fraction)
        else:
            GLib.idle_add(self.prc_label.set_label, data['status'])
            GLib.idle_add(self.progress_bar.pulse)

class pulling_model_list(Gtk.ListBox):
    __gtype_name__ = 'AlpacaPullingModelList'

    def __init__(self):
        super().__init__(
            selection_mode=0,
            css_classes=["boxed-list"],
            visible=False
        )

class information_bow(Gtk.Box):
    __gtype_name__ = 'AlpacaModelInformationBow'

    def __init__(self, title:str, subtitle:str):
        self.title = title
        self.subtitle = subtitle
        title_label = Gtk.Label(
            label=self.title,
            css_classes=['subtitle', 'caption', 'dim-label'],
            hexpand=True,
            margin_top=10,
            margin_start=0,
            margin_end=0
        )
        subtitle_label = Gtk.Label(
            label=self.subtitle if self.subtitle else '(none)',
            css_classes=['heading'],
            hexpand=True,
            margin_bottom=10,
            margin_start=0,
            margin_end=0
        )
        super().__init__(
            spacing=5,
            orientation=1,
            css_classes=['card']
        )
        self.append(title_label)
        self.append(subtitle_label)

class category_pill(Gtk.Button):
    __gtype_name__ = 'AlpacaCategoryPill'

    metadata = {
        'multilingual': {'name': _('Multilingual'), 'css': ['accent'], 'icon': 'language-symbolic'},
        'code': {'name': _('Code'), 'css': ['accent'], 'icon': 'code-symbolic'},
        'math': {'name': _('Math'), 'css': ['accent'], 'icon': 'accessories-calculator-symbolic'},
        'vision': {'name': _('Vision'), 'css': ['accent'], 'icon': 'eye-open-negative-filled-symbolic'},
        'embedding': {'name': _('Embedding'), 'css': ['error'], 'icon': 'brain-augemnted-symbolic'},
        'small': {'name': _('Small'), 'css': ['success'], 'icon': 'leaf-symbolic'},
        'medium': {'name': _('Medium'), 'css': ['success'], 'icon': 'sprout-symbolic'},
        'big': {'name': _('Big'), 'css': ['warning'], 'icon': 'tree-circle-symbolic'},
        'huge': {'name': _('Huge'), 'css': ['error'], 'icon': 'weight-symbolic'}
    }

    def __init__(self, name_id:str, show_label:bool):
        button_content = Adw.ButtonContent(
            icon_name=self.metadata[name_id]['icon']
        )
        if show_label:
            button_content.set_label(self.metadata[name_id]['name'])
        super().__init__(
            css_classes=['subtitle', 'category_pill'] + self.metadata[name_id]['css'] + (['pill'] if show_label else ['circular']),
            tooltip_text=self.metadata[name_id]['name'],
            child=button_content,
            halign=1
        )


class local_model(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaLocalModel'

    def __init__(self, model_name:str, categories:list):
        model_title = window.convert_model_name(model_name, 0)
        self.categories = categories
        model_label = Gtk.Label(
            css_classes=["heading"],
            label=model_title.split(" (")[0],
            hexpand=True,
            halign=1
        )
        tag_label = Gtk.Label(
            css_classes=["subtitle"],
            label=model_title.split(" (")[1][:-1],
            hexpand=True,
            halign=1
        )
        description_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=5,
            orientation=1
        )
        description_box.append(model_label)
        description_box.append(tag_label)

        info_button = Gtk.Button(
            icon_name = "info-outline-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["circular"],
            tooltip_text = _("Details")
        )

        info_button.connect('clicked', self.show_information)

        delete_button = Gtk.Button(
            icon_name = "user-trash-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["error", "circular"],
            tooltip_text = _("Remove '{}'").format(window.convert_model_name(model_name, 0))
        )

        delete_button.connect('clicked', lambda *i: dialog_widget.simple(
            _('Delete Model?'),
            _("Are you sure you want to delete '{}'?").format(model_title),
            lambda model_name=model_name: window.model_manager.remove_local_model(model_name),
            _('Delete'),
            'destructive'
        ))

        container_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=10,
            orientation=0,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10
        )
        container_box.append(description_box)
        container_box.append(info_button)
        container_box.append(delete_button)

        super().__init__(
            child=container_box,
            name=model_name
        )

    def show_information(self, button):
        model = next((element for element in list(window.model_manager.model_selector.get_popover().model_list_box) if element.get_name() == self.get_name()), None)
        model_name = model.get_child().get_label()

        window.model_detail_page.set_title(' ('.join(model_name.split(' (')[:-1]))
        window.model_detail_page.set_description(' ('.join(model_name.split(' (')[-1:])[:-1])
        window.model_detail_create_button.set_name(model_name)
        window.model_detail_create_button.set_tooltip_text(_("Create Model Based on '{}'").format(model_name))

        details_flow_box = Gtk.FlowBox(
            valign=1,
            hexpand=True,
            vexpand=False,
            selection_mode=0,
            max_children_per_line=2,
            min_children_per_line=1,
        )

        translation_strings={
            'modified_at': _('Modified At'),
            'parent_model': _('Parent Model'),
            'format': _('Format'),
            'family': _('Family'),
            'parameter_size': _('Parameter Size'),
            'quantization_level': _('Quantization Level')
        }

        if 'modified_at' in model.data and model.data['modified_at']:
            details_flow_box.append(information_bow(
                title=translation_strings['modified_at'],
                subtitle=datetime.datetime.strptime(':'.join(model.data['modified_at'].split(':')[:2]), '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
            ))

        for name, value in model.data['details'].items():
            if isinstance(value, str):
                details_flow_box.append(information_bow(
                    title=translation_strings[name] if name in translation_strings else name.replace('_', ' ').title(),
                    subtitle=value
                ))

        categories_box = Gtk.FlowBox(
            hexpand=True,
            vexpand=False,
            orientation=0,
            selection_mode=0,
            valign=1,
            halign=3
        )
        for category in self.categories:
            categories_box.append(category_pill(category, True))

        container_box = Gtk.Box(
            orientation=1,
            spacing=10,
            hexpand=True,
            vexpand=True,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12
        )

        container_box.append(details_flow_box)
        container_box.append(categories_box)

        window.model_detail_page.set_child(container_box)
        window.navigation_view_manage_models.push_by_tag('model_information')

class local_model_list(Gtk.ListBox):
    __gtype_name__ = 'AlpacaLocalModelList'

    def __init__(self):
        super().__init__(
            selection_mode=0,
            css_classes=["boxed-list"],
            visible=False
        )

    def add_model(self, model_name:str, categories:list):
        model = local_model(model_name, categories)
        GLib.idle_add(self.append, model)
        if not self.get_visible():
            self.set_visible(True)

    def remove_model(self, model_name:str):
        self.remove(next((model for model in list(self) if model.get_name() == model_name), None))

class available_model(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaAvailableModel'

    def __init__(self, model_name:str, model_author:str, model_description:str, categories:list):
        self.model_description = model_description
        self.model_title = model_name.replace("-", " ").title()
        self.model_author = model_author
        self.categories = categories
        self.image_recognition = 'vision' in categories
        model_label = Gtk.Label(
            css_classes=["heading"],
            label="<b>{}</b> <small>by {}</small>".format(self.model_title, self.model_author),
            hexpand=True,
            halign=1,
            use_markup=True,
            wrap=True,
            wrap_mode=0
        )
        description_label = Gtk.Label(
            css_classes=["subtitle"],
            label=self.model_description,
            hexpand=True,
            halign=1,
            wrap=True,
            wrap_mode=0,
        )
        categories_box = Gtk.FlowBox(
            hexpand=True,
            vexpand=True,
            orientation=0,
            selection_mode=0
        )
        description_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=5,
            orientation=1
        )
        description_box.append(model_label)
        description_box.append(description_label)
        description_box.append(categories_box)

        for category in self.categories:
            categories_box.append(category_pill(category, False))

        #if self.image_recognition: description_box.append(image_recognition_indicator)

        container_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=10,
            orientation=0,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10
        )
        next_icon = Gtk.Image.new_from_icon_name("go-next")
        next_icon.update_property([4], [_("Enter download menu for {}").format(self.model_title)])

        container_box.append(description_box)
        container_box.append(next_icon)

        super().__init__(
            child=container_box,
            name=model_name
        )

        gesture_click = Gtk.GestureClick.new()
        gesture_click.connect("pressed", lambda *_: self.show_pull_menu())

        event_controller_key = Gtk.EventControllerKey.new()
        event_controller_key.connect("key-pressed", lambda controller, key, *_: self.show_pull_menu() if key in (Gdk.KEY_space, Gdk.KEY_Return) else None)

        self.add_controller(gesture_click)
        self.add_controller(event_controller_key)

    def confirm_pull_model(self, model_name):
        threading.Thread(target=window.model_manager.pull_model, args=(model_name,)).start()
        window.navigation_view_manage_models.pop()

    def pull_model(self, model_name):
        if sys.platform in ('linux', 'linux2'):
            try:
                rematch = re.search(r':(\d*\.?\d*)([bBmM])', model_name)
                parameter_size = 0
                if rematch:
                    number = float(rematch.group(1))
                    suffix = rematch.group(2).lower()
                    parameter_size = number * 1e9 if suffix == 'b' else number * 1e6
                result = os.popen("free -b | awk '/^Mem:/ {print $7}'").read().strip()
                ram = float(result)

                if parameter_size * 2 <= ram: # multiplied by bytes_per_param (2)
                    # Probably Ok
                    self.confirm_pull_model(model_name)
                else:
                    # Might don't work
                    dialog_widget.simple(
                        _('Large Model'),
                        _("Your system's available RAM suggests that this model might be too large to run optimally. Are you sure you want to download it anyway?"),
                        lambda name=model_name: self.confirm_pull_model(name),
                        _('Download'),
                        'destructive'
                    )
            except Exception as e:
                self.confirm_pull_model(model_name)
        else:
            self.confirm_pull_model(model_name)

    def show_pull_menu(self):
        window.navigation_view_manage_models.push_by_tag('model_tags_page')
        window.navigation_view_manage_models.find_page('model_tags_page').set_title(self.get_name().replace("-", " ").title())
        window.model_link_button.set_name(available_models[self.get_name()]['url'])
        window.model_link_button.set_tooltip_text(available_models[self.get_name()]['url'])
        window.model_tag_list_box.remove_all()
        tags = available_models[self.get_name()]['tags']

        for tag_data in tags:
            if f"{self.get_name()}:{tag_data[0]}" not in window.model_manager.get_model_list():
                tag_row = Adw.ActionRow(
                    title = tag_data[0],
                    subtitle = tag_data[1],
                    name = f"{self.get_name()}:{tag_data[0]}"
                )
                download_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
                tag_row.add_suffix(download_icon)
                download_icon.update_property([4], [_("Download {}:{}").format(self.get_name(), tag_data[0])])

                gesture_click = Gtk.GestureClick.new()
                gesture_click.connect("pressed", lambda *_, name=f"{self.get_name()}:{tag_data[0]}" : self.pull_model(name))

                event_controller_key = Gtk.EventControllerKey.new()
                event_controller_key.connect("key-pressed", lambda controller, key, *_, name=f"{self.get_name()}:{tag_data[0]}" : self.confirm_pull_model(name) if key in (Gdk.KEY_space, Gdk.KEY_Return) else None)

                tag_row.add_controller(gesture_click)
                tag_row.add_controller(event_controller_key)

                window.model_tag_list_box.append(tag_row)

class available_model_list(Gtk.ListBox):
    __gtype_name__ = 'AlpacaAvailableModelList'

    def __init__(self):
        super().__init__(
            selection_mode=0,
            css_classes=["boxed-list"],
            visible=False
        )

    def add_model(self, model_name:str, model_author:str, model_description:str, categories:list):
        model = available_model(model_name, model_author, model_description, categories)
        self.append(model)
        if not self.get_visible():
            self.set_visible(True)

class model_manager_container(Gtk.Box):
    __gtype_name__ = 'AlpacaModelManagerContainer'

    def __init__(self):
        super().__init__(
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            spacing=12,
            orientation=1
        )
        
        self.pulling_list = pulling_model_list()
        self.append(self.pulling_list)
        self.local_list = local_model_list()
        self.append(self.local_list)
        self.available_list = available_model_list()
        self.append(self.available_list)
        self.model_selector = model_selector_button()
        window.title_stack.add_named(self.model_selector, 'model_selector')
        global available_models
        try:
            with open(os.path.join(source_dir, 'available_models.json'), 'r', encoding="utf-8") as f:
                available_models = json.load(f)
        except Exception as e:
            available_models = {}

    def add_local_model(self, model_name:str):
        data = None
        categories = []
        try:
            response = window.ollama_instance.request("POST", "api/show", json.dumps({"name": model_name}))
            data = json.loads(response.text)
        except Exception as e:
            data = None

        if model_name.split(':')[0] in available_models: # Same name in available models, extract categories
            categories = available_models[model_name.split(':')[0]]['categories']
        elif data and data['details']['parent_model'].split(':')[0] in available_models:
            categories = available_models[data['details']['parent_model'].split(':')[0]]['categories']

        self.local_list.add_model(model_name, [cat for cat in categories if cat not in ['small', 'medium', 'big', 'huge']])
        if not self.local_list.get_visible():
            self.local_list.set_visible(True)
        self.model_selector.add_model(model_name, data)
        window.default_model_list.append(window.convert_model_name(model_name, 0))

    def remove_local_model(self, model_name:str):
        logger.debug("Deleting model")
        response = window.ollama_instance.request("DELETE", "api/delete", json.dumps({"name": model_name}))

        if response.status_code == 200:
            self.local_list.remove_model(model_name)
            self.model_selector.remove_model(model_name)
            try:
                window.default_model_list.remove(window.default_model_list.find(model_name))
            except:
                pass
            if len(self.get_model_list()) == 0:
                self.local_list.set_visible(False)
                window.chat_list_box.update_welcome_screens(False)
            window.show_toast(_("Model deleted successfully"), window.manage_models_overlay)
        else:
            window.manage_models_dialog.close()
            window.connection_error()

    def get_selected_model(self) -> str:
        row = self.model_selector.get_popover().model_list_box.get_selected_row()
        if row:
            return row.get_name()

    def get_model_list(self) -> list:
        return [model.get_name() for model in list(self.model_selector.get_popover().model_list_box)]

    #Should only be called when the app starts
    def update_local_list(self):
        try:
            response = window.ollama_instance.request("GET", "api/tags")
            if response.status_code == 200:
                threads = []
                self.model_selector.popover.model_list_box.remove_all()
                self.local_list.remove_all()
                window.default_model_list.splice(0, len(list(window.default_model_list)), None)
                data = json.loads(response.text)
                if len(data['models']) == 0:
                    self.local_list.set_visible(False)
                else:
                    self.local_list.set_visible(True)
                    for model in data['models']:
                        thread = threading.Thread(target=self.add_local_model, args=(model['name'], ))
                        thread.start()
                        threads.append(thread)
                for thread in threads:
                    thread.join()
            else:
                window.connection_error()
        except Exception as e:
            logger.error(e)
            window.connection_error()
        window.title_stack.set_visible_child_name('model_selector' if len(window.model_manager.get_model_list()) > 0 else 'no_models')
        #window.title_stack.set_visible_child_name('model_selector')
        window.chat_list_box.update_welcome_screens(len(self.get_model_list()) > 0)

    #Should only be called when the app starts
    def update_available_list(self):
        global available_models
        for name, model_info in available_models.items():
            self.available_list.add_model(name, model_info['author'], available_models_descriptions.descriptions[name], model_info['categories'])

    def change_model(self, model_name:str):
        self.model_selector.change_model(model_name)

    def verify_if_image_can_be_used(self):
        logger.debug("Verifying if image can be used")
        selected = self.model_selector.get_popover().model_list_box.get_selected_row()
        if selected and selected.image_recognition:
            for name, content in window.attachments.items():
                if content['type'] == 'image':
                    content['button'].set_css_classes(["flat"])
            return True
        elif selected:
            for name, content in window.attachments.items():
                if content['type'] == 'image':
                    content['button'].set_css_classes(["flat", "error"])

    def pull_model(self, model_name:str, modelfile:str=None):
        if ':' not in model_name:
            model_name += ':latest'
        if model_name not in [model.get_name() for model in list(self.pulling_list)] and model_name not in [model.get_name() for model in list(self.local_list)]:
            logger.info("Pulling model: {}".format(model_name))
            model = pulling_model(model_name)
            self.pulling_list.append(model)
            if not self.pulling_list.get_visible():
                GLib.idle_add(self.pulling_list.set_visible, True)

            if modelfile:
                response = window.ollama_instance.request("POST", "api/create", json.dumps({"name": model_name, "modelfile": modelfile}), lambda data: model.update(data))
            else:
                response = window.ollama_instance.request("POST", "api/pull", json.dumps({"name": model_name}), lambda data: model.update(data))

            if response.status_code == 200 and not model.error:
                GLib.idle_add(window.show_notification, _("Task Complete"), _("Model '{}' pulled successfully.").format(model_name), Gio.ThemedIcon.new("emblem-ok-symbolic"))
                GLib.idle_add(window.show_toast, _("Model '{}' pulled successfully.").format(model_name), window.manage_models_overlay)
                self.add_local_model(model_name)
            elif response.status_code == 200:
                GLib.idle_add(window.show_notification, _("Pull Model Error"), _("Failed to pull model '{}': {}").format(model_name, model.error), Gio.ThemedIcon.new("dialog-error-symbolic"))
                GLib.idle_add(window.show_toast, _("Error pulling '{}': {}").format(model_name, model.error), window.manage_models_overlay)
            else:
                GLib.idle_add(window.show_notification, _("Pull Model Error"), _("Failed to pull model '{}' due to network error.").format(model_name), Gio.ThemedIcon.new("dialog-error-symbolic"))
                GLib.idle_add(window.show_toast, _("Error pulling '{}'").format(model_name), window.manage_models_overlay)
                GLib.idle_add(window.manage_models_dialog.close)
                GLib.idle_add(window.connection_error)

            self.pulling_list.remove(model)
            GLib.idle_add(window.chat_list_box.update_welcome_screens, len(self.get_model_list()) > 0)
            if len(list(self.pulling_list)) == 0:
                GLib.idle_add(self.pulling_list.set_visible, False)
