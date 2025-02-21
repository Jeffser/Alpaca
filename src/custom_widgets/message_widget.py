#message_widget.py
"""
Handles the message widget (testing)
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GObject, Gio, Adw, GtkSource, GLib, Gdk, GdkPixbuf
import logging, os, datetime, re, shutil, threading, sys, base64, tempfile, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.mathtext as mathtext
from PIL import Image
from ..internal import config_dir, data_dir, cache_dir, source_dir
from .table_widget import TableWidget
from . import dialog_widget, terminal_widget, model_manager_widget

logger = logging.getLogger(__name__)

window = None

language_fallback = {
    'bash': 'sh',
    'cmd': 'powershell',
    'batch': 'powershell',
    'c#': 'csharp',
    'vb.net': 'vbnet'
}

markup_pattern = re.compile(r'<(b|u|tt|a.*|span.*)>(.*?)<\/(b|u|tt|a|span)>')

patterns = [
    ('think', re.compile(r'<think>\n+(.*?)\n+<\/think>', re.DOTALL)),
    ('code', re.compile(r'```([a-zA-Z0-9_+\-]*)\n(.*?)\n\s*```', re.DOTALL)),
    ('code', re.compile(r'`(\w*)\n(.*?)\n\s*`', re.DOTALL)),
    ('table', re.compile(r'((?:\| *[^|\r\n]+ *)+\|)(?:\r?\n)((?:\|[ :]?-+[ :]?)+\|)((?:(?:\r?\n)(?:\| *[^|\r\n]+ *)+\|)+)', re.MULTILINE)),
    ('latex', re.compile(r'^\s+\\\[\n(.*?)\n\s+\\\]|^\s+\$(.*?)\$', re.MULTILINE))
]

class edit_text_block(Gtk.Box):
    __gtype_name__ = 'AlpacaEditTextBlock'

    def __init__(self, text:str):
        super().__init__(
            halign=0,
            spacing=5,
            orientation=1
        )
        self.text_view = Gtk.TextView(
            halign=0,
            css_classes=["view", "editing_message_textview"],
            wrap_mode=2
        )
        cancel_button = Gtk.Button(
            vexpand=False,
            valign=2,
            halign=1,
            tooltip_text=_("Cancel"),
            css_classes=['flat', 'circular', 'dim-label'],
            icon_name='cross-large-symbolic'
        )
        cancel_button.connect('clicked', lambda *_: self.cancel_edit())
        save_button = Gtk.Button(
            vexpand=False,
            valign=2,
            halign=1,
            tooltip_text=_("Save Message"),
            css_classes=['flat', 'circular', 'dim-label'],
            icon_name='paper-plane-symbolic'
        )
        save_button.connect('clicked', lambda *_: self.save_edit())
        self.append(self.text_view)

        button_container = Gtk.Box(
            halign=1,
            spacing=5
        )
        button_container.append(cancel_button)
        button_container.append(save_button)
        self.append(button_container)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.handle_key)
        self.text_view.add_controller(key_controller)
        self.text_view.connect('realize', lambda *_: self.set_text(text))

    def set_text(self, text:str):
        buffer = self.text_view.get_buffer()
        buffer.delete(buffer.get_start_iter(), buffer.get_end_iter())
        buffer.insert(buffer.get_start_iter(), text, len(text.encode('utf8')))
        GLib.idle_add(self.text_view.set_vexpand, True)
        GLib.idle_add(self.text_view.set_vexpand, False)

    def handle_key(self, controller, keyval, keycode, state):
        if keyval==Gdk.KEY_Return and not (state & Gdk.ModifierType.SHIFT_MASK):
            self.save_edit()
            return True
        elif keyval==Gdk.KEY_Escape:
            self.cancel_edit()
            return True

    def save_edit(self):
        message_element = self.get_parent().get_parent()
        message_element.set_text(self.text_view.get_buffer().get_text(self.text_view.get_buffer().get_start_iter(), self.text_view.get_buffer().get_end_iter(), False))
        window.sql_instance.insert_or_update_message(message_element)
        self.get_parent().remove(self)
        message_element.set_hexpand(message_element.bot)
        message_element.set_halign(0 if message_element.bot else 2)
        window.show_toast(_("Message edited successfully"), window.main_overlay)

    def cancel_edit(self):
        message_element = self.get_parent().get_parent()
        message_element.set_text(message_element.text)
        message_element.set_hexpand(message_element.bot)
        message_element.set_halign(0 if message_element.bot else 2)
        self.get_parent().remove(self)

class text_block(Gtk.Label):
    __gtype_name__ = 'AlpacaTextBlock'

    def __init__(self, bot:bool, system:bool):
        super().__init__(
            hexpand=True,
            halign=0,
            wrap=True,
            wrap_mode=2,
            xalign=0,
            focusable=True,
            selectable=True,
            css_classes=['dim-label'] if system else [],
            justify=2 if system else 0
        )
        self.raw_text = ''
        if bot:
            self.update_property([4, 7], [_("Response message"), False])
        elif system:
            self.update_property([4, 7], [_("System message"), False])
        else:
            self.update_property([4, 7], [_("User message"), False])
        self.connect('notify::has-focus', lambda *_: GLib.idle_add(self.remove_selection) if self.has_focus() else None)

    def remove_selection(self):
        self.set_selectable(False)
        self.set_selectable(True)

class generating_text_block(Gtk.TextView):
    __gtype_name__ = 'AlpacaGeneratingTextBlock'

    def __init__(self):
        super().__init__(
            hexpand=True,
            halign=0,
            editable=False,
            wrap_mode=3,
            css_classes=['flat']
        )
        self.buffer = self.get_buffer()

    def get_text(self) -> str:
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

class code_block(Gtk.Box):
    __gtype_name__ = 'AlpacaCodeBlock'

    def __init__(self, text:str, language_name:str=None):
        super().__init__(
            css_classes=["card", "code_block"],
            orientation=1,
            overflow=1,
            margin_start=5,
            margin_end=5
        )

        self.language = None
        self.language_name = language_name
        if self.language_name:
            self.language = GtkSource.LanguageManager.get_default().get_language(language_fallback.get(self.language_name.lower(), self.language_name))
        if self.language:
            self.buffer = GtkSource.Buffer.new_with_language(self.language)
        else:
            self.buffer = GtkSource.Buffer()
        self.buffer.set_style_scheme(GtkSource.StyleSchemeManager.get_default().get_scheme('Adwaita-dark'))
        self.source_view = GtkSource.View(
            auto_indent=True, indent_width=4, buffer=self.buffer, show_line_numbers=True, editable=None,
            top_margin=6, bottom_margin=6, left_margin=12, right_margin=12, css_classes=["code_block"]
        )
        self.source_view.update_property([4], [_("{}Code Block").format('{} '.format(self.language_name.title()) if self.language else "")])
        title_box = Gtk.Box(margin_start=12, margin_top=3, margin_bottom=3, margin_end=12, spacing=5)
        title_box.append(Gtk.Label(label=self.language_name.title() if self.language_name else _("Code Block"), hexpand=True, xalign=0))
        copy_button = Gtk.Button(icon_name="edit-copy-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Copy Message"))
        copy_button.connect("clicked", lambda *_: self.on_copy())
        title_box.append(copy_button)
        self.run_button = None
        self.edit_button = Gtk.Button(icon_name="edit-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Edit Code Block"))
        self.edit_button.connect('clicked', self.start_edit)
        title_box.append(self.edit_button)

        self.cancel_edit_button = Gtk.Button(icon_name="cross-large-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Cancel"), visible=False)
        self.cancel_edit_button.connect('clicked', self.cancel_edit)
        title_box.append(self.cancel_edit_button)

        self.save_edit_button = Gtk.Button(icon_name="paper-plane-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Save"), visible=False)
        self.save_edit_button.connect('clicked', self.save_edit)
        title_box.append(self.save_edit_button)
        if self.language_name and self.language_name.lower() in ('bash', 'sh', 'python', 'python3', 'py', 'py3', 'c++', 'cpp', 'c', 'html'):
            self.run_button = Gtk.Button(icon_name="execute-from-symbolic", css_classes=["flat", "circular"], tooltip_text=_("Run Script"))
            self.run_button.connect("clicked", lambda *_: self.run_script(self.language_name))
            title_box.append(self.run_button)
        self.append(title_box)
        self.append(Gtk.Separator())
        self.append(self.source_view)
        self.buffer.set_text(text)
        self.text_preedit = text

    def change_buttons_state(self, editing):
        if self.run_button:
            self.run_button.set_visible(not editing)
        self.edit_button.set_visible(not editing)
        self.cancel_edit_button.set_visible(editing)
        self.save_edit_button.set_visible(editing)
        self.source_view.set_editable(editing)

    def start_edit(self, button):
        self.change_buttons_state(True)
        self.text_preedit = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        window.set_focus(self.source_view)

    def cancel_edit(self, button):
        self.change_buttons_state(False)
        self.buffer.set_text(self.text_preedit)

    def save_edit(self, button):
        self.change_buttons_state(False)
        message_element = self.get_parent().get_parent()
        message_element.text = message_element.text.replace(self.text_preedit, self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False))
        window.sql_instance.insert_or_update_message(message_element)
        window.show_toast(_("Message edited successfully"), window.main_overlay)

    def on_copy(self):
        logger.debug("Copying code")
        clipboard = Gdk.Display().get_default().get_clipboard()
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, False)
        clipboard.set(text)
        window.show_toast(_("Code copied to the clipboard"), window.main_overlay)

    def extract_code(self, code_block_element):
        file_name = 'script'
        language = code_block_element.language_name
        file_names = {
            'script.cpp': ['cpp', 'c', 'c++'],
            'main.py': ['python3', 'py', 'py3', 'python'],
            'index.html': ['html'],
            'style.css': ['css'],
            'script.js': ['js', 'javascript'],
            'script.sh': ['bash', 'sh']
        }
        found_types = [key for key, value in file_names.items() if language.lower() in value]
        if len(found_types) > 0:
            file_name = found_types[0]
        return file_name, {'language': language, 'content': code_block_element.buffer.get_text(code_block_element.buffer.get_start_iter(), code_block_element.buffer.get_end_iter(), False)}

    def confirm_run_script(self):
        message_element = self.get_parent().get_parent()
        files = {}
        file_name, file_data = self.extract_code(self)
        files[file_name] = file_data
        if file_data['language'].lower() == 'html':
            for block in message_element.content_children:
                if isinstance(block, code_block) and block != self:
                    file_name2, file_data2 = self.extract_code(block)
                    if file_data2['language'].lower() in ('css', 'js', 'javascript'):
                        files[file_name2] = file_data2
        terminal_widget.run_terminal(files)

    def run_script(self, language_name):
        logger.debug("Running script")
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        dialog_widget.simple(
            _('Run Script'),
            _('Make sure you understand what this script does before running it, Alpaca is not responsible for any damages to your device or data'),
            lambda *_: self.confirm_run_script(),
            _('Execute'),
            'destructive'
        )

class attachment(Gtk.Button):
    __gtype_name__ = 'AlpacaAttachment'

    def __init__(self, file_name:str, file_type:str, file_content:str):
        self.file_type = file_type
        self.file_content = file_content
        button_content = Adw.ButtonContent(
            label=file_name,
            icon_name={
                "plain_text": "document-text-symbolic",
                "code": "code-symbolic",
                "pdf": "document-text-symbolic",
                "youtube": "play-symbolic",
                "website": "globe-symbolic",
                "thought": "brain-augemnted-symbolic"
            }[self.file_type]
        )
        super().__init__(
            vexpand=False,
            valign=3,
            name=file_name,
            css_classes=["flat"],
            tooltip_text=file_name,
            child=button_content
        )
        self.connect("clicked", lambda button, file_content=self.file_content, file_type=self.file_type: window.preview_file(self.get_name(), file_content, file_type, False))

class attachment_container(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaAttachmentContainer'

    def __init__(self):
        self.files = []

        self.container = Gtk.Box(
            orientation=0,
            spacing=10,
            valign=1
        )

        super().__init__(
            hexpand=True,
            child=self.container,
            vscrollbar_policy=2,
            propagate_natural_width=True
        )

    def add_file(self, file:attachment):
        self.container.append(file)
        self.files.append(file)

class image(Gtk.Button):
    __gtype_name__ = 'AlpacaImage'

    def __init__(self, file_name:str, file_content:str):
        self.file_type = 'image'
        self.file_content = file_content
        self.width = 0
        try:
            image_data = base64.b64decode(self.file_content)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            self.width = int((pixbuf.get_property('width') * 240) / pixbuf.get_property('height'))
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image = Gtk.Picture.new_for_paintable(texture)
            image.set_size_request(self.width, 240)
            super().__init__(
                child=image,
                css_classes=["flat", "chat_image_button"],
                name=file_name,
                tooltip_text=_("Image")
            )
            image.update_property([4], [_("Image")])
            self.connect("clicked", lambda button, content=self.file_content: window.preview_file(self.get_name(), content, 'image', False))
        except Exception as e:
            logger.error(e)
            image_texture = Gtk.Image.new_from_icon_name("image-missing-symbolic")
            image_texture.set_icon_size(2)
            image_texture.set_vexpand(True)
            image_texture.set_pixel_size(120)
            image_label = Gtk.Label(
                label=_("Missing Image"),
            )
            image_box = Gtk.Box(
                spacing=10,
                orientation=1,
            )
            image_box.append(image_texture)
            image_box.append(image_label)
            image_box.set_size_request(240, 240)
            super().__init__(
                child=image_box,
                css_classes=["flat", "chat_image_button"],
                tooltip_text=_("Missing Image")
            )
            image_texture.update_property([4], [_("Missing image")])
        self.set_overflow(1)

class image_container(Gtk.ScrolledWindow):
    __gtype_name__ = 'AlpacaImageContainer'

    def __init__(self):
        self.files = []

        self.container = Gtk.Box(
            orientation=0,
            spacing=12
        )

        super().__init__(
            height_request = 240,
            child=self.container,
            halign=2,
            propagate_natural_width=True
        )

    def add_image(self, img:image):
        self.container.append(img)
        self.files.append(img)
        self.set_max_content_width(sum([f.width for f in self.files] + [12*(len(self.files)-1)]))

class latex_image(Gtk.MenuButton):
    __gtype_name__ = 'AlpacaLatexImage'

    def __init__(self, equation:str):
        self.equation = equation
        copy_button = Gtk.Button(
            icon_name='edit-copy-symbolic',
            tooltip_text=_('Copy Equation'),
            css_classes=['flat']
        )
        copy_button.connect('clicked', lambda button: self.copy_equation())
        regenerate_button = Gtk.Button(
            icon_name='update-symbolic',
            tooltip_text=_('Regenerate Equation'),
            css_classes=['flat']
        )
        regenerate_button.connect('clicked', lambda button: self.generate_image(True))
        popover_container = Gtk.Box(spacing=10)
        popover_container.append(copy_button)
        popover_container.append(regenerate_button)
        self.popover = Gtk.Popover(child=popover_container)
        super().__init__(
            halign=3,
            popover=self.popover,
            height_request=75,
            css_classes=['flat'],
            child=Adw.Spinner()
        )
        threading.Thread(target=self.generate_image, args=(True,)).start()

    def copy_equation(self):
        self.popover.popdown()
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.equation)
        window.show_toast(_("Equation copied to the clipboard"), window.main_overlay)

    def generate_image(self, use_TeX:bool):
        self.popover.popdown()
        self.set_tooltip_text(_('LaTeX Equation'))
        if use_TeX:
            eq = self.equation
        else:
            eq = '${}$'.format(self.equation.replace('\\[', '').replace('\\]', '').replace('$', '').replace('\n', ''))
        try:
            picture = Gtk.Picture(
                css_classes=['latex_equation'],
                content_fit=1,
                vexpand=True
            )
            with tempfile.TemporaryDirectory() as temp_path:
                png_path = os.path.join(temp_path, 'equation.png')
                fig, ax = plt.subplots()
                ax.text(0.5, 0.5, eq, fontsize=24, ha='center', va='center', usetex=use_TeX)
                ax.axis('off')
                fig.patch.set_alpha(0.0)
                plt.savefig(png_path, format='png', bbox_inches="tight", pad_inches=0, transparent=True)
                plt.close(fig)

                img = Image.open(png_path).convert("RGBA")
                bbox = img.getbbox()
                if bbox:
                    cropped_image = img.crop(bbox)
                    width, height = cropped_image.size
                    cropped_image.save(png_path)

                picture.set_filename(png_path)
                picture.set_alternative_text(self.equation)
                self.set_child(picture)
        except Exception as e:
            if use_TeX:
                self.generate_image(False)
            else:
                logger.error(e)
                label = Gtk.Label(
                    label=eq,
                    wrap_mode=2,
                    wrap=True,
                    ellipsize=3,
                    css_classes=['error']
                )
                error = str(e)
                if 'ParseSyntaxException' in error:
                    self.set_tooltip_text(error.split('ParseSyntaxException: ')[-1])
                self.set_child(label)

class option_popup(Gtk.Popover):
    __gtype_name__ = 'AlpacaMessagePopup'

    def __init__(self, message_element):
        self.message_element = message_element
        container = Gtk.Box(
            spacing=5
        )
        super().__init__(
            has_arrow=True,
            child=container
        )

        self.delete_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="user-trash-symbolic",
            css_classes = ["flat"],
            tooltip_text = _("Remove Message")
        )
        self.delete_button.connect('clicked', lambda *_: self.delete_message())
        container.append(self.delete_button)

        self.copy_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="edit-copy-symbolic",
            css_classes=["flat"],
            tooltip_text=_("Copy Message")
        )
        self.copy_button.connect('clicked', lambda *_: self.copy_message())
        container.append(self.copy_button)

        self.edit_button = Gtk.Button(
            halign=1,
            hexpand=True,
            icon_name="edit-symbolic",
            css_classes=["flat"],
            tooltip_text=_("Edit Message")
        )
        self.edit_button.connect('clicked', lambda *_: self.edit_message())

        container.append(self.edit_button)
        if self.message_element.bot:
            self.regenerate_button = Gtk.Button(
                halign=1,
                hexpand=True,
                icon_name="update-symbolic",
                css_classes=["flat"],
                tooltip_text=_("Regenerate Message")
            )
            self.regenerate_button.connect('clicked', lambda *_: self.regenerate_message())
            container.append(self.regenerate_button)

    def delete_message(self):
        logger.debug("Deleting message")
        chat = self.message_element.get_chat()
        message_id = self.message_element.message_id
        window.sql_instance.delete_message(self.message_element)
        self.message_element.get_parent().remove(self.message_element)
        del chat.messages[message_id]
        if len(chat.messages) == 0:
            chat.set_visible_child_name('welcome-screen')

    def copy_message(self):
        logger.debug("Copying message")
        clipboard = Gdk.Display().get_default().get_clipboard()
        clipboard.set(self.message_element.text)
        window.show_toast(_("Message copied to the clipboard"), window.main_overlay)

    def edit_message(self):
        logger.debug("Editing message")
        self.popdown()
        self.message_element.set_hexpand(True)
        self.message_element.set_halign(0)
        edit_text_b = edit_text_block(self.message_element.text)
        for child in self.message_element.content_children:
            self.message_element.container.remove(child)
        self.message_element.content_children = []
        self.message_element.container.append(edit_text_b)
        window.set_focus(edit_text_b)

    def regenerate_message(self):
        chat = self.message_element.get_chat()
        if self.message_element.spinner:
            self.message_element.container.remove(self.message_element.spinner)
            self.message_element.spinner = None
        model = model_manager_widget.get_selected_model().get_name()
        if not chat.busy and model:
            self.message_element.set_text()
            self.message_element.model = model
            self.message_element.add_footer()
            self.message_element.update_profile_picture()
            self.message_element.footer.options_button.set_sensitive(False)
            threading.Thread(target=window.get_current_instance().generate_message, args=(self.message_element, model)).start()
        else:
            window.show_toast(_("Message cannot be regenerated while receiving a response"), window.main_overlay)

class footer(Gtk.Box):
    __gtype_name__ = 'AlpacaMessageFooter'

    def __init__(self, message_element):
        self.message_element = message_element
        super().__init__(
            orientation=0,
            hexpand=True,
            spacing=5,
            halign=0
        )
        self.options_button=None
        label = Gtk.Label(
            hexpand=True,
            wrap=True,
            ellipsize=3,
            wrap_mode=2,
            margin_end=5,
            margin_start=5 if message_element.profile_picture_data else 0,
            xalign=0,
            focusable=True,
            css_classes=[] if message_element.profile_picture_data else ['dim-label']
        )
        message_author = ""
        if self.message_element.model:
            model_name = window.convert_model_name(self.message_element.model, 0).replace(" (latest)", '').replace(' (custom)', '')
            if message_element.profile_picture_data:
                message_author = model_name
            else:
                message_author = "{} • ".format(model_name)
        if self.message_element.system:
            message_author = "{} • ".format(_("System"))
        if message_element.profile_picture_data:
            label.set_markup("<span weight='bold'>{}</span>\n<small>{}</small>".format(message_author, GLib.markup_escape_text(self.format_datetime())))
        else:
            label.set_markup("<small>{}{}</small>".format(message_author, GLib.markup_escape_text(self.format_datetime())))
        self.append(label)

    def format_datetime(self) -> str:
        dt = self.message_element.dt
        date = GLib.DateTime.new(GLib.DateTime.new_now_local().get_timezone(), dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        current_date = GLib.DateTime.new_now_local()
        if date.format("%Y/%m/%d") == current_date.format("%Y/%m/%d"):
            return date.format("%H:%M %p")
        if date.format("%Y") == current_date.format("%Y"):
            return date.format("%b %d, %H:%M %p")
        return date.format("%b %d %Y, %H:%M %p")

    def add_options_button(self):
        self.popup = option_popup(self.message_element)
        self.message_element.profile_picture = None

        if self.message_element.profile_picture_data:
            image_data = base64.b64decode(self.message_element.profile_picture_data)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            self.message_element.profile_picture = Gtk.Image.new_from_paintable(texture)
            self.message_element.profile_picture.set_size_request(40, 40)
            self.options_button = Gtk.MenuButton(
                width_request=40,
                height_request=40,
                css_classes=['circular'],
                valign=1,
                popover=self.popup,
                margin_top=5
            )
            self.options_button.set_overflow(1)
            self.options_button.set_child(self.message_element.profile_picture)
            list(self.options_button)[0].add_css_class('circular')
            list(self.options_button)[0].set_overflow(1)
            self.message_element.prepend(self.options_button)

        if not self.options_button:
            self.options_button = Gtk.MenuButton(
                icon_name='view-more-horizontal-symbolic',
                css_classes=['message_options_button', 'flat', 'circular', 'dim-label'],
                popover=self.popup
            )
            self.prepend(self.options_button)


class message(Gtk.Box):
    __gtype_name__ = 'AlpacaMessage'

    def __init__(self, message_id:str, dt:datetime.datetime, model:str=None, system:bool=False):
        self.message_id = message_id
        self.bot = model != None
        self.system = system
        self.dt = dt
        self.model = model
        self.content_children = [] #These are the code blocks, text blocks and tables
        self.footer = None
        self.image_c = None
        self.attachment_c = None
        self.spinner = None
        self.text = None
        self.profile_picture_data = None
        self.profile_picture = None
        if self.bot and self.model:
            found_models = [row.model for row in list(window.model_dropdown.get_model()) if row.model.get_name() == self.model]
            if found_models:
                self.profile_picture_data = found_models[0].data.get('profile_picture')

        self.container = Gtk.Box(
            orientation=1,
            halign='fill',
            css_classes=["response_message"] if self.bot or self.system else ["card", "user_message"],
            spacing=5,
            width_request=-1 if self.bot or self.system else 100
        )

        super().__init__(
            css_classes=["message"],
            name=message_id,
            halign=0 if self.bot or self.system else 2,
            spacing=2
        )

        self.append(self.container)
        self.add_footer()

    def update_profile_picture(self):
        if self.bot and self.model:
            found_models = [row.model for row in list(window.model_dropdown.get_model()) if row.model.get_name() == self.model]
            if found_models:
                new_profile_picture_data = found_models[0].data.get('profile_picture')
                if new_profile_picture_data != self.profile_picture_data:
                    self.profile_picture_data = new_profile_picture_data
                    self.add_footer()
            elif self.profile_picture_data:
                self.profile_picture_data = None
                self.add_footer()

    def get_chat(self):
        try:
            return self.get_parent().get_parent().get_parent().get_parent().get_parent()
        except Exception as e:
            pass

    def add_attachment(self, name:str, attachment_type:str, content:str):
        if attachment_type == 'image':
            if not self.image_c:
                self.image_c = image_container()
                self.container.append(self.image_c)
            new_image = image(name, content)
            self.image_c.add_image(new_image)
            return new_image
        else:
            if not self.attachment_c:
                self.attachment_c = attachment_container()
                self.container.append(self.attachment_c)
            new_attachment = attachment(name, attachment_type, content)
            self.attachment_c.add_file(new_attachment)
            return new_attachment

    def add_footer(self):
        if self.footer:
            if self.profile_picture:
                self.footer.options_button.get_parent().remove(self.footer.options_button)
            self.container.remove(self.footer)
        self.footer = footer(self)
        self.container.prepend(self.footer)
        self.footer.add_options_button()

    def update_message(self, data:dict):
        def write(content:str):
            self.content_children[-1].buffer.insert(self.content_children[-1].buffer.get_end_iter(), content, len(content.encode('utf-8')))
        chat = self.get_chat()
        if chat.busy:
            vadjustment = chat.scrolledwindow.get_vadjustment()
            if self.spinner:
                self.container.remove(self.spinner)
                self.spinner = None
                self.content_children[-1].set_visible(True)
                GLib.idle_add(vadjustment.set_value, vadjustment.get_upper())
            elif vadjustment.get_value() + 50 >= vadjustment.get_upper() - vadjustment.get_page_size():
                GLib.idle_add(vadjustment.set_value, vadjustment.get_upper() - vadjustment.get_page_size())
            GLib.idle_add(write, data.get('content', ''))

        if not chat.busy or data.get('done', False):
            self.footer.options_button.set_sensitive(True)
            tab = window.chat_list_box.get_tab_by_name(chat.get_name())
            if not chat.quick_chat and tab:
                tab.spinner.set_visible(False)
                if window.chat_list_box.get_current_chat().get_name() != chat.get_name():
                    window.chat_list_box.get_tab_by_name(chat.get_name()).indicator.set_visible(True)
                if chat.welcome_screen:
                    chat.container.remove(chat.welcome_screen)
                    chat.welcome_screen = None
            chat.stop_message()
            self.text = self.content_children[-1].get_text()
            GLib.idle_add(self.set_text, self.content_children[-1].get_text())
            self.dt = datetime.datetime.now()
            window.show_notification(chat.get_name(), self.text[:200] + (self.text[200:] and '...'), Gio.ThemedIcon.new("chat-message-new-symbolic"))
            if chat.quick_chat:
                GLib.idle_add(window.quick_ask_save_button.set_sensitive, True)
            else:
                window.sql_instance.insert_or_update_message(self)
            sys.exit()

    def set_text(self, text:str=None):
        self.text = text
        for child in self.content_children:
            self.container.remove(child)
        self.content_children = []
        if text:
            parts = []
            pos = 0
            for pattern_name, pattern in patterns:
                for match in pattern.finditer(self.text[pos:]):
                    match_start, match_end = match.span()

                    if pos < (match_start):
                        normal_text = self.text[pos:(match_start)]
                        parts.append({"type": "normal", "text": normal_text.strip()})

                    if pattern_name == "code":
                        parts.append(
                            {
                                "type": pattern_name,
                                "text": match.group(2),
                                "language": match.group(1),
                            }
                        )
                    elif pattern_name == "table":
                        parts.append({"type": pattern_name, "text": text[match_start:match_end]})
                    else:
                        parts.append({"type": pattern_name, "text": match.group(1)})

                    pos = match_end

            # Text blocks
            if pos < len(self.text):
                normal_text = self.text[pos:]
                if normal_text.strip():
                    parts.append({"type": "normal", "text": normal_text.strip()})

            self.text = re.sub(patterns[0][1], '', self.text)

            for part in parts:
                if part['type'] == 'normal':
                    text_b = text_block(self.bot, self.system)
                    part['text'] = GLib.markup_escape_text(part['text'])
                    part['text'] = part['text'].replace("\n* ", "\n• ")
                    part['text'] = re.sub(r'`([^`\n]*?)`', r'<tt>\1</tt>', part['text'])
                    part['text'] = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'^#\s+(.*)', r'<span size="xx-large">\1</span>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'^##\s+(.*)', r'<span size="x-large">\1</span>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'^###\s+(.*)', r'<span size="large">\1</span>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'_(\((.*?)\)|\d+)', r'<sub>\2\1</sub>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'\^(\((.*?)\)|\d+)', r'<sup>\2\1</sup>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\1">\2</a>', part['text'], flags=re.MULTILINE)
                    part['text'] = re.sub(r'\s\[(.*?)\]\s', r' <a href="\1">\1</a> ', part['text'], flags=re.MULTILINE)
                    pos = 0

                    for match in markup_pattern.finditer(part['text']):
                        start, end = match.span()
                        if pos < start:
                            text_b.raw_text += part['text'][pos:start]
                        text_b.raw_text += match.group(0)
                        pos = end

                    if pos < len(part['text']):
                        text_b.raw_text += part['text'][pos:]
                    if text_b.raw_text:
                        self.content_children.append(text_b)
                        self.container.append(text_b)
                        GLib.idle_add(text_b.set_markup,text_b.raw_text)
                elif part['type'] == 'code':
                    code_b = code_block(part['text'], part['language'])
                    self.content_children.append(code_b)
                    self.container.append(code_b)
                elif part['type'] == 'table':
                    table_w = TableWidget(part['text'])
                    self.content_children.append(table_w)
                    self.container.append(table_w)
                elif part['type'] == 'latex':
                    latex_w = latex_image(part['text'])
                    self.content_children.append(latex_w)
                    self.container.append(latex_w)
                elif part['type'] == 'think':
                    attachment = self.add_attachment(_('Thought'), 'thought', part['text'])
                    attachment.remove_css_class('flat')
        else:
            text_b = generating_text_block()
            text_b.set_visible(False)
            self.content_children.append(text_b)
            if self.spinner:
                self.container.remove(self.spinner)
                self.spinner = None
            self.spinner = Adw.Spinner(margin_top=10, margin_bottom=10, halign=3, hexpand=True)
            self.container.append(self.spinner)
            self.container.append(text_b)
        self.container.queue_draw()



