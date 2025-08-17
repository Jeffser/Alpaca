# __init__.py

from gi.repository import Adw, Gtk, GLib, Gio

import os, shutil, json, re, logging
from ...sql_manager import generate_uuid, generate_numbered_name, prettify_model_name, Instance as SQL
from .. import dialog
from .ollama_instances import BaseInstance as BaseOllama
from .openai_instances import BaseInstance as BaseOpenAI

logger = logging.getLogger(__name__)

override_urls = {
    'HSA_OVERRIDE_GFX_VERSION': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#overrides',
    'CUDA_VISIBLE_DEVICES': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#gpu-selection',
    'ROCR_VISIBLE_DEVICES': 'https://github.com/ollama/ollama/blob/main/docs/gpu.md#gpu-selection-1',
    'OLLAMA_ORIGINS': 'https://github.com/ollama/ollama/blob/main/docs/faq.md#how-can-i-allow-additional-web-origins-to-access-ollama'
}

class InstancePreferencesGroup(Adw.Dialog):
    __gtype_name__ = 'AlpacaInstancePreferencesGroup'

    def __init__(self, instance):
        self.instance = instance
        self.groups = []

        self.groups.append(Adw.PreferencesGroup(
            title=self.instance.instance_type_display,
            description=self.instance.description if self.instance.description else self.instance.properties.get('url')
        ))

        if self.instance.instance_type == 'ollama:managed' and self.instance.get_row() and self.instance.process:
            suffix_button = Gtk.Button(icon_name='terminal-symbolic', valign=1, css_classes=['flat'], tooltip_text=_('Ollama Log'))
            suffix_button.connect('clicked', lambda button: dialog.simple_log(
                    parent = self.get_root(),
                    title = _('Ollama Log'),
                    summary_text = self.instance.log_summary[0],
                    summary_classes = self.instance.log_summary[1],
                    log_text = '\n'.join(self.instance.log_raw.split('\n')[-50:])
                )
            )
            self.groups[-1].set_header_suffix(suffix_button)

        if 'name' in self.instance.properties: #NAME
            self.groups[-1].add(Adw.EntryRow(
                title=_('Name'),
                name='name',
                text=self.instance.properties.get('name')
            ))

        if 'url' in self.instance.properties and self.instance.instance_type in ('ollama', 'ollama:managed', 'openai:generic'):
            if self.instance.instance_type == 'ollama:managed': #PORT
                try:
                    port = int(self.instance.properties.get('url').split(':')[-1])
                except Exception as e:
                    port = 11435
                self.groups[-1].add(Adw.SpinRow(
                    title=_('Port'),
                    subtitle=_("Which network port will '{}' use").format(self.instance.instance_type_display),
                    name='port',
                    digits=0,
                    numeric=True,
                    snap_to_ticks=True,
                    adjustment=Gtk.Adjustment(
                        value=port,
                        lower=1024,
                        upper=65535,
                        step_increment=1
                    )
                ))
            else: #URL
                self.groups[-1].add(Adw.EntryRow(
                    title=_('Instance URL'),
                    name='url',
                    text=self.instance.properties.get('url')
                ))

        if 'api' in self.instance.properties: #API
            normal_api_title = _('API Key')
            unchanged_api_title = _('API Key (Unchanged)')
            if self.instance.properties.get('api'):
                normal_api_title = unchanged_api_title
            elif self.instance.instance_type == 'ollama':
                normal_api_title = _('API Key (Optional)')

            api_el = Adw.PasswordEntryRow(
                title=normal_api_title,
                name='api'
            )

            api_el.connect('changed', lambda el: api_el.set_title(normal_api_title if api_el.get_text() else unchanged_api_title))
            self.groups[-1].add(api_el)

        self.groups.append(Adw.PreferencesGroup())

        if 'think' in self.instance.properties: #THINK
            self.groups[-1].add(Adw.SwitchRow(
                title=_('Thought Processing'),
                subtitle=_('Have compatible reasoning models think about their response before generating a message.'),
                name='think',
                active=self.instance.properties.get('think')
            ))

        if 'share_name' in self.instance.properties: #SHARE NAME
            share_name_el = Adw.ComboRow(
                title=_('Share Name'),
                subtitle=_('Automatically share your name with the AI models.'),
                name='share_name'
            )

            string_list = Gtk.StringList()
            string_list.append(_('Do Not Share'))
            string_list.append(_('Username'))
            string_list.append(_('Full Name'))

            share_name_el.set_model(string_list)
            share_name_el.set_selected(self.instance.properties.get('share_name'))
            self.groups[-1].add(share_name_el)

        if 'show_response_metadata' in self.instance.properties: #SHOW REQUEST METADATA
            self.groups[-1].add(Adw.SwitchRow(
                title=_('Show Response Metadata'),
                subtitle=_('Add the option to show reply metadata in the message as an attachment.'),
                name='show_response_metadata',
                active=self.instance.properties.get('show_response_metadata')
            ))

        if 'max_tokens' in self.instance.properties: #MAX TOKENS
            self.groups[-1].add(Adw.SpinRow(
                title=_('Max Tokens'),
                subtitle=_('Defines the maximum number of tokens (words + spaces) the AI can generate in a response. More tokens allow longer replies but may take more time and cost more.'),
                name='max_tokens',
                digits=0,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.instance.properties.get('max_tokens'),
                    lower=50,
                    upper=16384,
                    step_increment=1
                )
            ))

        if 'temperature' in self.instance.properties: #TEMPERATURE
            self.groups[-1].add(Adw.SpinRow(
                title=_('Temperature'),
                subtitle=_('Increasing the temperature will make the models answer more creatively.'),
                name='temperature',
                digits=2,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.instance.properties.get('temperature'),
                    lower=0.01,
                    upper=2,
                    step_increment=0.01
                )
            ))

        if 'seed' in self.instance.properties: #SEED
            self.groups[-1].add(Adw.SpinRow(
                title=_('Seed'),
                subtitle=_('Setting this to a specific number other than 0 will make the model generate the same text for the same prompt.'),
                name='seed',
                digits=0,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.instance.properties.get('seed'),
                    lower=0,
                    upper=99999999,
                    step_increment=1
                )
            ))

        if 'response_num_ctx' in self.instance.properties: #RESPONSE CONTEXT SIZE
            self.groups[-1].add(Adw.SpinRow(
                title=_('Response Context Size'), 
                subtitle=_('Context window size for chat responses. Higher values allow longer conversations but use more memory.'),
                name='response_num_ctx',
                digits=0,
                numeric=True,
                snap_to_ticks=True,
                adjustment=Gtk.Adjustment(
                    value=self.instance.properties.get('response_num_ctx'),
                    lower=1024,
                    upper=131072,
                    step_increment=1024
                )
            ))

        if 'overrides' in self.instance.properties: #OVERRIDES
            self.groups.append(Adw.PreferencesGroup(
                title=_('Overrides'),
                description=_('These entries are optional, they are used to troubleshoot GPU related problems with Ollama.')
            ))
            for name, value in self.instance.properties.get('overrides').items():
                override_el = Adw.EntryRow(
                    title=name,
                    name='override:{}'.format(name),
                    text=value
                )
                if override_urls.get(name):
                    link_button = Gtk.Button(
                        name=override_urls.get(name),
                        tooltip_text=override_urls.get(name),
                        icon_name='globe-symbolic',
                        valign=3
                    )
                    link_button.connect('clicked', lambda button: Gio.AppInfo.launch_default_for_uri(button.get_name()))
                    override_el.add_suffix(link_button)
                self.groups[-1].add(override_el)

        if 'model_directory' in self.instance.properties: #MODEL DIRECTORY
            self.groups.append(Adw.PreferencesGroup())
            model_directory_el = Adw.ActionRow(
                title=_('Model Directory'),
                subtitle=self.instance.properties.get('model_directory'),
                name="model_directory"
            )
            open_dir_button = Gtk.Button(
                tooltip_text=_('Select Directory'),
                icon_name='inode-directory-symbolic',
                valign=3
            )
            open_dir_button.connect('clicked', lambda button, row=model_directory_el: dialog.simple_directory(
                    parent = open_dir_button.get_root(),
                    callback = lambda res, row=model_directory_el: row.set_subtitle(res.get_path())
                )
            )
            model_directory_el.add_suffix(open_dir_button)
            self.groups[-1].add(model_directory_el)

        if self.instance.get_row() and ('default_model' in self.instance.properties or 'title_model' in self.instance.properties):
            self.groups.append(Adw.PreferencesGroup())

            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
            factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))

            default_model_el = Adw.ComboRow(
                title=_('Default Model'),
                subtitle=_('Model to select when starting a new chat.'),
                name='default_model',
                factory=factory
            )
            default_model_index = 0

            title_model_el = Adw.ComboRow(
                title=_('Title Model'),
                subtitle=_('Model to use when generating a chat title.'),
                name='title_model',
                factory=factory
            )
            title_model_index = 0

            string_list_default = Gtk.StringList()
            string_list_title = Gtk.StringList()
            string_list_title.append(_('Use Current Model'))
            for i, model in enumerate(self.instance.get_local_models()):
                string_list_default.append(prettify_model_name(model.get('name')))
                string_list_title.append(prettify_model_name(model.get('name')))
                if model.get('name') == self.instance.properties.get('default_model'):
                    default_model_index = i
                if model.get('name') == self.instance.properties.get('title_model'):
                    title_model_index = i

            default_model_el.set_model(string_list_default)
            default_model_el.set_selected(default_model_index)
            title_model_el.set_model(string_list_title)
            title_model_el.set_selected(title_model_index)
            self.groups[-1].add(default_model_el)
            self.groups[-1].add(title_model_el)

        pp = Adw.PreferencesPage()
        for group in self.groups:
            pp.add(group)

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

        tbv=Adw.ToolbarView()
        tbv.add_top_bar(hb)
        tbv.set_content(pp)
        super().__init__(
            child=tbv,
            title=_('Edit Instance') if self.instance.get_row() else _('Create Instance'),
            content_width=500
        )

    def save(self):
        save_functions = {
            'name': lambda val: val if val else _('Instance'),
            'port': lambda val: 'http://0.0.0.0:{}'.format(int(val)),
            'url': lambda val: '{}{}'.format('http://' if not re.match(r'^(http|https)://', val) else '', val.rstrip('/')),
            'api': lambda val: self.instance.properties.get('api') if self.instance.properties.get('api') and not val else (val if val else 'empty'),
            'think': lambda val: val,
            'share_name': lambda val: val,
            'show_response_metadata': lambda val: val,
            'max_tokens': lambda val: val,
            'temperature': lambda val: val,
            'seed': lambda val: val,
            'response_num_ctx': lambda val: int(val),
            'override': lambda val: val.strip(),
            'model_directory': lambda val: val.strip(),
            'default_model': lambda val: self.instance.get_local_models()[val].get('name') if val >= 0 else None,
            'title_model': lambda val: self.instance.get_local_models()[val-1].get('name') if val >= 1 else None
        }

        for group in self.groups:
            for el in list(list(list(list(group)[0])[1])[0]):
                value = None
                if isinstance(el, Adw.EntryRow) or isinstance(el, Adw.PasswordEntryRow):
                    value = el.get_text().replace('\n', '')
                elif isinstance(el, Adw.SpinRow):
                    value = el.get_value()
                elif isinstance(el, Adw.SwitchRow):
                    value = el.get_active()
                elif isinstance(el, Adw.ComboRow):
                    if len(list(el.get_model())) <= 0:
                        value = -1
                    else:
                        value = el.get_selected()
                elif isinstance(el, Adw.ActionRow):
                    value = el.get_subtitle()

                if el.get_name().startswith('override:'):
                    if 'overrides' not in self.instance.properties:
                        self.instance.properties['overrides'] = {}
                    self.instance.properties['overrides'][el.get_name().split(':')[1]] = value
                elif save_functions.get(el.get_name()):
                    self.instance.properties[el.get_name()] = save_functions.get(el.get_name())(value)

        if not self.instance.instance_id:
            self.instance.instance_id = generate_uuid()

        SQL.insert_or_update_instance(
            instance_id=self.instance.instance_id,
            pinned=self.instance.get_row().pinned if self.instance.get_row() else False,
            instance_type=self.instance.instance_type,
            properties=self.instance.properties
        )

        if self.instance.get_row():
            self.instance.get_row().set_title(self.instance.properties.get('name'))
        else:
            row = InstanceRow(instance=self.instance)
            self.get_root().instance_listbox.append(row)
            self.get_root().instance_listbox.select_row(row)

        if len(list(self.get_root().instance_listbox)) > 0:
            self.get_root().instance_manager_stack.set_visible_child_name('content')

        else:
            self.get_root().instance_manager_stack.set_visible_child_name('no-instances')

        self.force_close()

# Fallback for when there are no instances
class Empty:
    instance_id = ''
    instance_type = 'empty'
    instance_type_display = 'Empty'
    properties = {
        'name': _('Fallback Instance')
    }

    def stop(self):
        pass

    def get_local_models(self) -> list:
        return []

    def get_available_models(self) -> dict:
        return {}

    def get_model_info(self, model_name:str) -> dict:
        return {}

    def get_default_model(self) -> str:
        return ''

class InstanceRow(Adw.ActionRow):
    __gtype_name__ = 'AlpacaInstanceRow'

    def __init__(self, instance, pinned:bool=False):
        self.instance = instance
        #self.instance.set_row(self)
        self.pinned = pinned
        super().__init__(
            title = self.instance.properties.get('name'),
            subtitle = self.instance.instance_type_display,
            name = self.instance.properties.get('name'),
            visible = self.instance.instance_type != 'empty'
        )

        if not self.pinned:
            remove_button = Gtk.Button(
                icon_name='user-trash-symbolic',
                valign=3,
                css_classes=['destructive-action', 'flat']
            )
            remove_button.connect('clicked', lambda button: dialog.simple(
                    parent = self.get_root(),
                    heading = _('Remove Instance?'),
                    body = _('Are you sure you want to remove this instance?'),
                    callback = self.remove,
                    button_name = _('Remove'),
                    button_appearance = 'destructive'
                )
            )
            self.add_suffix(remove_button)

        if not isinstance(self.instance, Empty):
            edit_button = Gtk.Button(
                icon_name='edit-symbolic',
                valign=3,
                css_classes=['accent', 'flat']
            )
            edit_button.connect('clicked', lambda button: self.show_edit())
            self.add_suffix(edit_button)

    def show_edit(self):
        InstancePreferencesGroup(self.instance).present(self.get_root())

    def remove(self):
        SQL.delete_instance(self.instance.instance_id)
        if len(list(self.get_root().instance_listbox)) > 1:
            self.get_root().instance_manager_stack.set_visible_child_name('content')
        else:
            self.get_root().instance_manager_stack.set_visible_child_name('no-instances')
        self.get_parent().remove(self)

def create_instance_row(ins:dict) -> InstanceRow or None:
    if 'ollama' in ins.get('type'):
        if ins.get('type') != 'ollama:managed' or shutil.which('ollama'):
            for instance_cls in BaseOllama.__subclasses__():
                if getattr(instance_cls, 'instance_type', None) == ins.get('type'):
                    return InstanceRow(
                        instance=instance_cls(
                            instance_id=ins.get('id'),
                            properties=ins.get('properties')
                        )
                    )
    elif os.getenv('ALPACA_OLLAMA_ONLY', '0') != '1':
        for instance_cls in BaseOpenAI.__subclasses__():
            if getattr(instance_cls, 'instance_type', None) == ins.get('type'):
                return InstanceRow(
                    instance=instance_cls(
                        instance_id=ins.get('id'),
                        properties=ins.get('properties')
                    )
                )

def update_instance_list(instance_listbox:Gtk.ListBox, selected_instance_id:str):
    instance_listbox.remove_all()
    instances = SQL.get_instances()
    instance_added = False
    if len(instances) > 0:
        instance_listbox.get_root().instance_manager_stack.set_visible_child_name('content')
        for i, ins in enumerate(instances):
            row = create_instance_row(ins)
            if row:
                row.instance.set_row(row)
                GLib.idle_add(instance_listbox.append, row)
                instance_added = True
                if row.instance.instance_id == selected_instance_id:
                    GLib.idle_add(instance_listbox.select_row, row)

    if not instance_added:
        GLib.idle_add(instance_listbox.get_root().instance_manager_stack.set_visible_child_name, 'no-instances')
        GLib.idle_add(instance_listbox.append, InstanceRow(Empty()))

    def check_row_is_selected():
        if not instance_listbox.get_selected_row():
            instance_listbox.select_row(instance_listbox.get_row_at_index(0))
    GLib.idle_add(check_row_is_selected)

