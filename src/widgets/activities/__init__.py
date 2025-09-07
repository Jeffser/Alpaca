# __init__.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from .background_remover import BackgroundRemoverPage
from .web_browser import WebBrowser
from .live_chat import LiveChatPage
from .terminal import Terminal, AttachmentCreator, CodeRunner, CodeEditor
from .camera import show_webcam_dialog
from .. import dialog
import importlib.util

last_activity_tabview = None

class ActivityWrapper(Gtk.Overlay):
    __gtype_name__ = 'AlpacaActivityWrapper'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        self.tab = None
        super().__init__(
            child=self.page
        )
        buttons_container = Gtk.Box(
            css_classes=['linked', 'r10', 'osd'],
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
            valign=1 if isinstance(page, LiveChatPage) else 2,
            halign=3,
            overflow=1
        )
        close_button = Gtk.Button(
            tooltip_text=_('Close Activity'),
            icon_name='window-close-symbolic',
            css_classes=['flat']
        )
        close_button.connect('clicked', lambda button: self.close())

        for btn in self.page.buttons:
            if btn.get_parent():
                btn.get_parent().remove(btn)
            buttons_container.append(btn)
            btn.add_css_class('flat')
            if btn.get_hexpand():
                buttons_container.set_halign(0)
                buttons_container.set_hexpand(True)

        if len(self.page.buttons) > 0:
            buttons_container.append(Gtk.Separator())
        buttons_container.append(close_button)

        self.add_overlay(buttons_container)

    def close(self):
        self.page.on_close()
        if self.page.get_parent():
            if self.tab and self.page:
                self.page.get_ancestor(Adw.TabView).close_page(self.tab)

    def reload(self):
        if self.tab and self.page:
            self.page.get_ancestor(Adw.TabView).set_selected_page(self.tab)
        self.page.on_reload()

class ActivityDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaActivityDialog'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        tbv=Adw.ToolbarView()
        hb = Adw.HeaderBar(show_title=False)
        for btn in page.buttons:
            if btn.get_parent():
                btn.get_parent().remove(btn)
            if isinstance(btn, Gtk.Stack):
                for box in list(btn):
                    if isinstance(box, Gtk.Box):
                        box.remove_css_class('linked')
                        box.set_spacing(6)
                        for btn2 in list(box):
                            btn2.remove_css_class('br0')
            hb.pack_start(btn)
            btn.add_css_class('flat')
        tbv.add_top_bar(hb)
        tbv.set_content(self.page)

        super().__init__(
            child=tbv,
            title=self.page.title,
            content_width=500,
            content_height=600
        )

        self.connect('closed', lambda *_: self.close())

    def close(self):
        self.force_close()
        if self.page and self.page.get_parent():
            self.page.on_close()
            self.tab = None
            self.page = None
            self = None

    def reload(self):
        self.page.on_reload()

class ActivityManager(Adw.Bin):
    __gtype_name__ = 'AlpacaActivityManager'

    def __init__(self):
        self.navigationview = Adw.NavigationView()
        super().__init__(child=self.navigationview)

        # TABS
        self.tabview = Adw.TabView()
        self.tabview.connect('close-page', self.page_closed)
        self.tabview.connect('page-attached', self.page_attached)
        self.tabview.connect('page-detached', self.page_detached)
        self.tabview.connect('create-window', self.window_create)
        self.tabview.connect('notify::selected-page', self.page_changed)
        tab_hb = Adw.HeaderBar()

        overview_button = Adw.TabButton(
            view=self.tabview,
            action_name='overview.open'
        )
        tab_hb.pack_start(overview_button)

        detach_activity_button = Gtk.Button(
            icon_name='pip-in-symbolic',
            tooltip_text=_('Detach Activity')
        )
        detach_activity_button.connect('clicked', self.detach_current_activity)
        tab_hb.pack_start(detach_activity_button)

        launcher_button = Gtk.Button(
            icon_name='list-add-symbolic',
            tooltip_text=_('Create Activity')
        )
        launcher_button.connect('clicked', lambda btn: self.navigationview.push_by_tag('launcher'))
        tab_hb.pack_end(launcher_button)

        tab_tbv = Adw.ToolbarView(
            content=self.tabview
        )
        tab_tbv.add_top_bar(tab_hb)

        self.taboverview = Adw.TabOverview(
            view=self.tabview,
            child=tab_tbv
        )

        self.navigationview.add(Adw.NavigationPage(
            child=self.taboverview,
            tag='tab',
            title=_('Activities')
        ))

        # LAUNCHER
        listbox = Gtk.ListBox(
            selection_mode=0,
            css_classes=['boxed-list-separate'],
            halign=3
        )

        default_activities = [
            {
                'title': _('Terminal'),
                'icon': 'terminal-symbolic',
                'builder': lambda: Terminal(
                    language='bash',
                    code_getter=lambda: 'bash'
                ),
                #runner is optional
                'runner': lambda term: term.run()
            },
            {
                'title': _('Attachment Creator'),
                'icon': 'document-text-symbolic',
                'builder': AttachmentCreator
            },
            {
                'title': _('Camera'),
                'icon': 'camera-photo-symbolic',
                'builder': lambda: show_webcam_dialog(
                    root_widget=self.get_root(),
                    attachment_func=lambda att: self.get_root().get_application().main_alpaca_window.global_footer.attachment_container.add_attachment(att),
                    return_page=True
                )
            },
            {
                'title': _('Web Browser'),
                'icon': 'globe-symbolic',
                'builder': WebBrowser
            }
        ]

        if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
            default_activities.append(
                {
                    'title': _('Live Chat'),
                    'icon': 'headset-symbolic',
                    'builder': LiveChatPage
                }
            )

        if importlib.util.find_spec('rembg'):
            default_activities.append(
                {
                    'title': _('Background Remover'),
                    'icon': 'image-missing-symbolic',
                    'builder': BackgroundRemoverPage
                }
            )

        for activity in default_activities:
            row = Adw.ButtonRow(
                title=activity.get('title'),
                tooltip_text=activity.get('title'),
                start_icon_name=activity.get('icon')
            )
            row.connect('activated', lambda *_, ac=activity: self.start_activity(ac))
            listbox.append(row)

        launcher = Adw.StatusPage(
            title=_('Activities'),
            icon_name='com.jeffser.Alpaca',
            child=listbox
        )
        launcher_tbv = Adw.ToolbarView(
            content=launcher
        )
        launcher_tbv.add_top_bar(Adw.HeaderBar(show_title=False))
        self.navigationview.add(Adw.NavigationPage(
            child=launcher_tbv,
            tag='launcher',
            title=_('Activities')
        ))
        self.navigationview.replace_with_tags(['launcher'])

    def start_activity(self, activity):
        page = activity.get('builder')()
        if page:
            tab_page = self.tabview.append(ActivityWrapper(page))
            if activity.get('runner'):
                activity.get('runner')(page)
            tab_page.set_title(page.title)
            tab_page.set_icon(Gio.ThemedIcon.new(page.activity_icon))
            tab_page.get_child().tab = tab_page

    def page_closed(self, tabview, tabpage):
        tabpage.get_child().page.on_close()

    def page_attached(self, tabview, tabpage, index):
        tabpage.set_title(tabpage.get_child().page.title)
        tabpage.set_icon(Gio.ThemedIcon.new(tabpage.get_child().page.activity_icon))
        tabpage.get_child().tab = tabpage
        tabpage.set_thumbnail_yalign(0.5)

        self.navigationview.replace_with_tags(['tab'])
        if self.get_root().get_name() == 'AlpacaWindow':
            if self.get_root().last_breakpoint_status:
                self.get_root().chat_splitview.set_show_content(False)
            else:
                self.get_root().chat_splitview.set_collapsed(False)
            if len(tabview.get_pages()) == 1:
                self.get_root().split_view_overlay.set_show_sidebar(False)

        tabview.set_selected_page(tabpage)
        self.taboverview.set_open(False)

    def page_detached(self, tabview, tabpage, index):
        if len(tabview.get_pages()) == 0:
            self.navigationview.replace_with_tags(['launcher'])
            if self.get_root().get_name() == 'AlpacaWindow':
                if self.get_root().last_breakpoint_status:
                    self.get_root().chat_splitview.set_show_content(True)
                else:
                    self.get_root().chat_splitview.set_collapsed(True)
                if not self.get_root().last_breakpoint_status:
                    self.get_root().split_view_overlay.set_show_sidebar(True)

    def window_create(self, tabview=None):
        atw = ActivityTabWindow(self.get_root().get_application())
        atw.present()
        return atw.activity_manager.tabview

    def page_changed(self, tabview, gparam):
        if tabview.get_selected_page():
            self.navigationview.find_page('tab').set_title(tabview.get_selected_page().get_child().page.title)

    def detach_current_activity(self, button):
        global last_activity_tabview
        if not last_activity_tabview or not last_activity_tabview.get_root() or last_activity_tabview == self.tabview:
            last_activity_tabview = self.window_create()
        self.tabview.transfer_page(
            self.tabview.get_selected_page(),
            last_activity_tabview,
            0
        )

class ActivityTabWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AlpacaActivityTabWindow'

    def __init__(self, application):
        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        self.activity_manager = ActivityManager()
        self.application = application
        super().__init__(
            content=self.activity_manager,
            title=_('Activities')
        )
        self.connect('close-request', lambda *_: self.close())

    def get_application(self):
        return self.application

    def close(self):
        if self.activity_manager.tabview:
            for page in list(self.activity_manager.tabview.get_pages()):
                self.activity_manager.tabview.close_page(page)
        self.set_child()
        self.activity_manager = None
        super().close()

def show_activity(page:Gtk.Widget, root:Gtk.Widget, force_dialog:bool=False):
    if not page.get_parent():
        if root.get_name() == 'AlpacaWindow' and root.settings.get_value('activity-mode').unpack() == 0 and not force_dialog:
            tab_page = root.activities_page.get_child().tabview.append(ActivityWrapper(page))
            return tab_page.get_child()
        elif root.settings.get_value('activity-mode').unpack() == 1 or force_dialog:
            dialog = ActivityDialog(page)
            dialog.present(root)
            return dialog
        else:
            global last_activity_tabview
            if not last_activity_tabview or not last_activity_tabview.get_root():
                atw = ActivityTabWindow(root.get_application())
                atw.present()
                last_activity_tabview = atw.activity_manager.tabview

            tab_page = last_activity_tabview.append(ActivityWrapper(page))
            return tab_page.get_child()



