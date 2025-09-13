#chat.py
"""
Handles the chat widget
"""

import gi
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
import logging, os, datetime, random, json, threading, re
from ..constants import SAMPLE_PROMPTS, cache_dir
from ..sql_manager import generate_uuid, prettify_model_name, generate_numbered_name, Instance as SQL
from . import dialog, voice
from .message import Message

logger = logging.getLogger(__name__)

class ChatList(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaChatList'

    def __init__(self, folder_id:str=None, folder_name:str=_('Root'), folder_color:str=None, show_bar:bool=True):
        self.folder_id = folder_id
        container = Gtk.Box(orientation=1)
        self.scrolled_window = Gtk.ScrolledWindow(child=container)
        self._scroll_timeout_id = None

        self.list_stack = Gtk.Stack()
        self.list_stack.add_named(self.scrolled_window, 'content')
        self.list_stack.add_named(
            Adw.StatusPage(
                title=_('No Results Found'),
                icon_name='sad-computer-symbolic'
            ),
            'no-results'
        )
        self.list_stack.add_named(
            Adw.StatusPage(
                title=_('Folder is Empty'),
                icon_name='folder-symbolic'
            ),
            'empty'
        )

        overlay = Gtk.Overlay(child=self.list_stack)

        indicator_top_drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.COPY)
        indicator_top_drop_target.connect("accept", lambda *_: self.start_scrolling(-1))
        indicator_top_drop_target.connect("leave", lambda *_: self.stop_scrolling())
        self.top_indicator = Adw.Bin(
            hexpand=True,
            height_request=20,
            valign=1,
            visible=False
        )
        self.top_indicator.add_controller(indicator_top_drop_target)
        overlay.add_overlay(self.top_indicator)

        indicator_bottom_drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.COPY)
        indicator_bottom_drop_target.connect("accept", lambda *_: self.start_scrolling(1))
        indicator_bottom_drop_target.connect("leave", lambda *_: self.stop_scrolling())
        self.bottom_indicator = Adw.Bin(
            hexpand=True,
            height_request=20,
            valign=2,
            visible=False
        )
        self.bottom_indicator.add_controller(indicator_bottom_drop_target)
        overlay.add_overlay(self.bottom_indicator)


        tbv = Adw.ToolbarView(content=overlay)
        super().__init__(
            child=tbv,
            title=folder_name
        )
        if show_bar:
            header_bar = Adw.HeaderBar(
                css_classes=['raised']
            )
            tbv.add_bottom_bar(header_bar)
            drop_target_folder = Gtk.DropTarget.new(FolderRow, Gdk.DragAction.MOVE)
            drop_target_folder.connect("drop", self.on_drop_folder)
            header_bar.add_controller(drop_target_folder)
            drop_target_chat = Gtk.DropTarget.new(ChatRow, Gdk.DragAction.MOVE)
            drop_target_chat.connect("drop", self.on_drop_chat)
            header_bar.add_controller(drop_target_chat)

        self.folder_list_box = Gtk.ListBox(
            css_classes=['navigation-sidebar'],
            selection_mode=0,
            name=self.folder_id
        )
        container.append(self.folder_list_box)
        self.separator = Gtk.Separator(
            margin_start=10,
            margin_end=10
        )
        container.append(self.separator)
        self.chat_list_box = Gtk.ListBox(
            css_classes=['navigation-sidebar'],
            name=self.folder_id
        )
        self.chat_list_box.connect('row-selected', self.chat_changed)
        container.append(self.chat_list_box)

        if folder_color:
            self.add_css_class('folder-{}'.format(folder_color))

    def start_scrolling(self, direction):
        if self._scroll_timeout_id:
            GLib.source_remove(self._scroll_timeout_id)
        self._scroll_timeout_id = GLib.timeout_add(30, self.do_scroll, direction)

    def stop_scrolling(self):
        if self._scroll_timeout_id:
            GLib.source_remove(self._scroll_timeout_id)
            self._scroll_timeout_id = None

    def do_scroll(self, direction):
        adj = self.scrolled_window.get_vadjustment()
        new_value = adj.get_value() + direction * 15 # scroll speed
        adj.set_value(max(0, min(new_value, adj.get_upper() - adj.get_page_size())))

        self.top_indicator.set_visible(new_value >= 0) # Hide the top indicator so it doesn't get in the way of the top folder
        return True

    def on_drop_folder(self, target, row, x, y):
        folder_page = self.get_root().chat_list_navigationview.get_previous_page(self)
        if row.folder_id != folder_page.folder_id:
            SQL.move_folder_to_folder(row.folder_id, folder_page.folder_id)
            row.get_parent().remove(row)
            folder_page.folder_list_box.prepend(row)
            row.set_visible(True)
            self.update_visibility()
            return True

    def on_drop_chat(self, target, row, x, y):
        folder_page = self.get_root().chat_list_navigationview.get_previous_page(self)
        row.chat.folder_id = folder_page.folder_id
        SQL.insert_or_update_chat(row.chat)
        row.get_parent().remove(row)
        folder_page.chat_list_box.prepend(row)
        row.set_visible(True)
        self.update_visibility()
        return True

    def update_visibility(self, searching:bool=False):
        folder_visible = False
        chat_visible = False

        for row in list(self.folder_list_box):
            folder_visible = folder_visible or row.get_visible()
            if folder_visible:
                break

        for row in list(self.chat_list_box):
            chat_visible = chat_visible or row.get_visible()
            if chat_visible:
                break

        self.folder_list_box.set_visible(folder_visible)
        self.chat_list_box.set_visible(chat_visible)
        self.separator.set_visible(folder_visible and chat_visible)

        if searching:
            self.list_stack.set_visible_child_name('content' if folder_visible or chat_visible else 'no-results')
        else:
            self.list_stack.set_visible_child_name('content' if folder_visible or chat_visible else 'empty')

    def on_search(self, query:str):
        if len(list(self.folder_list_box)) + len(list(self.chat_list_box)) == 0:
            self.list_stack.set_visible_child_name('empty')
            return

        for row in list(self.folder_list_box):
            row.set_visible(re.search(query, row.get_name(), re.IGNORECASE))

        for row in list(self.chat_list_box):
            row.set_visible(re.search(query, row.get_name(), re.IGNORECASE))

        self.update_visibility()

    def update(self):
        selected_chat = self.get_root().settings.get_value('default-chat').unpack()
        chats = SQL.get_chats_by_folder(self.folder_id)
        if len(chats) > 0:
            if selected_chat not in [row[0] for row in chats] and not self.folder_id:
                selected_chat = chats[0][0]

            for row in chats:
                self.add_chat(
                    chat_name=row[1],
                    chat_id=row[0],
                    mode=0
                )
                if row[0] == selected_chat and len(list(self.chat_list_box)) > 0:
                    self.chat_list_box.select_row(list(self.chat_list_box)[-1])

        if len(list(self.chat_list_box)) == 0 and not self.folder_id:
            self.chat_list_box.select_row(self.new_chat().row)

        if not self.chat_list_box.get_selected_row() and not self.folder_id:
            self.chat_list_box.select_row(list(self.chat_list_box)[0])

        folders = SQL.get_chat_folders(self.folder_id)
        for f in folders:
            row = FolderRow(f[0], f[1], f[2], f[3])
            self.folder_list_box.append(row)

        self.update_visibility()

    def add_chat(self, chat_name:str, chat_id:str, mode:int): #mode = 0: append, mode = 1: prepend
        chat_name = chat_name.strip()
        if chat_name and mode in (0, 1):
            chat_name = generate_numbered_name(chat_name, [row.get_name() for row in list(self.chat_list_box)])
            chat = None
            chat = Chat(
                chat_id=chat_id,
                name=chat_name,
                folder_id=self.folder_id
            )

            if chat:
                if mode == 0:
                    self.chat_list_box.append(chat.row)
                else:
                    self.chat_list_box.prepend(chat.row)
                self.update_visibility()
                return chat

    def new_chat(self, chat_name:str=_('New Chat')):
        if not chat_name.strip():
            chat_name = _('New Chat')
        chat = self.add_chat(
            chat_name=chat_name,
            chat_id=generate_uuid(),
            mode=1
        )
        if chat:
            SQL.insert_or_update_chat(chat)
            return chat

    def new_folder(self, name:str, color:str):
        name = generate_numbered_name(name, [row.get_name() for row in list(self.folder_list_box)])
        row = FolderRow(
            generate_uuid(),
            name,
            color,
            self.folder_id
        )
        SQL.insert_or_update_folder(
            row.folder_id,
            row.folder_name,
            row.folder_color,
            row.folder_parent
        )
        self.folder_list_box.prepend(row)
        self.update_visibility()

    def prompt_new_folder(self):
        options = {
            _('Cancel'): {},
            _('Accept'): {
                'appearance': 'suggested',
                'callback': lambda name, toggle_group: self.new_folder(name, toggle_group.get_active_name()),
                'default': True
            }
        }

        d = dialog.Entry(
            _('New Folder'),
            '',
            list(options.keys())[0],
            options,
            {'placeholder': _('New Folder'), 'text': _('New Folder')}
        )
        color_group = Adw.ToggleGroup()
        color_names = ('blue', 'teal', 'green', 'yellow', 'orange', 'red', 'pink', 'purple', 'slate')
        for c in color_names:
            icon = Gtk.Image.new_from_icon_name('big-dot-symbolic')
            icon.add_css_class('button-{}'.format(c))
            icon.set_icon_size(2)
            toggle = Adw.Toggle(
                name=c,
                child=icon
            )
            color_group.add(toggle)

        color_group.set_active_name(random.choice(color_names))
        d.container.append(color_group)

        d.show(self.get_root())

    def chat_changed(self, listbox, row):
        if not listbox.get_root() or (row and not row.get_root()):
            return

        last_chat_id = -1
        if listbox.get_root().chat_bin.get_child():
            last_chat_id = listbox.get_root().chat_bin.get_child().chat_id

        if row and row.chat.chat_id != last_chat_id:
            if listbox.get_root().chat_bin.get_child():
                list_box = listbox.get_root().chat_bin.get_child().row.get_parent()
                if list_box and list_box != self.chat_list_box:
                    listbox.get_root().chat_bin.get_child().row.get_parent().unselect_all()
            # Discard Old Chat if Not Busy DISABLED FOR PERFORMANCE REASONS (even tho it uses more ram)
            #old_chat = listbox.get_root().chat_bin.get_child()
            #if old_chat and not old_chat.busy:
                #old_chat.unload_messages()
                #old_chat.unrealize()

            # Load New Chat
            new_chat = row.chat
            if new_chat.get_parent():
                new_chat.get_parent().set_child(None)
            if new_chat.busy:
                self.get_root().global_footer.toggle_action_button(False)
            else:
                self.get_root().global_footer.toggle_action_button(True)

            if len(list(new_chat.container)) == 0:
                new_chat.load_messages()

            # Show New Stack Page
            self.get_root().chat_bin.set_child(new_chat)

            # Select Model
            GLib.idle_add(self.auto_select_model)

    def auto_select_model(self):
        def find_model_index(model_name:str) -> int:
            if len(list(self.get_root().model_dropdown.get_model())) == 0 or not model_name:
                return -1
            detected_models = [i for i, future_row in enumerate(list(self.get_root().model_dropdown.get_model())) if future_row.model.get_name() == model_name]
            if len(detected_models) > 0:
                return detected_models[0]
            return -1

        chat = self.get_root().chat_bin.get_child()
        if chat:
            model_index = -1
            if len(list(chat.container)) > 0:
                model_index = find_model_index(list(chat.container)[-1].get_model())
            if model_index == -1:
                model_index = find_model_index(self.get_root().get_current_instance().get_default_model())

            if model_index and model_index != -1:
                self.get_root().model_dropdown.set_selected(model_index)

class Chat(Gtk.Stack):
    __gtype_name__ = 'AlpacaChat'

    def __init__(self, chat_id:str=None, name:str=_("New Chat"), folder_id:str=None):
        super().__init__(
            name=name,
            transition_type=1,
            vexpand=True
        )
        self.container = Gtk.Box(
            orientation=1,
            hexpand=True,
            vexpand=True,
            spacing=12,
            css_classes=['p10']
        )
        clamp = Adw.Clamp(
            maximum_size=1000,
            tightening_threshold=800,
            child=self.container
        )
        self.scrolledwindow = Gtk.ScrolledWindow(
            child=clamp,
            propagate_natural_height=True,
            kinetic_scrolling=True,
            vexpand=True,
            hexpand=True,
            css_classes=["undershoot-bottom"],
            hscrollbar_policy=2
        )
        self.add_named(Adw.Spinner(), 'loading')
        self.add_named(self.scrolledwindow, 'content')

        self.welcome_screen = Adw.StatusPage(
            icon_name="com.jeffser.Alpaca",
            title="Alpaca",
            description=_("Try one of these prompts"),
            vexpand=True
        )
        list(self.welcome_screen)[0].add_css_class('undershoot-bottom')
        self.add_named(self.welcome_screen, 'welcome-screen')
        self.refresh_welcome_screen_prompts()

        self.add_named(Adw.StatusPage(
            icon_name="sad-computer-symbolic",
            title=_("No Messages Found"),
            description=_("Uh oh! No messages found for your search.")
        ), 'no-results')

        self.busy = False
        self.chat_id = chat_id
        self.folder_id = folder_id
        self.row = ChatRow(self)

    def refresh_welcome_screen_prompts(self):
        button_container = Gtk.Box(
            orientation=1,
            spacing=10,
            halign=3
        )
        for prompt in random.sample(SAMPLE_PROMPTS, 3):
            prompt_button = Gtk.Button(
                child=Gtk.Label(
                    label=prompt,
                    justify=2,
                    wrap=True
                ),
                tooltip_text=_("Send prompt: '{}'").format(prompt)
            )
            prompt_button.connect('clicked', lambda *_, prompt=prompt : self.send_sample_prompt(prompt))
            button_container.append(prompt_button)
        refresh_button = Gtk.Button(
            icon_name='view-refresh-symbolic',
            tooltip_text=_("Refresh Prompts"),
            halign=3,
            css_classes=["circular", "accent"]
        )
        refresh_button.connect('clicked', lambda *_: self.refresh_welcome_screen_prompts())
        button_container.append(refresh_button)
        self.welcome_screen.set_child(button_container)

    def stop_message(self):
        self.busy = False
        self.get_root().global_footer.toggle_action_button(True)

    def unload_messages(self):
        for widget in list(self.container):
            GLib.idle_add(widget.unparent)
            GLib.idle_add(widget.unrealize)
        self.set_visible_child_name('loading')

    def add_message(self, message):
        self.container.append(message)
        GLib.idle_add(self.set_visible_child_name, 'content')

    def load_messages(self):
        messages = SQL.get_messages(self)
        for message in messages:
            message_element = Message(
                dt=datetime.datetime.strptime(message[3] + (":00" if message[3].count(":") == 1 else ""), '%Y/%m/%d %H:%M:%S'),
                message_id=message[0],
                chat=self,
                mode=('user', 'assistant', 'system').index(message[1]),
                author=message[2]
            )
            self.container.append(message_element)

            attachments = SQL.get_attachments(message_element)
            for attachment in attachments:
                GLib.idle_add(
                    lambda msg=message_element, att=attachment: msg.add_attachment(
                        file_id=att[0],
                        name=att[2],
                        attachment_type=att[1],
                        content=att[3]
                    ) and False
                )
            GLib.idle_add(message_element.block_container.set_content, message[4])
        GLib.idle_add(self.set_visible_child_name, 'content' if len(messages) > 0 else 'welcome-screen')

    def send_sample_prompt(self, prompt:str):
        if self.get_root().get_name() == 'AlpacaWindow':
            if len(list(self.get_root().local_model_flowbox)) == 0:
                if self.get_root().get_current_instance().instance_type == 'empty':
                    self.get_root().get_application().lookup_action('instance_manager').activate()
                else:
                    self.get_root().get_application().lookup_action('model_manager').activate()
        buffer = self.get_root().global_footer.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), prompt, len(prompt.encode('utf-8')))
        self.get_root().send_message()

    def convert_to_ollama(self) -> list:
        messages = []
        for message in list(self.container):
            if message.get_content() and message.dt:
                message_data = {
                    'role': ('user', 'assistant', 'system')[message.mode],
                    'content': ''
                }

                for image in message.image_attachment_container.get_content():
                    if 'images' not in message_data:
                        message_data['images'] = []

                    message_data['images'].append(image['content'])

                for attachment in message.attachment_container.get_content():
                    if attachment.get('type') not in ('thought', 'metadata'):
                        message_data['content'] += '```{} ({})\n{}\n```\n\n'.format(attachment.get('name'), attachment.get('type'), attachment.get('content'))
                message_data['content'] += message.get_content()
                messages.append(message_data)
        return messages

    def convert_to_json(self, include_metadata:bool=False) -> list:
        messages = []
        for message in list(self.container):
            if message.get_content() and message.dt:
                message_data = {
                    'role': ('user', 'assistant', 'system')[message.mode],
                    'content': []
                }
                for image in message.image_attachment_container.get_content():
                    message_data['content'].append({
                        'type': 'image_url',
                        'image_url': f'data:image/png;base64,{image.get("content")}'
                    })
                message_data['content'].append({
                    'type': 'text',
                    'text': ''
                })
                for attachment in message.attachment_container.get_content():
                    if attachment.get('type') not in ('thought', 'metadata'):
                        message_data['content'][0]['text'] += '```{} ({})\n{}\n```\n\n'.format(attachment.get('name'), attachment.get('type'), attachment.get('content'))
                message_data['content'][0 if ("text" in message_data.get("content", [''])[0]) else 1]['text'] += message.get_content()
                if include_metadata:
                    message_data['date'] = message.dt.strftime("%Y/%m/%d %H:%M:%S")
                    message_data['model'] = message.get_model()
                messages.append(message_data)
        return messages

class FolderRow(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaFolderRow'

    def __init__(self, folder_id:str=None, folder_name:str=_('Root'), folder_color:str=None, folder_parent:str=None):
        self.folder_id = folder_id
        self.folder_name = folder_name
        self.folder_color = folder_color
        self.folder_parent = folder_parent
        container = Gtk.Box(
            spacing=10
        )
        container.append(
            Gtk.Image.new_from_icon_name('folder-symbolic')
        )
        self.label = Gtk.Label(
            label=folder_name,
            tooltip_text=folder_name,
            hexpand=True,
            halign=0,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            xalign=0
        )
        container.append(self.label)
        button = Gtk.Button(
            child=container,
            css_classes=['flat']
        )
        button.connect('clicked', lambda button: self.open_folder())

        super().__init__(
            height_request=45,
            child=button,
            name=folder_name,
            css_classes=['p0']
        )
        if folder_color:
            self.add_css_class('folder-{}'.format(folder_color))

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        drop_target_folder = Gtk.DropTarget.new(FolderRow, Gdk.DragAction.MOVE)
        drop_target_folder.connect("drop", self.on_drop_folder)
        self.add_controller(drop_target_folder)
        drop_target_chat = Gtk.DropTarget.new(ChatRow, Gdk.DragAction.MOVE)
        drop_target_chat.connect("drop", self.on_drop_chat)
        self.add_controller(drop_target_chat)
        self.connect('map', lambda *_: self.on_map())

    def on_map(self):
        page = self.get_ancestor(Adw.NavigationPage)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("drag-cancel", lambda *_: self.set_visible(True))
        drag_source.connect('prepare', lambda *_: Gdk.ContentProvider.new_for_value(self))
        drag_source.connect("drag-begin", lambda s,d,page=page: self.on_drag_begin(s,d,page))
        drag_source.connect("drag-end", lambda s,d,r,page=page: self.on_drag_end(s,d,r,page))
        self.add_controller(drag_source)

    def on_drop_folder(self, target, row, x, y):
        if row.folder_id != self.folder_id:
            SQL.move_folder_to_folder(row.folder_id, self.folder_id)
            row.get_parent().remove(row)
            folder_page = self.get_root().chat_list_navigationview.find_page(self.folder_id)
            if folder_page:
                folder_page.folder_list_box.prepend(row)
                row.set_visible(True)
                folder_page.update_visibility()
            return True

    def on_drop_chat(self, target, row, x, y):
        row.chat.folder_id = self.folder_id
        SQL.insert_or_update_chat(row.chat)
        row.get_parent().remove(row)
        folder_page = self.get_root().chat_list_navigationview.find_page(self.folder_id)
        if folder_page:
            folder_page.chat_list_box.prepend(row)
            row.set_visible(True)
            folder_page.update_visibility()
        return True

    def on_drag_begin(self, source, drag, page):
        page.top_indicator.set_visible(True)
        page.bottom_indicator.set_visible(True)
        snapshot = Gtk.Snapshot()
        self.snapshot_child(self.get_child(), snapshot)
        paintable = snapshot.to_paintable()
        source.set_icon(paintable, 0, 0)
        self.set_visible(False)
        GLib.idle_add(self.get_root().get_chat_list_page().scrolled_window.get_vadjustment().set_value, 0)

    def on_drag_end(self, source, drag, res, page):
        page.top_indicator.set_visible(False)
        page.bottom_indicator.set_visible(False)
        if page._scroll_timeout_id:
            GLib.source_remove(page._scroll_timeout_id)
            page._scroll_timeout_id = None

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Edit Folder'),
                    'callback': self.prompt_rename,
                    'icon': 'document-edit-symbolic'
                }
            ],
            [
                {
                    'label': _('Delete Folder'),
                    'callback': self.prompt_delete,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

    def open_folder(self):
        if not self.get_root().chat_list_navigationview.find_page(self.folder_id):
            folder_page = ChatList(self.folder_id, self.folder_name, self.folder_color, True)
            folder_page.set_tag(self.folder_id)
            self.get_root().chat_list_navigationview.add(folder_page)
            folder_page.update()
        self.get_root().chat_list_navigationview.push_by_tag(self.folder_id)

    def rename(self, new_name:str, new_color:str):
        if not new_name:
            new_name = _('New Folder')
        if new_name != self.folder_name:
            new_name = generate_numbered_name(new_name, [row.get_name() for row in list(self.get_parent())])
        self.folder_name = new_name
        self.label.set_label(new_name)
        self.label.set_tooltip_text(new_name)
        self.set_name(new_name)

        self.remove_css_class('folder-{}'.format(self.folder_color))
        self.folder_color = new_color
        self.add_css_class('folder-{}'.format(self.folder_color))
        SQL.insert_or_update_folder(self.folder_id, self.folder_name, self.folder_color, self.folder_parent)

        folder_page = self.get_root().chat_list_navigationview.find_page(self.folder_id)
        if folder_page:
            folder_page.set_title(new_name)
            folder_page.set_css_classes(['folder-{}'.format(self.folder_color)])

    def prompt_rename(self):
        options = {
            _('Cancel'): {},
            _('Accept'): {
                'appearance': 'suggested',
                'callback': lambda name, toggle_group: self.rename(name, toggle_group.get_active_name()),
                'default': True
            }
        }

        d = dialog.Entry(
            _('Edit Folder?'),
            ("Editing '{}'").format(self.get_name()),
            list(options.keys())[0],
            options,
            {'placeholder': _('New Folder'), 'text': self.folder_name}
        )
        color_group = Adw.ToggleGroup()
        for c in ('blue', 'teal', 'green', 'yellow', 'orange', 'red', 'pink', 'purple', 'slate'):
            icon = Gtk.Image.new_from_icon_name('big-dot-symbolic')
            icon.add_css_class('button-{}'.format(c))
            icon.set_icon_size(2)
            toggle = Adw.Toggle(
                name=c,
                child=icon
            )
            color_group.add(toggle)
            if self.folder_color == c:
                color_group.set_active_name(c)
        d.container.append(color_group)

        d.show(self.get_root())

    def delete(self):
        if len(list(self.get_parent())) == 1:
            self.get_parent().set_visible(False)
            list(self.get_parent().get_parent())[1].set_visible(False)
        self.get_parent().remove(self)
        SQL.remove_folder(self.folder_id)

    def prompt_delete(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Delete Folder?'),
            body = _("Are you sure you want to delete '{}' and all it's sub-folders and chats?").format(self.get_name()),
            callback = lambda: self.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

class ChatRow(Gtk.ListBoxRow):
    __gtype_name__ = 'AlpacaChatRow'

    def __init__(self, chat:Chat):
        self.chat = chat
        self.spinner = Adw.Spinner(visible=False)
        self.label = Gtk.Label(
            label=self.chat.get_name(),
            tooltip_text=self.chat.get_name(),
            hexpand=True,
            halign=0,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            xalign=0
        )
        self.indicator = Gtk.Image.new_from_icon_name("chat-bubble-text-symbolic")
        self.indicator.set_visible(False)
        self.indicator.set_css_classes(['accent'])
        container = Gtk.Box(
            spacing=5
        )
        container.append(self.label)
        container.append(self.spinner)
        container.append(self.indicator)
        super().__init__(
            height_request=45,
            child=container,
            name=self.chat.get_name()
        )

        self.gesture_click = Gtk.GestureClick(button=3)
        self.gesture_click.connect("released", lambda gesture, n_press, x, y: self.show_popup(gesture, x, y) if n_press == 1 else None)
        self.add_controller(self.gesture_click)
        self.gesture_long_press = Gtk.GestureLongPress()
        self.gesture_long_press.connect("pressed", self.show_popup)
        self.add_controller(self.gesture_long_press)
        self.connect('map', lambda *_: self.on_map())

    def on_map(self):
        page = self.get_ancestor(Adw.NavigationPage)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("drag-cancel", lambda *_: self.set_visible(True))
        drag_source.connect('prepare', lambda *_: Gdk.ContentProvider.new_for_value(self))
        drag_source.connect("drag-begin", lambda s,d,page=page: self.on_drag_begin(s,d,page))
        drag_source.connect("drag-end", lambda s,d,r,page=page: self.on_drag_end(s,d,r,page))
        self.add_controller(drag_source)

    def on_drag_begin(self, source, drag, page):
        page.top_indicator.set_visible(True)
        page.bottom_indicator.set_visible(True)
        snapshot = Gtk.Snapshot()
        self.snapshot_child(self.get_child(), snapshot)
        paintable = snapshot.to_paintable()
        source.set_icon(paintable, 0, 0)
        self.set_visible(False)
        GLib.idle_add(self.get_root().get_chat_list_page().scrolled_window.get_vadjustment().set_value, 0)

    def on_drag_end(self, source, drag, res, page):
        page.top_indicator.set_visible(False)
        page.bottom_indicator.set_visible(False)
        if page._scroll_timeout_id:
            GLib.source_remove(page._scroll_timeout_id)
            page._scroll_timeout_id = None

    def show_popup(self, gesture, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, = x, y
        actions = [
            [
                {
                    'label': _('Rename Chat'),
                    'callback': self.prompt_rename,
                    'icon': 'document-edit-symbolic'
                },
                {
                    'label': _('Duplicate Chat'),
                    'callback': self.duplicate,
                    'icon': 'edit-copy-symbolic'
                },
                {
                    'label': _('Export Chat'),
                    'callback': self.prompt_export,
                    'icon': 'folder-download-symbolic'
                }
            ],
            [
                {
                    'label': _('Delete Chat'),
                    'callback': self.prompt_delete,
                    'icon': 'user-trash-symbolic'
                }
            ]
        ]
        popup = dialog.Popover(actions)
        popup.set_parent(self)
        popup.set_pointing_to(rect)
        popup.popup()

    def update_profile_pictures(self):
        for msg in list(self.chat.container):
            msg.update_profile_picture()

    def rename(self, new_name:str):
        if not new_name:
            new_name = _('New Chat')
        new_name = generate_numbered_name(new_name, [row.get_name() for row in list(self.get_parent())])
        self.label.set_label(new_name)
        self.label.set_tooltip_text(new_name)
        self.chat.set_name(new_name)
        self.set_name(new_name)
        SQL.insert_or_update_chat(self.chat)

    def prompt_rename(self):
        dialog.simple_entry(
            parent = self.get_root(),
            heading = _('Rename Chat?'),
            body = _("Renaming '{}'").format(self.get_name()),
            callback = lambda new_name: self.rename(new_name),
            entries = {'placeholder': _('Chat name'), 'default': True, 'text': self.get_name()},
            button_name = _('Rename')
        )

    def delete(self):
        window = self.get_root()
        list_box = self.get_parent()
        list_box.remove(self)
        SQL.delete_chat(self.chat)
        if len(list(list_box)) == 0:
            chat_list_page = window.get_chat_list_page()
            if chat_list_page.folder_id:
                previous_page = window.chat_list_navigationview.get_previous_page(chat_list_page)
                previous_page.chat_list_box.select_row(list(previous_page.chat_list_box)[0])
                previous_page.update_visibility()
            else:
                chat_list_page.new_chat()
            chat_list_page.update_visibility()
        if not list_box.get_selected_row() or list_box.get_selected_row() == self:
            list_box.select_row(list_box.get_row_at_index(0))
        if voice.message_dictated and voice.message_dictated.chat.chat_id == self.chat.chat_id:
            voice.message_dictated.popup.tts_button.set_active(False)

    def prompt_delete(self):
        dialog.simple(
            parent = self.get_root(),
            heading = _('Delete Chat?'),
            body = _("Are you sure you want to delete '{}'?").format(self.get_name()),
            callback = lambda: self.delete(),
            button_name = _('Delete'),
            button_appearance = 'destructive'
        )

    def duplicate(self):
        new_chat_name = _("Copy of {}".format(self.get_name()))
        new_chat_id = generate_uuid()
        new_chat = self.get_root().get_chat_list_page().add_chat(
            chat_name=new_chat_name,
            chat_id=new_chat_id,
            mode=1
        )
        SQL.duplicate_chat(self.chat, new_chat)

    def on_export_successful(self, file, result):
        file.replace_contents_finish(result)
        dialog.show_toast(_("Chat exported successfully"), self.get_root())

    def on_export_chat(self, file_dialog, result, temp_path):
        file = file_dialog.save_finish(result)
        if file:
            with open(temp_path, "rb") as db:
                file.replace_contents_async(
                    db.read(),
                    etag=None,
                    make_backup=False,
                    flags=Gio.FileCreateFlags.NONE,
                    cancellable=None,
                    callback=self.on_export_successful
                )

    def export_md(self, obsidian:bool):
        logger.info("Exporting chat (MD)")
        markdown = []
        for message_element in list(self.chat.container):
            if message_element.get_content() and message_element.dt:
                message_author = _('User')
                if message_element.get_model():
                    message_author = prettify_model_name(message_element.get_model())
                if message_element.mode == 2:
                    message_author = _('System')

                markdown.append('### **{}** | {}'.format(message_author, message_element.dt.strftime("%Y/%m/%d %H:%M:%S")))
                markdown.append(message_element.get_content())
                for file in message_element.image_attachment_container.get_content():
                    markdown.append('![🖼️ {}](data:image/{};base64,{})'.format(file.get('name'), file.get('name').split('.')[1], file.get('content')))
                emojis = {
                    'plain_text': '📃',
                    'code': '💻',
                    'pdf': '📕',
                    'youtube': '📹',
                    'website': '🌐',
                    'thought': '🧠'
                }
                for file in message_element.attachment_container.get_content():
                    if obsidian:
                        file_block = "> [!quote]- {}\n".format(file.get('name'))
                        for line in file.get('content').split("\n"):
                            file_block += "> {}\n".format(line)
                        markdown.append(file_block)
                    else:
                        markdown.append('<details>\n\n<summary>{} {}</summary>\n\n```TXT\n{}\n```\n\n</details>'.format(emojis.get(file.get('type'), '📃'), file.get('name'), file.get('content')))
                markdown.append('----')
        markdown.append('Generated from [Alpaca](https://github.com/Jeffser/Alpaca)')
        with open(os.path.join(cache_dir, 'export.md'), 'w') as f:
            f.write('\n\n'.join(markdown))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.md")
        file_dialog.save(parent=self.get_root(), cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.md'): self.on_export_chat(file_dialog, result, temp_path))

    def export_db(self):
        logger.info("Exporting chat (DB)")
        if os.path.isfile(os.path.join(cache_dir, 'export.db')):
            os.remove(os.path.join(cache_dir, 'export.db'))
        SQL.export_db(self.chat, os.path.join(cache_dir, 'export.db'))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.db")
        file_dialog.save(parent=self.get_root(), cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.db'): self.on_export_chat(file_dialog, result, temp_path))

    def export_json(self, include_metadata:bool):
        logger.info("Exporting chat (JSON)")
        with open(os.path.join(cache_dir, 'export.json'), 'w') as f:
            f.write(json.dumps({self.get_name() if include_metadata else 'messages': self.chat.convert_to_json(include_metadata)}, indent=4))
        file_dialog = Gtk.FileDialog(initial_name=f"{self.get_name()}.json")
        file_dialog.save(parent=self.get_root(), cancellable=None, callback=lambda file_dialog, result, temp_path=os.path.join(cache_dir, 'export.json'): self.on_export_chat(file_dialog, result, temp_path))

    def prompt_export(self):
        options = {
            _("Importable (.db)"): self.export_db,
            _("Markdown"): lambda: self.export_md(False),
            _("Markdown (Obsidian Style)"): lambda: self.export_md(True),
            _("JSON"): lambda: self.export_json(False),
            _("JSON (Include Metadata)"): lambda: self.export_json(True)
        }
        dialog.simple_dropdown(
            parent = self.get_root(),
            heading = _("Export Chat"),
            body = _("Select a method to export the chat"),
            callback = lambda option, options=options: options[option](),
            items = options.keys()
        )
