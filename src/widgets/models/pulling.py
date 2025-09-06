# pulling.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .common import get_local_models

logger = logging.getLogger(__name__)

class PullingModelDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaPullingModelDialog'

    def __init__(self, model):
        self.model = model

        main_container = Gtk.Box(
            orientation=1,
            spacing=20,
            valign=3,
            css_classes=['p10']
        )
        title_label = Gtk.Label(
            label=prettify_model_name(self.model.get_name(), True)[0],
            css_classes=['title-1'],
            wrap=True,
            wrap_mode=2,
            justify=2
        )
        main_container.append(title_label)
        tag_name = prettify_model_name(self.model.get_name(), True)[1]
        if tag_name:
            subtitle_label = Gtk.Label(
                label=tag_name,
                css_classes=['dim-label'],
                wrap=True,
                wrap_mode=2,
                justify=2
            )
            main_container.append(subtitle_label)


        self.status_label = Gtk.Label(
            wrap=True,
            wrap_mode=2,
            justify=2,
            label=_("Downloading...")
        )
        status_container = Gtk.Box(
            orientation=1,
            spacing=5,
            css_classes=['card', 'p10']
        )
        status_container.append(self.status_label)

        self.progressbar = Gtk.ProgressBar(
            show_text=self.model.cancellable,
            pulse_step=0.5
        )
        GLib.idle_add(self.progressbar.pulse)
        status_container.append(self.progressbar)

        main_container.append(status_container)

        stop_button = Gtk.Button(
            child=Adw.ButtonContent(
                icon_name='media-playback-stop-symbolic',
                label=_('Stop Download')
            ),
            tooltip_text=_('Stop Download'),
            css_classes=['destructive-action'],
            halign=3
        )
        if self.model.cancellable:
            stop_button.connect('clicked', lambda button: self.model.prompt_stop_download())
            main_container.append(stop_button)

        tbv=Adw.ToolbarView()
        header_bar = Adw.HeaderBar(
            show_title=False
        )
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
            default_widget=stop_button
        )

class PullingModelButton(Gtk.Button):
    __gtype_name__ = 'AlpacaPullingModelButton'

    def __init__(self, name:str, success_callback:callable, instance=None, cancellable:bool=True):
        self.model_title = prettify_model_name(name)
        self.instance = instance
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
            label=prettify_model_name(name, True)[0],
            css_classes=['title-3'],
            ellipsize=3,
            hexpand=True,
            halign=1
        )
        container.append(title_label)

        if cancellable:
            subtitle_text = prettify_model_name(name, True)[1]
        else: # Probably STT
            subtitle_text = _("Dictation Model")
        subtitle_label = Gtk.Label(
            label=subtitle_text,
            css_classes=['dim-label'],
            ellipsize=3,
            hexpand=True,
            halign=1,
            visible=prettify_model_name(name, True)[1] or not cancellable
        )
        container.append(subtitle_label)
        self.progressbar = Gtk.ProgressBar(pulse_step=0.5)
        GLib.idle_add(self.progressbar.pulse)
        container.append(self.progressbar)
        self.digests = []
        self.success_callback = success_callback
        self.cancellable = cancellable

        self.dialog = PullingModelDialog(self)

        if self.cancellable:
            self.connect('clicked', lambda btn: self.dialog.present(self.get_root()))

            self.gesture_click = Gtk.GestureClick(button=3)
            self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
            self.add_controller(self.gesture_click)
            self.gesture_long_press = Gtk.GestureLongPress()
            self.gesture_long_press.connect("pressed", self.show_popup)
            self.add_controller(self.gesture_long_press)

    def get_search_string(self) -> str:
        return '{} {}'.format(self.get_name(), self.model_title)

    def get_search_categories(self) -> set:
        return set([c for c in available_models.get(self.get_name().split(':')[0], {}).get('categories', []) if c not in ('small', 'medium', 'big', 'huge')])

    def show_popup(self, gesture, x, y):
        if '{}:latest'.format(self.get_name()) not in list(get_local_models(self.get_root())):
            rect = Gdk.Rectangle()
            rect.x, rect.y, = x, y
            actions = [
                [
                    {
                        'label': _('Stop Download'),
                        'callback': lambda: self.prompt_stop_download(),
                        'icon': 'media-playback-stop-symbolic'
                    }
                ]
            ]
            popup = dialog.Popover(actions)
            popup.set_parent(self)
            popup.set_pointing_to(rect)
            popup.popup()

    def prompt_stop_download(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Stop Download?'),
            body = _("Are you sure you want to stop pulling '{}'?").format(prettify_model_name(self.get_name())),
            callback = self.stop_download,
            button_name = _('Stop'),
            button_appearance = 'destructive'
        )

    def stop_download(self):
        local_model_flowbox = self.get_parent().get_parent()
        if self.dialog.get_root():
            self.dialog.close()
        if len(list(local_model_flowbox)) == 1:
            self.get_root().get_application().main_alpaca_window.local_model_stack.set_visible_child_name('no-models')
        local_model_flowbox.remove(self.get_parent())

    def update_progressbar(self, data:dict):
        if not self.get_parent():
            logger.info("Pulling of '{}' was canceled".format(self.get_name()))
            if self.instance and self.instance.properties.get('model_directory'):
                directory = os.path.join(self.instance.properties.get('model_directory'), 'blobs')
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
                GLib.idle_add(self.dialog.progressbar.set_fraction, data.get('completed', 0) / data.get('total', 0))
            else:
                GLib.idle_add(self.progressbar.pulse)
                GLib.idle_add(self.dialog.progressbar.pulse)

            label_text = [line for line in self.dialog.status_label.get_label().split('\n') if line != '']
            if data.get('status') and (len(label_text) == 0 or label_text[-1] != data.get('status')):
                label_text.append(data.get('status'))
                GLib.idle_add(self.dialog.status_label.set_label, '\n'.join(label_text))

            if data.get('digest') and data.get('digest') not in self.digests:
                self.digests.append(data.get('digest').replace(':', '-'))

            if data.get('status') == 'success':
                new_model = self.success_callback(self.get_name())
                if len(get_local_models(self.get_root())) > 0:
                    self.get_root().get_application().main_alpaca_window.title_stack.set_visible_child_name('model-selector')
                if self.dialog.get_root():
                    self.dialog.close()

                dialog.show_notification(
                    root_widget=self.get_root(),
                    title=_('Download Completed'),
                    body=_("Model '{}' downloaded successfully.").format(self.model_title),
                    icon=Gio.ThemedIcon.new('document-save-symbolic')
                )
                self.get_parent().get_parent().remove(self.get_parent())
                sys.exit()
