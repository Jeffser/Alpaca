#model_widget.py
"""
Handles the model widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk
import logging, os, datetime, re, shutil, threading, json, sys
from ..internal import config_dir, data_dir, cache_dir, source_dir
from .. import available_models_descriptions, dialogs

logger = logging.getLogger(__name__)

window = None

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

    def __init__(self, model_name:str, image_recognition:bool):
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
        self.image_recognition = image_recognition

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
        self.label = Gtk.Label(label=_('Select a Model'))
        container.append(self.label)
        container.append(Gtk.Image.new_from_icon_name("down-symbolic"))
        super().__init__(
            tooltip_text=_('Select a Model'),
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
            self.label.set_label(_("Select a Model"))
            self.set_tooltip_text(_("Select a Model"))
        window.model_manager.verify_if_image_can_be_used()

    def add_model(self, model_name:str):
        vision = False
        response = window.ollama_instance.request("POST", "api/show", json.dumps({"name": model_name}))
        if response.status_code != 200:
            logger.error(f"Status code was {response.status_code}")
            return
        try:
            vision = 'projector_info' in json.loads(response.text)
        except Exception as e:
            logger.error(f"Error fetching vision info: {str(e)}")
        model_row = model_selector_row(model_name, vision)
        GLib.idle_add(self.get_popover().model_list_box.append, model_row)
        GLib.idle_add(self.change_model, model_name)

    def remove_model(self, model_name:str):
        self.get_popover().model_list_box.remove(next((model for model in list(self.get_popover().model_list_box) if model.get_name() == model_name), None))
        self.model_changed(self.get_popover().model_list_box)

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
        stop_button.connect('clicked', lambda *_: dialogs.stop_pull_model(window, self))

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

    def update(self, data):
        if not self.get_parent():
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

class local_model(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaLocalModel'

    def __init__(self, model_name:str):
        model_title = window.convert_model_name(model_name, 0)

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

        delete_button = Gtk.Button(
            icon_name = "user-trash-symbolic",
            vexpand = False,
            valign = 3,
            css_classes = ["error", "circular"],
            tooltip_text = _("Remove '{}'").format(window.convert_model_name(model_name, 0))
        )
        delete_button.connect('clicked', lambda *_, model_name=model_name: dialogs.delete_model(window, model_name))

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
        container_box.append(delete_button)

        super().__init__(
            child=container_box,
            name=model_name
        )

class local_model_list(Gtk.ListBox):
    __gtype_name__ = 'AlpacaLocalModelList'

    def __init__(self):
        super().__init__(
            selection_mode=0,
            css_classes=["boxed-list"],
            visible=False
        )

    def add_model(self, model_name:str):
        model = local_model(model_name)
        GLib.idle_add(self.append, model)
        if not self.get_visible():
            self.set_visible(True)

    def remove_model(self, model_name:str):
        self.remove(next((model for model in list(self) if model.get_name() == model_name), None))

class available_model(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaAvailableModel'

    def __init__(self, model_name:str, model_author:str, model_description:str, image_recognition:bool):
        self.model_description = model_description
        self.model_title = model_name.replace("-", " ").title()
        self.model_author = model_author
        self.image_recognition = image_recognition
        model_label = Gtk.Label(
            css_classes=["heading"],
            label="<b>{}</b> <small>by {}</small>".format(self.model_title, self.model_author),
            hexpand=True,
            halign=1,
            use_markup=True
        )
        description_label = Gtk.Label(
            css_classes=["subtitle"],
            label=self.model_description,
            hexpand=True,
            halign=1,
            wrap=True,
            wrap_mode=0,
        )
        image_recognition_indicator = Gtk.Button(
            css_classes=["success", "pill", "image_recognition_indicator"],
            child=Gtk.Label(
                label=_("Image Recognition"),
                css_classes=["subtitle"]
            ),
            halign=1
        )
        description_box = Gtk.Box(
            hexpand=True,
            vexpand=True,
            spacing=5,
            orientation=1
        )
        description_box.append(model_label)
        description_box.append(description_label)
        if self.image_recognition: description_box.append(image_recognition_indicator)

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

    def show_pull_menu(self):
        with open(os.path.join(source_dir, 'available_models.json'), 'r', encoding="utf-8") as f:
            data = json.load(f)
            window.navigation_view_manage_models.push_by_tag('model_tags_page')
            window.navigation_view_manage_models.find_page('model_tags_page').set_title(self.get_name().replace("-", " ").title())
            window.model_link_button.set_name(data[self.get_name()]['url'])
            window.model_link_button.set_tooltip_text(data[self.get_name()]['url'])
            window.model_tag_list_box.remove_all()
            tags = data[self.get_name()]['tags']

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
                    gesture_click.connect("pressed", lambda *_, name=f"{self.get_name()}:{tag_data[0]}" : self.confirm_pull_model(name))

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

    def add_model(self, model_name:str, model_author:str, model_description:str, image_recognition:bool):
        model = available_model(model_name, model_author, model_description, image_recognition)
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

    def add_local_model(self, model_name:str):
        self.local_list.add_model(model_name)
        if not self.local_list.get_visible():
            self.local_list.set_visible(True)
        self.model_selector.add_model(model_name)

    def remove_local_model(self, model_name:str):
        logger.debug("Deleting model")
        response = window.ollama_instance.request("DELETE", "api/delete", json.dumps({"name": model_name}))

        if response.status_code == 200:
            self.local_list.remove_model(model_name)
            self.model_selector.remove_model(model_name)
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
                self.local_list.remove_all()
                data = json.loads(response.text)
                if len(data['models']) == 0:
                    self.local_list.set_visible(False)
                else:
                    self.local_list.set_visible(True)
                    for model in data['models']:
                        threading.Thread(target=self.add_local_model, args=(model['name'], )).start()
            else:
                window.connection_error()
        except Exception as e:
            logger.error(e)
            window.connection_error()
        window.title_stack.set_visible_child_name('model_selector')
        window.chat_list_box.update_welcome_screens(len(self.get_model_list()) > 0)

    #Should only be called when the app starts
    def update_available_list(self):
        with open(os.path.join(source_dir, 'available_models.json'), 'r', encoding="utf-8") as f:
            for name, model_info in json.load(f).items():
                self.available_list.add_model(name, model_info['author'], available_models_descriptions.descriptions[name], model_info['image'])

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
