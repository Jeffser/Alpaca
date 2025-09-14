# available.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .common import CategoryPill, get_local_models, prepend_added_model
from .pulling import PullingModelButton
from .added import AddedModelButton

logger = logging.getLogger(__name__)

class PullModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaPullModelButton'

    def __init__(self, tag_name:str, size:str, downloaded:bool):
        main_container = Gtk.Box(
            spacing=10
        )
        main_container.append(
            Gtk.Image.new_from_icon_name('check-plain-symbolic' if downloaded else 'folder-download-symbolic')
        )
        text_container = Gtk.Box(
            orientation=1,
            valign=3
        )
        main_container.append(text_container)
        text_container.append(
            Gtk.Label(
                label=tag_name.title(),
                css_classes=['title'],
                hexpand=True
            )
        )
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
        elif size:
            tooltip_text = _("Pull '{}'").format(tag_name.title())
        else:
            tooltip_text = _('Add Model')

        super().__init__(
            child=main_container,
            tooltip_text=tooltip_text,
            sensitive=not downloaded,
            name=tag_name
        )

class AvailableModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaAvailableModelDialog'

    def __init__(self, model):
        self.model = model

        main_container = Gtk.Box(
            spacing=10,
            hexpand=True,
            vexpand=True,
            css_classes=['p10'],
            orientation=1
        )

        title_label = Gtk.Label(
            label=self.model.model_title,
            tooltip_text=self.model.model_title,
            css_classes=['title-1'],
            wrap=True,
            vexpand=True,
            wrap_mode=2,
            justify=2
        )
        main_container.append(title_label)
        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=5,
            child_spacing=5,
            justify=1,
            natural_line_length=25,
            natural_line_length_unit=2
        )
        main_container.append(categories_box)
        for category in set(self.model.data.get('categories', [])):
            categories_box.append(CategoryPill(category, True))

        tag_list = Gtk.FlowBox(
            hexpand=True,
            max_children_per_line=3,
            selection_mode=0,
            halign=3
        )
        model_list = get_local_models(self.model.get_root())
        if len(self.model.data.get('tags', [])) > 0:
            for tag in self.model.data.get('tags', []):
                downloaded = '{}:{}'.format(self.model.get_name(), tag[0]) in list(model_list.keys())
                button = PullModelButton(tag[0], tag[1], downloaded)
                button.connect('clicked', lambda button: self.model.pull_model(button.get_name()))
                tag_list.append(button)
                button.get_parent().set_focusable(False)
        else:
            downloaded = self.model.get_name() in list(model_list.keys())
            button = PullModelButton(_('Added') if downloaded else _('Add'), None, downloaded)
            button.connect('clicked', lambda button: self.model.pull_model(None))
            tag_list.append(button)
            button.get_parent().set_focusable(False)

        main_container.append(tag_list)

        if self.model.data.get('url'):
            main_container.append(Gtk.Label(
                label=_("By downloading this model you accept the license agreement available on the model's website"),
                wrap=True,
                wrap_mode=2,
                css_classes=['dim-label', 'p10'],
                justify=2,
                use_markup=True
            ))

        tbv=Adw.ToolbarView()
        header_bar = Adw.HeaderBar(
            show_title=False
        )

        if self.model.data.get('url'):
            web_button = Gtk.Button(
                icon_name='globe-symbolic',
                tooltip_text=self.model.data.get('url')
            )
            web_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri(self.model.data.get('url')))
            header_bar.pack_start(web_button)

        if len(self.model.data.get('languages', [])) > 1:
            languages_container = Gtk.FlowBox(
                max_children_per_line=3,
                selection_mode=0
            )
            for language in ['language:' + icu.Locale(lan).getDisplayLanguage(icu.Locale(lan)).title() for lan in self.model.data.get('languages', [])]:
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
                propagate_natural_height=True
            )
        )
        super().__init__(
            child=tbv,
            title=self.model.model_title,
            width_request=360,
            height_request=240,
            follows_content_size=True,
            default_widget=list(tag_list)[0].get_child()
        )

class AvailableModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaAvailableModelButton'

    def __init__(self, name:str, data:dict):
        self.data = data
        self.model_title = prettify_model_name(name)
        container = Gtk.Box(
            orientation=1,
            spacing=5,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10
        )

        super().__init__(
            name=name,
            child=container,
            css_classes=['p0', 'card']
        )

        title_label = Gtk.Label(
            label=name.replace('-', ' ').title(),
            css_classes=['title-3'],
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            halign=1
        )
        container.append(title_label)
        description_label = Gtk.Label(
            label=self.data.get('description'),
            css_classes=['dim-label'],
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            halign=1,
            visible=self.data.get('description')
        )
        container.append(description_label)
        categories_box = Adw.WrapBox(
            hexpand=True,
            line_spacing=10,
            child_spacing=10,
            justify=0,
            halign=1,
            valign=3,
            vexpand=True,
            visible=len(self.data.get('categories', [])) > 0
        )
        container.append(categories_box)
        for category in set(self.data.get('categories', [])):
            categories_box.append(CategoryPill(category, False))

        self.connect('clicked', lambda btn: AvailableModelDialog(self).present(self.get_root()))

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)

    def get_search_string(self) -> str:
        return '{} {} {} {}'.format(self.get_name(), self.get_name().replace('-', ' ').title(), self.data.get('description'), ' '.join(self.data.get('categories', [])))

    def get_search_categories(self) -> set:
        return set(self.data.get('categories', []))

    def show_popup(self, gesture, x, y):
        if '{}:latest'.format(self.get_name()) not in list(get_local_models(self.get_root())):
            rect = Gdk.Rectangle()
            rect.x, rect.y, = x, y
            actions = [
                [
                    {
                        'label': _("Pull Latest"),
                        'callback': lambda: self.pull_model('latest'),
                        'icon': 'folder-download-symbolic'
                    }
                ]
            ]
            popup = dialog.Popover(actions)
            popup.set_parent(self)
            popup.set_pointing_to(rect)
            popup.popup()

    def pull_model(self, tag_name):
        dialog = self.get_root().get_visible_dialog()
        if dialog and isinstance(dialog, AvailableModelDialog):
            dialog.close()

        if tag_name is None:
            tag_name = ''
        model_name = '{}:{}'.format(self.get_name(), tag_name).removesuffix(':').strip()
        window = self.get_root().get_application().main_alpaca_window
        threading.Thread(target=pull_model_confirm, args=(
            model_name,
            window.get_current_instance(),
            window
        )).start()

def pull_model_confirm(model_name:str, instance, window):
    if model_name:
        if model_name not in list(get_local_models(window)):
            model = PullingModelButton(
                model_name,
                lambda model_name, window=window, instance=instance: prepend_added_model(window, AddedModelButton(model_name, instance)),
                instance,
                True
            )
            window.local_model_flowbox.prepend(model)
            GLib.idle_add(window.model_manager_stack.set_visible_child_name, 'added_models')
            GLib.idle_add(window.local_model_stack.set_visible_child_name, 'content')
            instance.pull_model(model_name, model.update_progressbar)
