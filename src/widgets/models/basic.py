# basic.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util, json
from PIL import Image
from ...constants import STT_MODELS, TTS_VOICES, REMBG_MODELS, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .added import AddedModelRow, AddedModelDialog, append_to_model_selector, list_from_selector
from .common import CategoryPill, get_available_models_data, prompt_existing, remove_added_model

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/basic_dialog.ui')
class BasicModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaBasicModelDialog'

    remove_button = Gtk.Template.Child()
    webpage_button = Gtk.Template.Child()
    status_page = Gtk.Template.Child()

    def __init__(self, model, description:str="", size:str="", url:str=""):
        super().__init__()
        self.model = model
        self.status_page.set_icon_name(self.model.image.get_icon_name())

        self.status_page.set_title(self.model.model_title)
        if description:
            self.status_page.set_description(description),
        if size:
            self.status_page.set_child(
                Gtk.Label(
                    label=size,
                    css_classes=['dim-label']
                )
            )
        self.remove_button.set_visible(self.model.remove_callback)
        if url:
            self.webpage_button.set_tooltip_text(url)
        self.webpage_button.set_visible(url)

    @Gtk.Template.Callback()
    def prompt_remove_model(self, button):
        self.model.prompt_remove_model()

    @Gtk.Template.Callback()
    def webpage_requested(self, button):
        Gio.AppInfo.launch_default_for_uri(button.get_tooltip_text())

class PullModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaPullModelButton'

    def __init__(self, tag_name:str, size:str, downloaded:bool):
        main_container = Gtk.Box(
            spacing=10
        )

        is_cloud = not size or size == 'cloud'

        add_icon = 'cloud-filled-symbolic' if is_cloud else 'folder-download-symbolic'
        main_container.append(
            Gtk.Image.new_from_icon_name('check-plain-symbolic' if downloaded else add_icon)
        )
        text_container = Gtk.Box(
            orientation=1,
            valign=3
        )
        main_container.append(text_container)
        text_container.append(
            Gtk.Label(
                label=tag_name.title() or 'Cloud',
                css_classes=['title'],
                hexpand=True
            )
        )
        if not is_cloud:
            text_container.append(
                Gtk.Label(
                    label=size,
                    css_classes=['dimmed', 'caption'],
                    hexpand=True,
                    visible=bool(size)
                )
            )
        tooltip_text = ''
        if downloaded:
            tooltip_text = _('Already Added')
        elif not is_cloud:
            tooltip_text = _("Pull '{}'").format(tag_name.title())
        else:
            tooltip_text = _('Add Model')

        super().__init__(
            child=main_container,
            tooltip_text=tooltip_text,
            sensitive=not downloaded,
            name=tag_name
        )

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/pulling_dialog.ui')
class PullingModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaPullingModelDialog'

    stop_button = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()

    def __init__(self, model):
        super().__init__()
        self.model = model

        model_name, model_tag = prettify_model_name(self.model.get_name(), True)
        self.status_page.set_title(model_name)
        self.status_page.set_description(model_tag)

        self.progressbar.set_fraction(self.model.progressbar.get_fraction())
        self.update_label()

    def update_label(self):
        self.status_label.set_text('\n'.join(self.model.progress_lines))
        self.status_label.set_visible(len(self.model.progress_lines) > 0)

    @Gtk.Template.Callback()
    def prompt_stop_download(self, button):
        pass

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/available_dialog.ui')
class AvailableModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaAvailableModelDialog'

    web_button = Gtk.Template.Child()
    language_button = Gtk.Template.Child()
    language_flowbox = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    category_container = Gtk.Template.Child()
    tag_container = Gtk.Template.Child()
    license_warning = Gtk.Template.Child()

    def __init__(self, model):
        super().__init__()
        self.model = model

        self.title_label.set_label(self.model.model_title)
        for category in set(self.model.data.get('categories', [])):
            self.category_container.append(CategoryPill(category, True))

        model_list = list_from_selector()
        if len(self.model.data.get('tags', [])) > 0:
            for tag in self.model.data.get('tags', []):
                if tag[0]:
                    downloaded = '{}:{}'.format(self.model.get_name(), tag[0]) in list(model_list.keys())
                else:
                    downloaded = self.model.get_name() in list(model_list.keys())

                button = PullModelButton(tag[0], tag[1], downloaded)
                if button.get_sensitive():
                    button.connect('clicked', lambda button: self.pull_model(button.get_name()))
                self.tag_container.append(button)
                button.get_parent().set_focusable(False)
        else:
            downloaded = self.model.get_name() in list(model_list.keys())
            button = PullModelButton(_('Added') if downloaded else _('Add'), None, downloaded)
            button.connect('clicked', lambda button: self.pull_model())
            self.tag_container.append(button)
            button.get_parent().set_focusable(False)

        self.license_warning.set_visible(self.model.data.get('url'))
        self.web_button.set_visible(self.model.data.get('url'))
        self.web_button.set_tooltip_text(self.model.data.get('url'))
        self.language_button.set_visible(len(self.model.data.get('languages', [])) > 1)
        for language in ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in self.model.data.get('languages', [])]:
            self.language_flowbox.append(CategoryPill(language, True))

    def pull_model(self, tag:str=None):
        window = self.get_root().get_application().get_main_window()
        self.close()
        if tag is None:
            tag = ''
        model_name = '{}:{}'.format(self.model.get_name(), tag).removesuffix(':').strip()
        confirm_pull_model(
            window=window,
            model_name=model_name
        )

    @Gtk.Template.Callback()
    def webpage_requested(self, button):
        Gio.AppInfo.launch_default_for_uri(button.get_tooltip_text())

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/basic_button.ui')
class BasicModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaBasicModelButton'

    image = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    subtitle_label = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    category_container = Gtk.Template.Child()

    def __init__(self, model_name:str, subtitle:str=None, icon_name:str=None, instance=None, dialog_callback:callable=None, remove_callback:callable=None, data:dict={}):
        super().__init__()
        self.instance = instance
        self.dialog_callback = dialog_callback
        self.remove_callback = remove_callback

        self.set_name(model_name)
        self.model_title, tag = prettify_model_name(self.get_name(), True)
        self.title_label.set_label(self.model_title)
        self.set_sensitive(self.dialog_callback)
        self.pulling_dialog = None # created when needed
        self.progress_lines = [] # for the pulling_dialog
        self.set_tooltip_text(prettify_model_name(self.get_name(), False))

        if self.instance:
            self.data = self.instance.get_model_info(model_name)
            self.row = AddedModelRow(self)
        else:
            self.data = data
            self.row = None

        if subtitle:
            self.set_subtitle(subtitle)
        else:
            family = prettify_model_name(self.data.get('details', {}).get('family'))
            if family and family.upper().replace(' ', '').replace('-', '') != self.model_title.upper().replace(' ', '').replace('-', '') and tag:
                self.set_subtitle('{} • {}'.format(family, tag))
            elif tag:
                self.set_subtitle(tag)
            elif family:
                self.set_subtitle(family)

        self.category_container.set_visible(len(self.data.get('categories', [])))
        for category in set(self.data.get('categories', [])):
            self.category_container.append(CategoryPill(category, False))

        if icon_name:
            self.set_image_icon_name(icon_name)
        elif self.instance:
            self.update_profile_picture()

    def get_search_string(self) -> str:
        return '{} {} {}'.format(self.get_name(), self.model_title, self.data.get('system', None))

    def get_search_categories(self) -> set:
        available_models_data = get_available_models_data()
        return set([c for c in available_models_data.get(self.get_name().split(':')[0], {}).get('categories', []) if c not in ('small', 'medium', 'big', 'huge')])

    def get_vision(self) -> bool:
        return 'vision' in self.data.get('capabilities', [])

    def update_profile_picture(self):
        self.set_image_data(SQL.get_model_preferences(self.get_name()).get('picture'))

    def set_subtitle(self, subtitle:str):
        self.subtitle_label.set_label(subtitle)
        self.subtitle_label.set_visible(subtitle)

    def set_image_data(self, b64_data:str):
        if b64_data:
            image_data = base64.b64decode(b64_data)
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(image_data))
            self.image.set_from_paintable(texture)
        else:
            self.image.set_from_paintable(None)

        self.image.set_size_request(64, 64)
        self.image.set_pixel_size(64)
        self.image.set_visible(b64_data)
        self.image.set_margin_start(0)
        self.image.set_margin_end(0)

    def set_image_icon_name(self, icon_name:str):
        if icon_name:
            self.image.set_from_icon_name(icon_name)
        self.image.set_size_request(-1, -1)
        self.image.set_pixel_size(-1)
        self.image.set_visible(icon_name)
        self.image.set_margin_start(10)
        self.image.set_margin_end(10)

    def prompt_create_child(self):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, AddedModelDialog):
            dialog.close()
        prompt_existing(self.get_root(), self.instance, self.row)

    def prompt_remove_model(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Remove Model?'),
            body = _("Are you sure you want to remove '{}'?").format(self.model_title),
            callback = self.remove_model,
            button_name = _('Remove'),
            button_appearance = 'destructive'
        )

    def remove_model(self):
        root = self.get_root()
        dialog = root.get_visible_dialog()
        if dialog:
            dialog.close()
        self.remove_callback(self)
        self.get_parent().get_parent().remove(self.get_parent())
        root.model_manager.update_added_visibility()

    def update_progressbar(self, prc:float):
        #prc:float = -1 or 0 to 1

        if prc == -1:
            GLib.idle_add(self.progressbar.set_visible, False)
            if self.pulling_dialog and self.pulling_dialog.get_root():
                self.pulling_dialog.close()
            if self.row:
                append_to_model_selector(self.row)
            if self.instance:
                self.data = self.instance.get_model_info(self.get_name())
        else:
            GLib.idle_add(self.progressbar.set_visible, True)

        if prc == 1:
            GLib.idle_add(self.progressbar.pulse)
            if self.pulling_dialog:
                GLib.idle_add(self.pulling_dialog.progressbar.pulse)
        elif prc > 0 and prc < 1:
            GLib.idle_add(self.progressbar.set_fraction, prc)
            if self.pulling_dialog:
                GLib.idle_add(self.pulling_dialog.progressbar.set_fraction, prc)

    def append_progress_line(self, line:str=""):
        if line and line not in self.progress_lines:
            self.progress_lines.append(line)
            if self.pulling_dialog:
                GLib.idle_add(self.pulling_dialog.update_label)

    @Gtk.Template.Callback()
    def on_click(self, button):
        if self.progressbar.get_visible():
            if not self.pulling_dialog:
                self.pulling_dialog = PullingModelDialog(self)
            self.pulling_dialog.present(self.get_root())
        else:
            self.dialog_callback(self).present(self.get_root())

    @Gtk.Template.Callback()
    def show_popup(self, *args):
        rect = Gdk.Rectangle()
        if len(args) == 4:
            rect.x, rect.y = args[2], args[3]
        else:
            rect.x, rect.y = args[1], args[2]

        actions = [[]]

        if not self.progressbar.get_visible():
            if self.instance and self.instance.instance_type in ('ollama', 'ollama:managed'):
                actions[0].append({
                    'label': _('Create Child'),
                    'callback': self.prompt_create_child,
                    'icon': 'list-add-symbolic'
                })
            if self.remove_callback:
                actions[0].append({
                    'label': _('Remove Model'),
                    'callback': self.prompt_remove_model,
                    'icon': 'user-trash-symbolic'
                })

        if len(actions[0]) > 0:
            popup = dialog.Popover(actions)
            popup.set_parent(self)
            popup.set_pointing_to(rect)
            popup.popup()

def confirm_pull_model(window, model_name:str):
    if model_name and model_name not in list(list_from_selector()):
        instance = window.get_current_instance()
        if instance:
            model_el = window.model_manager.create_added_model(
                model_name=model_name,
                instance=instance,
                append_row=False
            )
            model_el.update_progressbar(1)
            threading.Thread(target=instance.pull_model, args=(model_el,)).start()
            window.model_manager.view_stack.set_visible_child_name('added_models')
