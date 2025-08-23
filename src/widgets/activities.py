# activities.py

from gi.repository import Gtk, Gio, Adw, GLib

class ActivityPage(Gtk.Overlay):
    __gtype_name__ = 'AlpacaActivityPage'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        self.tab = None
        super().__init__(
            child=Gtk.ScrolledWindow(
                child=self.page,
                hexpand=True,
                vexpand=True,
                propagate_natural_width=True,
                propagate_natural_height=True,
                css_classes=['undershoot-bottom'],
                max_content_width=500
            ),
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

        for btn in self.page.buttons + [Gtk.Separator(), close_button]:
            buttons_container.append(btn)
            btn.add_css_class('flat')

        self.add_overlay(buttons_container)

    def close(self):
        if self.tab:
            self.get_root().activities_tab_view.close_page(self.tab)
        self.tab = None
        self.page = None
        self = None

class ActivityDialog(Adw.Dialog):
    __gtype_name__ = 'AlpacaActivityDialog'

    def __init__(self, page:Gtk.Widget):
        self.page = page
        tbv=Adw.ToolbarView(css_classes=self.page.activity_css)
        hb = Adw.HeaderBar()
        for btn in page.buttons:
            hb.pack_start(btn)
            btn.add_css_class('flat')
        tbv.add_top_bar(hb)
        tbv.set_content(Gtk.ScrolledWindow(
            child=self.page,
            hexpand=True,
            vexpand=True,
            propagate_natural_width=True,
            propagate_natural_height=True,
            css_classes=['undershoot-bottom'],
            max_content_width=500
        ))

        super().__init__(
            child=tbv,
            title=self.page.title,
            content_width=500,
            content_height=600
        )

        self.connect('closed', lambda *_: self.page.close())

class ActivityTabWindow(Adw.Window):
    __gtype_name__ = 'AlpacaActivityTabWindow'

    def __init__(self):
        self.activities_tab_view = Adw.TabView()
        self.activities_tab_view.connect('close-page', self.tab_closed)
        self.activities_tab_view.connect('notify::selected-page', self.tab_changed)
        tbv = Adw.ToolbarView(
            content=self.activities_tab_view
        )
        hb = Adw.HeaderBar()
        tbv.add_top_bar(hb)
        tbv.add_top_bar(Adw.TabBar(
            view=self.activities_tab_view
        ))
        tab_overview = Adw.TabOverview(
            child=tbv,
            view=self.activities_tab_view
        )
        overview_button = Gtk.Button(
            icon_name='view-grid-symbolic',
            tooltip_text=_('Overview')
        )
        overview_button.connect('clicked', lambda btn: tab_overview.set_open(True))
        hb.pack_start(overview_button)

        super().__init__(
            content=tab_overview,
            title=_('Activities')
        )

    def tab_closed(self, tabview, tabpage):
        tabpage.get_child().page.close()
        if len(tabview.get_pages()) == 1:
            self.close()

    def tab_changed(self, tabview, gparam):
        if tabview.get_selected_page():
            self.set_title(tabview.get_selected_page().get_child().page.title)

def show_activity(page:Gtk.Widget, root:Gtk.Widget, force_dialog:bool=False):
    global fun
    if not page.get_parent():
        if root.get_name() == 'AlpacaWindow' and root.settings.get_value('activity-mode').unpack() == 'sidebar' and not force_dialog:
            tab_page = root.activities_tab_view.append(ActivityPage(page))
            tab_page.set_title(page.title)
            tab_page.get_child().tab = tab_page
        else:
            dialog = ActivityDialog(page)
            dialog.present(root)


