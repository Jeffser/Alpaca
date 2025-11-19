# __init__.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk
from .background_remover import BackgroundRemover
from .web_browser import WebBrowser
from .live_chat import LiveChat
from .terminal import Terminal, AttachmentCreator, CodeRunner, CodeEditor
from .transcriber import Transcriber
from .camera import Camera
from .viewers import ImageViewer, FileViewer
from .. import dialog
import importlib.util

last_activity_tabview = None

class ActivityDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaActivityDialog'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        tbv=Adw.ToolbarView()
        hb = Adw.HeaderBar()
        tbv.add_top_bar(hb)
        bb = generate_action_bar(self.page)
        if self.page.extend_to_edge and self.page.__gtype_name__ != 'AlpacaLiveChat':
            hb.add_css_class('osd')
            if bb:
                bb.add_css_class('osd')
        if bb:
            for css_class in self.page.buttons.get('css', []):
                bb.add_css_class(css_class)

        tbv.add_bottom_bar(bb)
        tbv.set_content(self.page)

        tbv.set_extend_content_to_bottom_edge(self.page.extend_to_edge)
        tbv.set_extend_content_to_top_edge(self.page.extend_to_edge)

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
            self.page = None
            self = None

    def reload(self):
        self.page.on_reload()

class ActivityManager(Adw.Bin):
    __gtype_name__ = 'AlpacaActivityManager'

    def __init__(self, reattach:bool=False):
        self.navigationview = Adw.NavigationView()
        super().__init__(child=self.navigationview)

        # TABS
        self.tabview = Adw.TabView()
        self.tabview.connect('close-page', self.page_closed)
        self.tabview.connect('page-attached', self.page_attached)
        self.tabview.connect('page-detached', self.page_detached)
        self.tabview.connect('create-window', self.window_create)
        self.tabview.connect('notify::selected-page', self.page_changed)
        self.tab_hb = Adw.HeaderBar()

        overview_button = Adw.TabButton(
            view=self.tabview,
            action_name='overview.open'
        )
        self.tab_hb.pack_start(overview_button)

        action_activity_button = Gtk.Button(
            icon_name='pip-out-symbolic' if reattach else 'pip-in-symbolic',
            tooltip_text=_('Attach Activity') if reattach else _('Detach Activity')
        )

        action_activity_button.connect('clicked', self.reattach_current_activity if reattach else self.detach_current_activity)
        self.tab_hb.pack_start(action_activity_button)

        launcher_button = Gtk.Button(
            icon_name='list-add-symbolic',
            tooltip_text=_('Create Activity')
        )
        launcher_button.connect('clicked', lambda btn: self.navigationview.push_by_tag('launcher'))
        self.tab_hb.pack_end(launcher_button)

        self.tab_tbv = Adw.ToolbarView(
            content=self.tabview
        )
        self.tab_tbv.add_top_bar(self.tab_hb)
        self.bottom_bar = None

        self.taboverview = Adw.TabOverview(
            view=self.tabview,
            child=self.tab_tbv
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
                    language='auto',
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
                'builder': Camera
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
                    'builder': LiveChat
                }
            )

        if importlib.util.find_spec('whisper'):
            default_activities.append(
                {
                    'title': _('Transcriber'),
                    'icon': 'music-note-single-symbolic',
                    'builder': Transcriber
                }
            )

        if importlib.util.find_spec('rembg'):
            default_activities.append(
                {
                    'title': _('Background Remover'),
                    'icon': 'image-missing-symbolic',
                    'builder': BackgroundRemover
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
            icon_name='shapes-symbolic',
            child=listbox
        )
        launcher_tbv = Adw.ToolbarView(
            content=launcher,
            extend_content_to_top_edge=True
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
            tab_page = self.tabview.append(page)
            if activity.get('runner'):
                activity.get('runner')(page)
            tab_page.set_title(page.title)
            tab_page.set_icon(Gio.ThemedIcon.new(page.activity_icon))

    def page_closed(self, tabview, tabpage):
        tabpage.get_child().on_close()

    def page_attached(self, tabview, tabpage, index):
        tabpage.set_title(tabpage.get_child().title)
        tabpage.set_icon(Gio.ThemedIcon.new(tabpage.get_child().activity_icon))
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
            selected_child = tabview.get_selected_page().get_child()
            self.navigationview.find_page('tab').set_title(selected_child.title)
            if self.bottom_bar:
                self.tab_tbv.remove(self.bottom_bar)
                self.bottom_bar = None

            self.bottom_bar = generate_action_bar(selected_child, self.tabview)
            if self.bottom_bar:
                self.tab_tbv.add_bottom_bar(self.bottom_bar)
                for css_class in selected_child.buttons.get('css', []):
                    self.bottom_bar.add_css_class(css_class)
            if selected_child.extend_to_edge and selected_child.__gtype_name__ != 'AlpacaLiveChat':
                self.tab_hb.add_css_class('osd')
                if self.bottom_bar:
                    self.bottom_bar.add_css_class('osd')
            else:
                self.tab_hb.remove_css_class('osd')
            self.tab_tbv.set_extend_content_to_bottom_edge(selected_child.extend_to_edge)
            self.tab_tbv.set_extend_content_to_top_edge(selected_child.extend_to_edge)

    def reattach_current_activity(self, button):
        tabview = self.get_root().application.main_alpaca_window.activities_page.get_child().tabview
        self.tabview.transfer_page(
            self.tabview.get_selected_page(),
            tabview,
            0
        )
        if len(self.tabview.get_pages()) == 0:
            self.get_root().close()

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
        self.activity_manager = ActivityManager(reattach=True)
        self.application = application
        super().__init__(
            content=self.activity_manager,
            title=_('Activities')
        )
        self.connect('close-request', lambda *_: self.close())

    def get_application(self):
        return self.application

    def close(self):
        if self.activity_manager:
            if self.activity_manager.tabview:
                for page in list(self.activity_manager.tabview.get_pages()):
                    self.activity_manager.tabview.close_page(page)
            self.set_child()
            self.activity_manager = None
        super().close()

def generate_action_bar(page:Gtk.Widget, tabview:Gtk.Widget=None):
    if not page or page.__gtype_name__ == 'AlpacaLiveChat':
        return
    action_bar = Gtk.ActionBar(
        valign=2
    )

    for btn in page.buttons.get('start', []):
        btn.unparent()
        action_bar.pack_start(btn)

    if page.buttons.get('center'):
        page.buttons.get('center').unparent()
        action_bar.set_center_widget(page.buttons.get('center'))

    if tabview:
        close_button = Gtk.Button(
            tooltip_text=_('Close Activity'),
            icon_name='window-close-symbolic',
            css_classes=['flat'],
            valign=3
        )
        close_button.connect('clicked', lambda button, tv=tabview: tv.close_page(tabview.get_selected_page()))
        action_bar.pack_end(close_button)

    for btn in page.buttons.get('end', []):
        btn.unparent()
        action_bar.pack_end(btn)

    return action_bar

def show_activity(page:Gtk.Widget, root:Gtk.Widget, force_dialog:bool=False):
    if not page or page.get_parent():
        return

    if root.get_name() == 'AlpacaQuickAsk':
        force_dialog = True

    if root.get_name() == 'AlpacaWindow' and root.settings.get_value('activity-mode').unpack() == 0 and not force_dialog:
        tab_page = root.activities_page.get_child().tabview.append(page)
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

        tab_page = last_activity_tabview.append(page)
        return tab_page.get_child()

def launch_detached_activity(page:Gtk.Widget, root):
    if not page or page.get_parent():
        return

    global last_activity_tabview
    if not last_activity_tabview or not last_activity_tabview.get_root():
        atw = ActivityTabWindow(root.get_application())
        atw.present()
        last_activity_tabview = atw.activity_manager.tabview

    last_activity_tabview.append(page)

# Activity names for console arguments (e.g. --activity "camera")
ARGUMENT_ACTIVITIES = {
    'web-browser': WebBrowser,
    'terminal': Terminal,
    'attachment-creator': AttachmentCreator,
    'camera': Camera
}

if importlib.util.find_spec('kokoro') and importlib.util.find_spec('sounddevice'):
    ARGUMENT_ACTIVITIES['live-chat'] = LiveChat

if importlib.util.find_spec('whisper'):
    ARGUMENT_ACTIVITIES['transcriber'] = Transcriber

if importlib.util.find_spec('rembg'):
    ARGUMENT_ACTIVITIES['background-remover'] = BackgroundRemover

