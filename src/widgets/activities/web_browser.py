# web_browser.py

from gi.repository import Gtk, Gio, Adw, GLib, Gdk, WebKit
from .. import dialog, attachments, models
from ...sql_manager import generate_uuid, Instance as SQL
from ...constants import cache_dir
from markitdown import MarkItDown
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import tempfile, os, threading, requests, random

@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/activities/web_browser.ui')
class WebBrowser(WebKit.WebView):
    __gtype_name__ = 'AlpacaWebBrowser'

    back_button = Gtk.Template.Child()
    forward_button = Gtk.Template.Child()
    url_entry = Gtk.Template.Child()
    attachment_stack = Gtk.Template.Child()
    menu_button = Gtk.Template.Child()

    def __init__(self, default_url:str=None):
        super().__init__()
        settings = Gio.Settings(schema_id="com.jeffser.Alpaca")
        self.default_url = default_url or settings.get_value('activity-webbrowser-homepage-url').unpack()
        web_settings = WebKit.Settings()
        web_settings.set_enable_fullscreen(False)
        self.set_settings(web_settings)

        self.on_load_callback=lambda:None

        actions = [[{
            'label': _('Reload Page'),
            'callback': self.reload,
            'icon': 'update-symbolic'
        },{
            'label': _('Open in External Browser'),
            'callback': lambda: Gio.AppInfo.launch_default_for_uri(self.get_uri()),
            'icon': 'globe-symbolic'
        },{
            'label': _('Go to Home'),
            'callback': lambda: self.load_uri(self.default_url),
            'icon': 'go-home-symbolic'
        }]]
        popover = dialog.Popover(actions)
        popover.set_has_arrow(True)
        popover.set_halign(0)
        self.menu_button.set_popover(popover)

        self.load_uri(self.default_url)

        # Activity
        self.title=_("Web Browser")
        self.activity_icon = 'globe-symbolic'
        self.buttons = {
            'start': [self.back_button, self.forward_button],
            'center': self.url_entry,
            'end': [self.attachment_stack, self.menu_button]
        }
        self.extend_to_edge = False

    @Gtk.Template.Callback()
    def title_changed(self, webview, gparam):
        self.title = webview.get_title() or _('Web Browser')
        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.get_page(self).set_title(self.title)

    @Gtk.Template.Callback()
    def url_entry_focus_enter(self, controller):
        GLib.idle_add(self.url_entry.select_region, 0, -1)
        for btn in [self.forward_button, self.attachment_stack, self.menu_button]:
            btn.set_visible(False)

    @Gtk.Template.Callback()
    def url_entry_focus_leave(self, controller):
        GLib.idle_add(self.url_entry.select_region, 0, 0)
        for btn in [self.forward_button, self.attachment_stack, self.menu_button]:
            btn.set_visible(True)

    @Gtk.Template.Callback()
    def on_url_activate(self, entry):
        url = entry.get_text().strip()
        if url.startswith("http://") or url.startswith("https://"):
            self.load_uri(url)
        elif '.' in url and ' ' not in url:
            self.load_uri('https://{}'.format(url))
        else:
            self.load_uri(self.get_root().settings.get_value('activity-webbrowser-query-url').unpack().format(url))

    @Gtk.Template.Callback()
    def on_create(self, webview, navigation_action):
        # Called when a new WebView would normally be created (new tab/window)
        uri_request = navigation_action.get_request()
        uri = uri_request.get_uri()

        webview.load_uri(uri)
        return None

    @Gtk.Template.Callback()
    def on_load_changed(self, webview, event):
        uri = webview.get_uri()
        if uri:
            self.url_entry.set_text(uri)

        self.back_button.set_sensitive(self.can_go_back())
        self.forward_button.set_sensitive(self.can_go_forward())
        if event == 0: #started
            self.attachment_stack.set_visible_child_name('loading')
        elif event == 1: #redirected
            pass
        elif event == 2: #commited
            pass
        if event == 3: #finished
            self.attachment_stack.set_visible_child_name('button')
            self.on_load_callback()

        parent = self.get_ancestor(Adw.TabView)
        if parent:
            parent.get_page(self).set_loading(not event==3)

    @Gtk.Template.Callback()
    def on_back_clicked(self, button):
        if self.can_go_back():
            self.go_back()

    @Gtk.Template.Callback()
    def on_forward_clicked(self, button):
        if self.can_go_forward():
            self.go_forward()

    def extract_html(self, save_func:callable):
        def on_evaluated(webview, res, user_data):
            raw_html = webview.evaluate_javascript_finish(res).to_string()
            save_func(raw_html)

        script = 'document.documentElement.outerHTML'
        self.evaluate_javascript(
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

        self.evaluate_javascript(
            script,
            len(script.encode('utf-8')),
            None,
            None,
            None,
            on_evaluated,
            None
        )

    @Gtk.Template.Callback()
    def attach_clicked(self, button):
        self.attachment_requested(self.save)

    def attachment_requested(self, save_func:callable):
        if self.get_uri().startswith('https://www.youtube.com'):
            save_func(attachments.extract_content('youtube', self.get_uri()))
        else:
            self.extract_md(save_func)

    def save(self, result):
        attachment = attachments.Attachment(
            file_id='-1',
            file_name=self.get_title(),
            file_type='youtube' if result.startswith('# YouTube') else 'website',
            file_content=result
        )
        self.get_root().get_application().get_main_window().global_footer.attachment_container.add_attachment(attachment)

    def on_close(self):
        self.terminate_web_process()

    def on_reload(self):
        pass

    # Call on different thread
    def automate_search(self, save_func:callable, search_term:str, auto_choice:bool):
        query_url = self.get_root().settings.get_value('activity-webbrowser-query-url').unpack()
        def on_result_load():
            query_hostname = urlparse(query_url).hostname.lower()
            if query_hostname.startswith('www.'):
                query_hostname = query_hostname[4:]
            current_hostname = urlparse(self.get_uri()).hostname.lower()
            if current_hostname.startswith('www.'):
                current_hostname = current_hostname[4:]
            if not query_hostname == current_hostname:
                self.on_load_callback = lambda: None
                self.attachment_requested(save_func)
                self.close()

        def on_html_extracted(raw_html):
            self.on_load_callback = lambda: threading.Thread(target=on_result_load, daemon=True).start()
            if auto_choice:
                soup = BeautifulSoup(raw_html, "html.parser")
                # I know, really sofisticated
                results = soup.select('a.result-title') + soup.select('a[data-testid="result-title-a"]') + soup.select('a:has(h3)')
                if len(results) > 0:
                    result = random.choice(results[min(5, len(results)):])
                    GLib.timeout_add(5000, self.load_uri, result["href"])

        def on_search_page_ready():
            GLib.timeout_add(5000, self.extract_html, on_html_extracted)

        self.on_load_callback = lambda: threading.Thread(target=on_search_page_ready, daemon=True).start()
        GLib.timeout_add(5000, self.load_uri, query_url.format(search_term))

    def close(self):
        # Only close if it's a dialog
        parent = self.get_ancestor(Adw.Dialog)
        if parent:
            parent.close()

