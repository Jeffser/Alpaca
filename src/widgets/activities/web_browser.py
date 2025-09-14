# web_browser.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, WebKit
from .. import dialog, attachments, models
from ...sql_manager import generate_uuid, Instance as SQL
from ...constants import cache_dir
from markitdown import MarkItDown
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import tempfile, os, threading, requests, random

class WebBrowser(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaWebBrowser'

    def __init__(self, default_url:str=None):
        settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        self.default_url = default_url or settings.get_value('activity-webbrowser-homepage-url').unpack()
        self.webview = WebKit.WebView()
        self.webview.connect('load-changed', self.on_load_changed)
        self.webview.connect('create', self.on_create)
        self.on_load_callback=lambda:None

        self.back_button = Gtk.Button(
            icon_name='left-symbolic',
            tooltip_text=_('Go Back'),
            sensitive=False
        )
        self.back_button.connect("clicked", self.on_back_clicked)

        self.forward_button = Gtk.Button(
            icon_name='right-symbolic',
            tooltip_text=_('Go Next'),
            sensitive=False
        )
        self.forward_button.connect("clicked", self.on_forward_clicked)

        self.url_entry = Gtk.Entry(
            placeholder_text=_('Enter URL...'),
            css_classes=['p5'],
            overflow=1,
            hexpand=True
        )
        self.url_entry.connect('activate', self.on_url_activate)
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect("enter", lambda c: GLib.idle_add(self.url_entry.select_region, 0, -1))
        focus_controller.connect("leave", lambda c: GLib.idle_add(self.url_entry.select_region, 0, 0))
        self.url_entry.add_controller(focus_controller)


        self.attachment_button = Gtk.Button(
            icon_name='chain-link-loose-symbolic',
            tooltip_text=_('Attach'),
            css_classes=['br0', 'flat']
        )
        self.attachment_button.connect("clicked", lambda button: threading.Thread(target=self.attachment_requested(self.save)).start())
        #self.attachment_button.connect("clicked", lambda button:  )
        self.attachment_stack = Gtk.Stack(transition_type=1)
        self.attachment_stack.add_named(self.attachment_button, 'button')
        self.attachment_stack.add_named(Adw.Spinner(css_classes=['p10']), 'loading')

        actions = [[{
            'label': _('Reload Page'),
            'callback': self.webview.reload,
            'icon': 'update-symbolic'
        },{
            'label': _('Open in External Browser'),
            'callback': lambda: Gio.AppInfo.launch_default_for_uri(self.webview.get_uri()),
            'icon': 'globe-symbolic'
        },{
            'label': _('Go to Home'),
            'callback': lambda: self.webview.load_uri(self.default_url),
            'icon': 'go-home-symbolic'
        },{
            'label': _('Browser Preferences'),
            'callback': lambda: WebBrowserPreferences().present(self.get_root()),
            'icon': 'wrench-wide-symbolic'
        }]]
        popover = dialog.Popover(actions)
        popover.set_has_arrow(True)
        popover.set_halign(0)
        menu_button = Gtk.MenuButton(
            icon_name='view-more-symbolic',
            popover=popover,
            direction=0
        )

        super().__init__(
            child=self.webview
        )

        self.webview.load_uri(self.default_url)

        # Activity
        self.title=_("Web Browser")
        self.activity_icon = 'globe-symbolic'
        self.buttons = [self.back_button, self.forward_button, self.url_entry, self.attachment_stack, menu_button]

    def on_url_activate(self, entry):
        url = entry.get_text().strip()
        if url.startswith("http://") or url.startswith("https://"):
            self.webview.load_uri(url)
        elif '.' in url and ' ' not in url:
            self.webview.load_uri('https://{}'.format(url))
        else:
            url = self.get_root().settings.get_value('activity-webbrowser-query-url').unpack().format(url)


    def on_create(self, webview, navigation_action):
        # Called when a new WebView would normally be created (new tab/window)
        uri_request = navigation_action.get_request()
        uri = uri_request.get_uri()

        webview.load_uri(uri)
        return None

    def on_load_changed(self, webview, event):
        uri = webview.get_uri()
        if uri:
            self.url_entry.set_text(uri)

        self.back_button.set_sensitive(self.webview.can_go_back())
        self.forward_button.set_sensitive(self.webview.can_go_forward())
        if event == 0: #started
            self.attachment_stack.set_visible_child_name('loading')
        elif event == 1: #redirected
            pass
        elif event == 2: #commited
            pass
        if event == 3: #finished
            self.attachment_stack.set_visible_child_name('button')
            self.on_load_callback()

    def on_back_clicked(self, button):
        if self.webview.can_go_back():
            self.webview.go_back()

    def on_forward_clicked(self, button):
        if self.webview.can_go_forward():
            self.webview.go_forward()

    def extract_html(self, save_func:callable):
        def on_evaluated(webview, res, user_data):
            raw_html = webview.evaluate_javascript_finish(res).to_string()
            save_func(raw_html)

        script = 'document.documentElement.outerHTML'
        self.webview.evaluate_javascript(
            script,
            len(script.encode('utf-8')),
            None,
            None,
            None,
            on_evaluated,
            None
        )

    def extract_md(self, save_func:callable):
        def on_evaluated(webview, res, user_data):
            md = MarkItDown(enable_plugins=False)
            raw_html = webview.evaluate_javascript_finish(res).to_string()
            markdown_text = ''
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as tmp_file:
                tmp_file.write(raw_html)
                markdown_text = md.convert(tmp_file.name).text_content

            markdown_text = markdown_text.replace('![](data:image/svg+xml;base64...)', '')
            save_func(markdown_text)


        readability_path = os.path.join(cache_dir, 'Readability.js')
        if not os.path.isfile(readability_path):
            response = requests.get('https://raw.githubusercontent.com/mozilla/readability/refs/heads/main/Readability.js', stream=True)
            with open(readability_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        with open(readability_path) as f:
            script = f.read() + """
            (function() {
                var docClone = document.cloneNode(true);
                var article = new Readability(docClone).parse();
                return document.documentElement.outerHTML;
                return article ? article.content : document.documentElement.outerHTML;
            })();
            """

        self.webview.evaluate_javascript(
            script,
            len(script.encode('utf-8')),
            None,
            None,
            None,
            on_evaluated,
            None
        )

    def attachment_requested(self, save_func:callable):
        if self.webview.get_uri().startswith('https://www.youtube.com'):
            save_func(attachments.extract_content('youtube', self.webview.get_uri()))
        else:
            self.extract_md(save_func)

    def save(self, result):
        attachment = attachments.Attachment(
            file_id='-1',
            file_name=self.webview.get_title(),
            file_type='youtube' if result.startswith('# YouTube') else 'website',
            file_content=result
        )
        self.get_root().get_application().main_alpaca_window.global_footer.attachment_container.add_attachment(attachment)

    def on_close(self):
        self.webview.terminate_web_process()

    def on_reload(self):
        pass

    # Call on different thread
    def automate_search(self, save_func:callable, search_term:str, auto_choice:bool):
        query_url = self.get_root().settings.get_value('activity-webbrowser-query-url').unpack()
        def on_result_load():
            query_hostname = urlparse(query_url).hostname.lower()
            if query_hostname.startswith('www.'):
                query_hostname = query_hostname[4:]
            current_hostname = urlparse(self.webview.get_uri()).hostname.lower()
            if current_hostname.startswith('www.'):
                current_hostname = current_hostname[4:]
            if not query_hostname == current_hostname:
                self.on_load_callback = lambda: None
                self.attachment_requested(save_func)
                self.close()

        def on_html_extracted(raw_html):
            self.on_load_callback = lambda: threading.Thread(target=on_result_load).start()
            if auto_choice:
                soup = BeautifulSoup(raw_html, "html.parser")
                # I know, really sofisticated
                results = soup.select('a.result-title') + soup.select('a[data-testid="result-title-a"]') + soup.select('a:has(h3)')
                result = random.choice(results[5:])
                GLib.timeout_add(5000, self.webview.load_uri, result["href"])

        def on_search_page_ready():
            GLib.timeout_add(5000, self.extract_html, on_html_extracted)

        self.on_load_callback = lambda: threading.Thread(target=on_search_page_ready).start()
        GLib.timeout_add(5000, self.webview.load_uri, query_url.format(search_term))

    def close(self):
        # Only close if it's a dialog
        parent = self.get_ancestor(Adw.Dialog)
        if parent:
            parent.close()

class WebBrowserPreferences(Adw.PreferencesDialog):
    __gtype_name__ = 'AlpacaWebBrowserPreferences'

    presets = [
        ['https://startpage.com/sp/search?query={}', 'https://startpage.com'],
        ['https://duckduckgo.com/?q={}', 'https://duckduckgo.com/'],
        ['https://google.com/search?q={}', 'https://google.com']
    ]

    def __init__(self):
        super().__init__(
            follows_content_size=True
        )
        settings = Gio.Settings(schema_id="com.jeffser.Alpaca")

        preferences_page = Adw.PreferencesPage()
        self.add(preferences_page)

        preferences_group = Adw.PreferencesGroup()
        preferences_page.add(preferences_group)

        search_presets_el = Adw.ComboRow(
            title=_('Search Engine')
        )

        string_list = Gtk.StringList()
        string_list.append('Startpage')
        string_list.append('DuckDuckGo')
        string_list.append('Google')
        string_list.append(_('Custom'))

        search_presets_el.set_model(string_list)

        selected_index = len(self.presets)
        for i, preset in enumerate(self.presets):
            if preset[0] == settings.get_value('activity-webbrowser-query-url').unpack() and preset[1] == settings.get_value('activity-webbrowser-homepage-url').unpack():
                selected_index=i
        search_presets_el.set_selected(selected_index)
        search_presets_el.connect('notify::selected', self.on_preset_change)
        preferences_group.add(search_presets_el)

        self.search_query_url_el = Adw.EntryRow(
            title=_('Search Query URL'),
            visible=search_presets_el.get_selected() == len(self.presets)
        )
        preferences_group.add(self.search_query_url_el)
        settings.bind('activity-webbrowser-query-url', self.search_query_url_el, 'text', Gio.SettingsBindFlags.DEFAULT)

        self.homepage_url_el = Adw.EntryRow(
            title=_('Homepage URL'),
            visible=search_presets_el.get_selected() == len(self.presets)
        )
        preferences_group.add(self.homepage_url_el)
        settings.bind('activity-webbrowser-homepage-url', self.homepage_url_el, 'text', Gio.SettingsBindFlags.DEFAULT)

    def on_preset_change(self, combo, gparam):
        selected_index = combo.get_selected()
        if selected_index < len(self.presets):
            self.search_query_url_el.set_text(self.presets[selected_index][0])
            self.homepage_url_el.set_text(self.presets[selected_index][1])

        self.search_query_url_el.set_visible(not selected_index < len(self.presets))
        self.homepage_url_el.set_visible(not selected_index < len(self.presets))
