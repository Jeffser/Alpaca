# web_browser.py

from gi.repository import Gtk, Gio, Adw, GLib, GdkPixbuf, Gdk, WebKit
from .. import dialog, attachments, models
from ...sql_manager import generate_uuid, Instance as SQL
from ...constants import cache_dir
from markitdown import MarkItDown
from bs4 import BeautifulSoup
import tempfile, os, threading, requests, time, random

class WebBrowser(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaWebBrowser'

    def __init__(self, url:str='https://www.startpage.com'):
        self.webview = WebKit.WebView()
        self.webview.load_uri(url)
        self.webview.connect('load-changed', self.on_load_changed)
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
            tooltip_text=_('Attach')
        )
        self.attachment_button.connect("clicked", lambda button: threading.Thread(target=self.extract_md(self.save)).start())


        super().__init__(
            child=self.webview
        )

        self.title=_("Web Browser")
        self.activity_icon = 'globe-symbolic'
        self.buttons = [self.back_button, self.forward_button, self.url_entry, self.attachment_button]

    def on_url_activate(self, entry):
        url = entry.get_text().strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = 'https://www.startpage.com/sp/search?query={}'.format(url)
        self.webview.load_uri(url)

    def on_load_changed(self, webview, event):
        uri = webview.get_uri()
        if uri:
            self.url_entry.set_text(uri)

        self.back_button.set_sensitive(self.webview.can_go_back())
        self.forward_button.set_sensitive(self.webview.can_go_forward())
        if event == 3:
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

    def save(self, result):
        attachment = attachments.Attachment(
            file_id='-1',
            file_name=self.webview.get_title(),
            file_type='website',
            file_content=result
        )
        self.get_root().get_application().main_alpaca_window.global_footer.attachment_container.add_attachment(attachment)

    def on_close(self):
        pass

    def on_reload(self):
        pass

    # Call on different thread
    def automate_search(self, save_func:callable, search_term:str):
        def on_result_load():
            self.on_load_callback = lambda: None
            self.extract_md(save_func)
            self.close()

        def on_html_extracted(raw_html):
            soup = BeautifulSoup(raw_html, "html.parser")
            # I know, really sofisticated
            result = random.choice(soup.select('a.result-title')[5:])
            self.on_load_callback = threading.Thread(target=on_result_load).start
            time.sleep(5)
            self.webview.load_uri(result["href"])

        def on_search_page_ready():
            self.extract_html(on_html_extracted)
            time.sleep(5)

        time.sleep(5)
        self.on_load_callback = threading.Thread(target=on_search_page_ready).start
        self.webview.load_uri('https://www.startpage.com/sp/search?query={}'.format(search_term))

    def close(self):
        # Only close if it's a dialog
        parent = self.get_ancestor(Adw.Dialog)
        if parent:
            parent.close()
