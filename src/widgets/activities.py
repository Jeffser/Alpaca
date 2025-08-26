# activities.py

from gi.repository import Gtk, Gio, Adw, GLib, GdkPixbuf, Gdk
from . import terminal, camera, dialog, attachments, models
from .tools import tools
from ..constants import IN_FLATPAK, data_dir, REMBG_MODELS
import base64, os, threading, importlib.util
from PIL import Image
from io import BytesIO

last_activity_tabview = None

class BackgroundRemoverPage(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaBackgroundRemoverPage'

    def __init__(self, save_func:callable=None, close_callback:callable=None):
        self.save_func = save_func
        self.close_callback = close_callback
        self.input_image_data = None
        self.output_image_data = None
        container = Gtk.Box(
            orientation=1,
            spacing=10,
            vexpand=True,
            css_classes=['p10']
        )

        super().__init__(
            child=container,
            hexpand=True
        )

        big_select_button = Gtk.Button(
            child=Adw.ButtonContent(
                label=_("Select Image"),
                icon_name="image-x-generic-symbolic",
                tooltip_text=_("Select Image")
            ),
            halign=3,
            valign=3,
            css_classes=['suggested-action', 'pill']
        )
        big_select_button.connect('clicked', lambda *_: self.load_image_requested())
        self.input_container = Adw.Bin(
            child=big_select_button,
            halign=3,
            vexpand=True,
            css_classes=['p10']
        )
        container.append(self.input_container)
        self.output_container = Gtk.Stack(
            visible=False,
            halign=3,
            vexpand=True,
            css_classes=['p10']
        )
        self.output_container.add_named(
            Adw.Spinner(
                width_request=140,
                height_request=140
            ),
            'loading'
        )
        self.output_container.add_named(
            Adw.Bin(),
            'result'
        )
        container.append(self.output_container)
        self.pulling_model = None

        string_list = Gtk.StringList()
        for m in REMBG_MODELS.values():
            string_list.append('{} ({})'.format(m.get('display_name'), m.get('size')) )
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda factory, list_item: list_item.set_child(Gtk.Label(ellipsize=3, xalign=0)))
        factory.connect("bind", lambda factory, list_item: list_item.get_child().set_label(list_item.get_item().get_string()))
        self.model_dropdown = Gtk.DropDown(
            model=string_list,
            factory=factory,
            halign=3
        )
        self.select_button = Gtk.Button(
            icon_name="image-x-generic-symbolic",
            tooltip_text=_("Select Image")
        )
        self.select_button.connect('clicked', lambda *_: self.load_image_requested())

        self.download_button = Gtk.Button(
            icon_name='folder-download-symbolic',
            tooltip_text=_("Download Result"),
            sensitive=False
        )
        self.download_button.connect('clicked', lambda *_: self.prompt_download())

        self.buttons = [self.model_dropdown, self.select_button, self.download_button]
        self.title = _("Background Remover")
        self.activity_icon = 'image-missing-symbolic'

    def run(self, model_name:str):
        self.output_container.set_visible_child_name('loading')
        self.output_container.set_visible(True)
        self.select_button.set_sensitive(False)
        self.download_button.set_sensitive(False)
        from rembg import remove, new_session
        session = new_session(model_name)
        input_image = Image.open(BytesIO(base64.b64decode(self.input_image_data)))
        output_image = remove(input_image, session=session)
        buffered = BytesIO()
        output_image.save(buffered, format="PNG")

        self.output_image_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        self.output_container.get_child_by_name('result').set_child(self.make_image(self.output_image_data))
        self.output_container.set_visible_child_name('result')

        self.select_button.set_sensitive(True)
        self.download_button.set_sensitive(True)
        if self.pulling_model:
            threading.Thread(target=self.pulling_model.update_progressbar, args=({'status': 'success'},)).start()
        if self.save_func:
            self.save_func(self.output_image_data)

    def prepare_model_download(self, model_name:str):
        self.pulling_model = models.pulling.PullingModelButton(
            model_name,
            lambda model_name, window=self.get_root(): models.common.prepend_added_model(window, models.image.BackgroundRemoverModelButton(model_name)),
            None,
            False
        )
        models.common.prepend_added_model(self.get_root(), self.pulling_model)
        threading.Thread(target=self.run, args=(model_name,)).start()

    def verify_model(self):
        model = list(REMBG_MODELS)[self.model_dropdown.get_selected()]
        model_dir = os.path.join(data_dir, '.u2net')
        if os.path.isdir(model_dir) and '{}.onnx'.format(model) in os.listdir(model_dir):
            threading.Thread(target=self.run, args=(model,)).start()
        else:
            GLib.idle_add(dialog.simple,
                self.get_root(),
                _('Download Background Removal Model'),
                _("To use this tool you'll need to download a special model ({})").format(REMBG_MODELS.get(model, {}).get('size')),
                lambda m=model: self.prepare_model_download(model)
            )

    def make_image(self, image_data:str):
        data = base64.b64decode(image_data)
        loader = GdkPixbuf.PixbufLoader.new()
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        height = int((pixbuf.get_property('height') * 240) / pixbuf.get_property('width'))
        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        image = Gtk.Picture.new_for_paintable(texture)
        image.set_size_request(240, height)
        return image

    def load_image(self, image_data:str):
        self.input_image_data = image_data
        image = self.make_image(self.input_image_data)
        image.add_css_class('r10')
        image.set_valign(3)
        self.input_container.set_child(image)
        self.verify_model()

    def on_attachment(self, file:Gio.File, remove_original:bool=False):
        if not file:
            return
        self.load_image(attachments.extract_image(file.get_path(), self.get_root().settings.get_value('max-image-size').unpack()))

    def load_image_requested(self):
        file_filter = Gtk.FileFilter()
        file_filter.add_pixbuf_formats()
        dialog.simple_file(
            parent = self.get_root(),
            file_filters = [file_filter],
            callback = self.on_attachment
        )

    def on_download(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            path = file.get_path()
            if path:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(self.output_image_data))
                Gio.AppInfo.launch_default_for_uri('file://{}'.format(path))
        except GLib.Error as e:
            logger.error(e)

    def prompt_download(self):
        dialog = Gtk.FileDialog(
            title=_("Save Image"),
            initial_name='output.png'
        )
        dialog.save(self.get_root(), None, self.on_download, None)

    def on_reload(self):
        pass

    def on_close(self):
        if self.close_callback:
            self.close_callback()

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
        tbv=Adw.ToolbarView(css_classes=page.get_css_classes())
        hb = Adw.HeaderBar(show_title=False)
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
                'builder': lambda: terminal.Terminal(
                    language='bash',
                    code_getter=lambda: 'bash'
                ),
                #runner is optional
                'runner': lambda term: term.run()
            },
            {
                'title': _('Create Attachment'),
                'icon': 'document-text-symbolic',
                'builder': terminal.AttachmentCreator
            },
            {
                'title': _('Camera'),
                'icon': 'camera-photo-symbolic',
                'builder': lambda: camera.show_webcam_dialog(
                    root_widget=self.get_root(),
                    attachment_func=lambda att: self.get_root().get_application().main_alpaca_window.global_footer.attachment_container.add_attachment(att),
                    return_page=True
                )
            }
        ]
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
        self.navigationview.replace_with_tags(['tab'])
        if self.get_root().get_name() == 'AlpacaWindow':
            if self.get_root().last_breakpoint_status:
                self.get_root().chat_splitview.set_show_content(False)
            else:
                self.get_root().chat_splitview.set_collapsed(False)
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
            tab_page.set_title(page.title)
            tab_page.set_icon(Gio.ThemedIcon.new(page.activity_icon))
            tab_page.get_child().tab = tab_page
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
            tab_page.set_title(page.title)
            tab_page.set_icon(Gio.ThemedIcon.new(page.activity_icon))
            tab_page.get_child().tab = tab_page
            return tab_page.get_child()


