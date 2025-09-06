# creator.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .common import CategoryPill, get_local_models, prepend_added_model
from .pulling import PullingModelButton
from .added import AddedModelButton

logger = logging.getLogger(__name__)

class ModelCreatorDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaModelCreatorDialog'

    def __init__(self, instance, base_source:str=None, using_gguf:bool=False):
        self.instance = instance
        self.base_source = base_source
        self.using_gguf = using_gguf

        pp = Adw.PreferencesPage()
        pg = Adw.PreferencesGroup(
            title=_('Identity')
        )
        pp.add(pg)

        #BASE
        self.base_element = Adw.ComboRow(
            title=_('Base')
        )
        self.base_element.connect('notify::selected-item', lambda *_: self.base_changed())
        pg.add(self.base_element)

        #PROFILE PICTURE
        self.profile_picture_element = Adw.ActionRow(
            title=_('Profile Picture')
        )
        profile_picture_button = Gtk.Button(
            icon_name='document-open-symbolic',
            tooltip_text=_('Open File'),
            css_classes=['flat'],
            valign=3
        )
        profile_picture_button.connect('clicked', lambda btn: self.load_profile_picture())
        self.profile_picture_element.add_suffix(profile_picture_button)
        pg.add(self.profile_picture_element)

        #NAME
        self.name_element = Adw.EntryRow(
            title=_('Name')
        )
        pg.add(self.name_element)

        #TAG
        self.tag_element = Adw.EntryRow(
            title=_('Tag')
        )
        pg.add(self.tag_element)

        self.name_element.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))
        self.tag_element.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))

        context_attachment_button = Gtk.Button(
            valign=3,
            icon_name='chain-link-loose-symbolic',
            tooltip_text=_('Add Files'),
            css_classes=['flat']
        )
        context_attachment_button.connect('clicked', lambda button: self.context_attachment_container.attachment_request(True))

        pg = Adw.PreferencesGroup(
            title=_('Context'),
            description=_('Describe the desired behavior of the model in its primary language (typically English).'),
            header_suffix=context_attachment_button
        )
        pp.add(pg)

        #CONTEXT
        self.context_attachment_container = attachments.GlobalAttachmentContainer()
        self.context_attachment_container.force_dialog = True
        self.context_attachment_container.set_margin_bottom(10)
        pg.add(self.context_attachment_container)

        self.context_element = Gtk.TextView(
            wrap_mode=3,
            accepts_tab=False,
            overflow=1,
            vexpand=True,
            css_classes=['p10', 'modelfile_textview']
        )

        context_sw = Gtk.ScrolledWindow(
            min_content_height=100,
            vexpand=True,
            propagate_natural_height=True,
            child=self.context_element,
            overflow=1,
            css_classes=['card', 'undershoot-bottom']
        )
        pg.add(context_sw)

        pg = Adw.PreferencesGroup(
            title=_('Behavior')
        )
        pp.add(pg)

        #IMAGINATION
        self.imagination_element = Adw.SpinRow(
            title=_('Imagination'),
            subtitle=_('A higher number results in more diverse answers from the model. (top_k)'),
            digits=0,
            numeric=True,
            snap_to_ticks=True,
            adjustment=Gtk.Adjustment(
                lower=0,
                upper=100,
                step_increment=1,
                value=40
            )
        )
        pg.add(self.imagination_element)

        #FOCUS
        self.focus_element = Adw.SpinRow(
            title=_('Focus'),
            subtitle=_('A higher number widens the amount of possible answers. (top_p)'),
            digits=0,
            numeric=True,
            snap_to_ticks=True,
            adjustment=Gtk.Adjustment(
                lower=0,
                upper=100,
                step_increment=1,
                value=90
            )
        )
        pg.add(self.focus_element)

        self.num_ctx_element = Adw.SpinRow(
            title=_('Context Window Size'),
            subtitle=_('Controls how many tokens (pieces of text) the model can process and remember at once.'),
            name='num_ctx',
            digits=0,
            numeric=True,
            snap_to_ticks=True,
            adjustment=Gtk.Adjustment(
                value=16384,
                lower=512,
                upper=131072,
                step_increment=512
            )
        )
        pg.add(self.num_ctx_element)

        tbv=Adw.ToolbarView()

        cancel_button = Gtk.Button(
            label=_('Cancel'),
            tooltip_text=_('Cancel'),
            css_classes=['raised']
        )
        cancel_button.connect('clicked', lambda button: self.close())

        save_button = Gtk.Button(
            label=_('Save'),
            tooltip_text=_('Save'),
            css_classes=['suggested-action']
        )
        save_button.connect('clicked', lambda button: self.save())

        hb = Adw.HeaderBar(
            show_start_title_buttons=False,
            show_end_title_buttons=False
        )
        hb.pack_start(cancel_button)
        hb.pack_end(save_button)

        tbv.add_top_bar(hb)
        tbv.set_content(pp)

        super().__init__(
            child=tbv,
            title=_('Create Model'),
            width_request=360,
            height_request=240,
            content_width=500,
            content_height=900
        )
        self.connect('map', self.on_map)

    def on_map(self, user_data):
        # Update Base
        if self.using_gguf:
            string_list = Gtk.StringList()
            string_list.append('GGUF')
            self.base_element.set_model(string_list)
            self.base_element.set_subtitle(self.base_source)
        elif self.base_source:
            string_list = Gtk.StringList()
            string_list.append(self.base_source)
            self.base_element.set_model(string_list)
        else:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
            factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))
            self.base_element.set_factory(factory)
            string_list = Gtk.StringList()
            for value in get_local_models(self.get_root()).values():
                string_list.append(value.model_title)
            self.base_element.set_model(string_list)

    def load_profile_picture(self):
        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = [file_filter],
            callback = lambda file: self.profile_picture_element.set_subtitle(file.get_path() if file else '')
        )

    def base_changed(self):
        pretty_name = self.base_element.get_selected_item().get_string()
        if pretty_name != 'GGUF' and not self.base_element.get_subtitle():
            self.tag_element.set_text('custom')

            system = None
            modelfile = None

            found_models = [model for model in list(get_local_models(self.get_root()).values()) if model.model_title == pretty_name]
            if len(found_models) > 0:
                self.name_element.set_text(found_models[0].get_name().split(':')[0])
                system = found_models[0].data.get('system')
                modelfile = found_models[0].data.get('modelfile')

            if system:
                for attachment in list(self.context_attachment_container.container):
                    attachment.get_parent().remove(attachment)

                pattern = re.compile(r"```(.+?)\n(.*?)```", re.DOTALL)
                matches = pattern.finditer(system)
                for match in matches:
                    attachment = attachments.Attachment(
                        file_id='-1',
                        file_name=match.group(1).strip(),
                        file_type='plain_text',
                        file_content=match.group(2).strip()
                    )
                    self.context_attachment_container.add_attachment(attachment)

                system = pattern.sub('', system).strip()
                context_buffer = self.context_element.get_buffer()
                context_buffer.delete(context_buffer.get_start_iter(), context_buffer.get_end_iter())
                context_buffer.insert_at_cursor(system, len(system.encode('utf-8')))

            if modelfile:
                for line in modelfile.splitlines():
                    if line.startswith('PARAMETER top_k'):
                        top_k = int(line.split(' ')[2])
                        self.imagination_element.set_value(top_k)
                    elif line.startswith('PARAMETER top_p'):
                        top_p = int(float(line.split(' ')[2]) * 100)
                        self.focus_element.set_value(top_p)
                    elif line.startswith('PARAMETER num_ctx'):
                        num_ctx = int(line.split(' ')[2])
                        self.num_ctx_element.set_value(num_ctx)

    def save(self):
        main_name = self.name_element.get_text()
        tag_name = self.tag_element.get_text()
        model_name = '{}:{}'.format(main_name, tag_name if tag_name else 'latest').strip().replace(' ', '-').lower()
        pretty_name = prettify_model_name(model_name)

        profile_picture = self.profile_picture_element.get_subtitle()

        context_buffer = self.context_element.get_buffer()
        system_message = []

        for attachment in self.context_attachment_container.get_content():
            system_message.append('```{}\n{}\n```'.format(attachment.get('name'), attachment.get('content').strip()))

        system_message.append(context_buffer.get_text(context_buffer.get_start_iter(), context_buffer.get_end_iter(), False).replace('"', '\\"'))
        system_message = '\n\n'.join(system_message).strip()

        top_k = self.imagination_element.get_value()
        top_p = self.focus_element.get_value() / 100
        num_ctx = self.num_ctx_element.get_value()

        found_models = [model for model in list(get_local_models(self.get_root()).values()) if model.model_title == pretty_name]
        if len(found_models) == 0:
            if profile_picture:
                SQL.insert_or_update_model_picture(model_name, attachments.extract_image(profile_picture, 480))

            data_json = {
                'model': model_name,
                'system': system_message,
                'parameters': {
                    'top_k': top_k,
                    'top_p': top_p,
                    'num_ctx': num_ctx
                },
                'stream': True
            }

            if self.base_element.get_subtitle():
                gguf_path = self.base_element.get_subtitle()
                threading.Thread(target=self.create_model, args=(data_json, gguf_path)).start()
            else:
                pretty_name = self.base_element.get_selected_item().get_string()
                found_models = [model for model in list(get_local_models(self.get_root()).values()) if model.model_title == pretty_name]
                if len(found_models) > 0:
                    data_json['from'] = found_models[0].get_name()
                    threading.Thread(target=self.create_model, args=(data_json,)).start()
            self.close()

    def create_model(self, data:dict, gguf_path:str=None):
        window = self.get_root().get_application().main_alpaca_window
        if data.get('model') and data.get('model') not in list(get_local_models(self.get_root()).keys()):
            model = PullingModelButton(
                data.get('model'),
                lambda model_name, window=window, instance=self.instance: prepend_added_model(window, AddedModelButton(model_name, instance)),
                self.instance
            )
            window.local_model_flowbox.prepend(model)
            window.model_manager_stack.set_visible_child_name('added_models')
            window.local_model_stack.set_visible_child_name('content')
            if gguf_path:
                try:
                    with open(gguf_path, 'rb', buffering=0) as f:
                        model.update_progressbar({'status': 'Generating sha256'})
                        sha256 = hashlib.file_digest(f, 'sha256').hexdigest()

                    if not self.instance.gguf_exists(sha256):
                        model.update_progressbar({'status': 'Uploading GGUF to Ollama instance'})
                        self.instance.upload_gguf(gguf_path, sha256)
                        data['files'] = {os.path.split(gguf_path)[1]: 'sha256:{}'.format(sha256)}
                except Exception as e:
                    logger.error(e)
                    GLib.idle_add(window.local_model_flowbox.remove, model.get_parent())
                    return
            self.instance.create_model(data, model.update_progressbar)

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        if length == 1:
            new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
            if new_text != text:
                editable.stop_emission_by_name("insert-text")

