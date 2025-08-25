# activities.py

from gi.repository import Gtk, Gio, Adw, GLib

class ActivityPage(Gtk.Overlay):
    __gtype_name__ = 'AlpacaActivityPage'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        self.tab = None
        super().__init__(
            child=self.page,
            css_classes=self.page.activity_css
        )
        buttons_container = Gtk.Box(
            css_classes=['linked', 'r10', 'osd'],
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
            valign=2,
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

        if len(self.page.buttons) > 0:
            buttons_container.append(Gtk.Separator())
        buttons_container.append(close_button)

        self.add_overlay(buttons_container)

    def close(self):
        self.page.on_close()
        if self.page.get_parent():
            if self.tab:
                self.get_root().activities_tab_view.close_page(self.tab)
            self.tab = None
            self.page = None
            self = None

    def reload(self):
        if self.tab:
            self.get_root().activities_tab_view.set_selected_page(self.tab)
        self.page.on_reload()

class ActivityDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaActivityDialog'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        tbv=Adw.ToolbarView(css_classes=self.page.activity_css)
        hb = Adw.HeaderBar()
        for btn in page.buttons:
            if btn.get_parent():
                btn.get_parent().remove(btn)
            if isinstance(btn, Gtk.Stack):
                for box in list(btn):
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

class ActivityTabWindow(Adw.Window):
    __gtype_name__ = 'AlpacaActivityTabWindow'

    def __init__(self):
        self.activities_tab_view = Adw.TabView()
        self.activities_tab_view.connect('close-page', self.tab_closed)
        self.activities_tab_view.connect('notify::selected-page', self.tab_changed)
        self.activities_tab_view.connect('page-detached', self.tab_detached)
        self.settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        tbv = Adw.ToolbarView(
            content=self.activities_tab_view
        )
        hb = Adw.HeaderBar()
        tbv.add_top_bar(hb)
        tab_overview = Adw.TabOverview(
            child=tbv,
            view=self.activities_tab_view
        )
        overview_button = Adw.TabButton(
            view=self.activities_tab_view,
            action_name='overview.open'
        )
        overview_button.connect('clicked', lambda btn: tab_overview.set_open(True))
        hb.pack_start(overview_button)

        super().__init__(
            content=tab_overview,
            title=_('Activities')
        )
        self.connect('close-request', lambda *_: self.close())

    def tab_closed(self, tabview, tabpage):
        tabpage.get_child().page.on_close()

    def tab_detached(self, tabview, tabpage, index):
        if len(tabview.get_pages()) == 0:
            self.close()

    def tab_changed(self, tabview, gparam):
        if tabview.get_selected_page():
            self.set_title(tabview.get_selected_page().get_child().page.title)

    def close(self):
        if self.activities_tab_view:
            for page in list(self.activities_tab_view.get_pages()):
                self.activities_tab_view.close_page(page)
        self.set_child()
        self.activities_tab_view = None
        super().close()

def show_activity(page:Gtk.Widget, root:Gtk.Widget, force_dialog:bool=False):
    if not page.get_parent():
        if root.get_name() == 'AlpacaWindow' and root.settings.get_value('activity-mode').unpack() == 0 and not force_dialog:
            tab_page = root.activities_tab_view.append(ActivityPage(page))
            tab_page.set_title(page.title)
            tab_page.set_icon(Gio.ThemedIcon.new(page.activity_icon))
            tab_page.get_child().tab = tab_page
            return tab_page.get_child()
        elif root.settings.get_value('activity-mode').unpack() == 1 or force_dialog:
            dialog = ActivityDialog(page)
            dialog.present(root)
            return dialog
        else:
            alpaca_window = root.get_application().main_alpaca_window
            if not alpaca_window.last_external_activity_tabview or not alpaca_window.last_external_activity_tabview.get_root():
                alpaca_window.last_external_activity_tabview = alpaca_window.activities_window_create()

            tab_page = alpaca_window.last_external_activity_tabview.append(ActivityPage(page))
            tab_page.set_title(page.title)
            tab_page.set_icon(Gio.ThemedIcon.new(page.activity_icon))
            tab_page.get_child().tab = tab_page
            alpaca_window.last_external_activity_tabview.set_selected_page(tab_page)
            return tab_page.get_child()


