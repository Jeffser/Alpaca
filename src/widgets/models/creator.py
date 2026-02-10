# creator.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, GObject
import logging, os, re, datetime, threading, sys, glob, icu, base64, hashlib, importlib.util
from ...constants import STT_MODELS, TTS_VOICES, data_dir, cache_dir
from ...sql_manager import prettify_model_name, Instance as SQL
from .. import dialog, attachments
from .basic import BasicModelButton
from .added import list_from_selector, AddedModelRow, AddedModelDialog, get_model
from .common import CategoryPill, remove_added_model

logger = logging.getLogger(__name__)

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/models/creator_dialog.ui')
class ModelCreatorDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaModelCreatorDialog'

    toast_overlay = Gtk.Template.Child()
    base_el = Gtk.Template.Child()
    name_el = Gtk.Template.Child()
    tag_el = Gtk.Template.Child()
    context_attachment_button = Gtk.Template.Child()
    context_attachment_container = Gtk.Template.Child()
    context_el = Gtk.Template.Child()
    template_group = Gtk.Template.Child()
    template_el = Gtk.Template.Child()
    imagination_el = Gtk.Template.Child()
    focus_el = Gtk.Template.Child()
    num_ctx_el = Gtk.Template.Child()

    def __init__(self, instance, base_row:AddedModelRow=None, gguf_path:str=""):
        super().__init__()
        self.instance = instance
        self.gguf_path = gguf_path

        self.name_el.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))
        self.tag_el.get_delegate().connect("insert-text", lambda *_: self.check_alphanumeric(*_, ['-', '.', '_', ' ']))

        self.context_attachment_button.connect('clicked', lambda *_: self.context_attachment_container.attachment_request(True))

        self.context_attachment_container.force_dialog = True

        self.template_group.set_visible(bool(self.gguf_path))

        if self.gguf_path:
            string_list = Gtk.StringList()
            string_list.append('GGUF')
            self.base_el.set_model(string_list)
            self.base_el.set_subtitle(self.gguf_path)
        else:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
            factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().name))
            self.base_el.set_factory(factory)
            if base_row:
                self.base_el.set_model(Gio.ListStore.new(AddedModelRow))
                self.base_el.get_model().append(base_row)
            else:
                self.base_el.set_model(get_model())

    def show_toast(self, message:str):
        toast = Adw.Toast(
            title=message,
            timeout=2
        )
        self.toast_overlay.add_toast(toast)

    def check_alphanumeric(self, editable, text, length, position, allowed_chars):
        if length == 1:
            new_text = ''.join([char for char in text if char.isalnum() or char in allowed_chars])
            if new_text != text:
                editable.stop_emission_by_name("insert-text")

    @Gtk.Template.Callback()
    def base_changed(self, combo, gparam):
        if self.gguf_path:
            self.name_el.set_text(os.path.basename(self.gguf_path).removesuffix('.gguf'))
            return
        item = self.base_el.get_selected_item()
        if not item:
            return
        model = item.model
        if not model:
            return

        self.name_el.set_text(prettify_model_name(model.get_name(), True)[0])

        system = model.data.get('system')
        if system:
            for attachment in list(self.context_attachment_container.container):
                attachment.unparent()

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
            context_buffer = self.context_el.get_buffer()
            context_buffer.delete(context_buffer.get_start_iter(), context_buffer.get_end_iter())
            context_buffer.insert_at_cursor(system, len(system.encode('utf-8')))

        modelfile = model.data.get('modelfile')
        if modelfile:
            for line in modelfile.splitlines():
                if line.startswith('PARAMETER top_k'):
                    top_k = int(line.split(' ')[2])
                    self.imagination_el.set_value(top_k)
                elif line.startswith('PARAMETER top_p'):
                    top_p = int(float(line.split(' ')[2]) * 100)
                    self.focus_el.set_value(top_p)
                elif line.startswith('PARAMETER num_ctx'):
                    num_ctx = int(line.split(' ')[2])
                    self.num_ctx_el.set_value(num_ctx)


    @Gtk.Template.Callback()
    def cancel(self, button):
        self.close()

    @Gtk.Template.Callback()
    def save(self, button):
        main_name = self.name_el.get_text()
        if not main_name:
            self.show_toast(_("Please add a name"))
            return

        tag_name = self.tag_el.get_text() or 'custom'
        model_name = '{}:{}'.format(main_name, tag_name).strip().replace(' ', '-').lower()
        pretty_name = prettify_model_name(model_name)

        for row in list_from_selector():
            if model_name == row:
                self.show_toast(_("Model name is already in use"))
                return

        system_message = []
        for attachment in self.context_attachment_container.get_content():
            system_message.append('```{}\n{}\n```'.format(attachment.get('name'), attachment.get('content').strip()))
        context_buffer = self.context_el.get_buffer()
        system_message.append(context_buffer.get_text(context_buffer.get_start_iter(), context_buffer.get_end_iter(), False).replace('"', '\\"').strip())
        system_message = '\n\n'.join(system_message).strip()

        template_buffer = self.template_el.get_buffer()
        template_text = template_buffer.get_text(template_buffer.get_start_iter(), template_buffer.get_end_iter(), False).replace('"', '\\"').strip()

        top_k = self.imagination_el.get_value()
        top_p = self.focus_el.get_value() / 100
        num_ctx = self.num_ctx_el.get_value()

        # SAVE BEGGINS

        data_json = {
            'model': model_name,
            'system': system_message,
            'parameters': {
                'top_k': top_k,
                'top_p': top_p,
                'num_ctx': num_ctx
            },
            "template": template_text,
            'stream': True
        }

        if not self.gguf_path:
            data_json['from'] = self.base_el.get_selected_item().model.get_name()

        threading.Thread(target=self.create_model, args=(data_json,), daemon=True).start()
        self.close()

    def create_model(self, data:dict):
        window = self.get_root().get_application().get_main_window()
        if not data.get('model'):
            return

        model_el = window.model_manager.create_added_model(
            model_name=data.get('model'),
            instance=self.instance,
            append_row=False
        )
        model_el.update_progressbar(1)

        if self.gguf_path:
            try:
                model_el.append_progress_line('Uploading GGUF to Ollama instance')
                digest = self.instance.upload_gguf(self.gguf_path)
                data['files'] = {os.path.split(self.gguf_path)[1]: digest}
            except Exception as e:
                logger.error(e)
                window.model_manager.added_model_flowbox.remove(model_el.get_parent())
                window.model_manager.update_added_visibility()
                return
        self.instance.create_model(data, model_el)

