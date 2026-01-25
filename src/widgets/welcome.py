# welcome.py

from gi.repository import Adw, Gtk, Gio
import shutil

@Gtk.Template(resource_path='/com/jeffser/Alpaca/welcome.ui')
class Welcome(Adw.NavigationPage):
    __gtype_name__ = 'AlpacaWelcome'

    welcome_previous_button = Gtk.Template.Child()
    welcome_next_button = Gtk.Template.Child()
    welcome_carousel = Gtk.Template.Child()
    install_ollama_button = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def welcome_previous_button_activate(self, button):
        self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()-1), True)

    @Gtk.Template.Callback()
    def welcome_next_button_activate(self, button):
        if button.get_label() == "Next":
            self.welcome_carousel.scroll_to(self.welcome_carousel.get_nth_page(self.welcome_carousel.get_position()+1), True)
        else:
            self.get_root().settings.set_boolean('skip-welcome', True)
            self.get_parent().replace_with_tags(['chat'])

    @Gtk.Template.Callback()
    def welcome_carousel_page_changed(self, carousel, index):
        if index == 0:
            self.welcome_previous_button.set_sensitive(False)
        else:
            self.welcome_previous_button.set_sensitive(True)
        if index == carousel.get_n_pages()-1:
            self.welcome_next_button.set_label(_("Close"))
            self.welcome_next_button.set_tooltip_text(_("Close"))
        else:
            self.welcome_next_button.set_label(_("Next"))
            self.welcome_next_button.set_tooltip_text(_("Next"))

    @Gtk.Template.Callback()
    def link_button_handler(self, button):
        try:
            Gio.AppInfo.launch_default_for_uri(button.get_name())
        except Exception as e:
            print(e)

    def __init__(self):
        super().__init__()

        if shutil.which('ollama'):
            text = _('Already Installed!')
            self.install_ollama_button.set_label(text)
            self.install_ollama_button.set_tooltip_text(text)
            self.install_ollama_button.set_sensitive(False)

