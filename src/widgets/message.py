# message.py
"""
TODO DESCRIPTION
"""

import gi
import blocks
from gi.repository import GLib, Gtk, Adw

patterns = (
    ('think', re.compile(r'(?:<think>|<\|begin_of_thought\|>)\n+(.*?)\n+(?:<\/think>|<\|end_of_thought\|>)', re.DOTALL | re.IGNORECASE)),
    ('latex', re.compile(r'\\\[\n*?(.*?)\n*?\\\]|\$+\n*?(.*?)\$+\n*?', re.DOTALL)),
    ('code', re.compile(r'```([a-zA-Z0-9_+\-]*)\n(.*?)\n\s*```', re.DOTALL)),
    ('code', re.compile(r'`(\w*)\n(.*?)\n\s*`', re.DOTALL)),
    ('table', re.compile(r'((?:\| *[^|\r\n]+ *)+\|)(?:\r?\n)((?:\|[ :]?-+[ :]?)+\|)((?:(?:\r?\n)(?:\| *[^|\r\n]+ *)+\|)+)', re.MULTILINE))
)

class BlockContainer(Gtk.Box):
    __gtype_name__ = 'AlpacaBlockContainer'

    def __init__(self, message:Message):
        self.message = message
        super().__init__(
            orientation=1,
            halign=0,
            spacing=5
        )
        self.generating_block = None

    def get_generating_block(self) -> blocks.Text:
        """
        Gets the generating text block, creates it if it does not exist
        """
        if not self.generating_block:
            self.generating_block = blocks.Text(generating=True)
            self.append(self.generating_block)
        return self.generating_block

    def set_content(self, content:str) -> None:
        if self.generating_block:
            self.remove(self.generating_block)
            self.generating_block = None
         for pattern_name, pattern in patterns:
            for match in pattern.finditer(content[pos:]):
                match_start, match_end = match.span()
                if pos < (match_start):
                    if isinstance(list(self)[-1], blocks.Text):
                        list(self)[-1].append_content(content[pos:(match_start)])
                    else:
                        self.append(blocks.Text(content=content[pos:(match_start)]))
                if pattern_name == "think":
                    print("think")
                elif pattern_name == "code":
                    if match.group(1).lower() == 'latex':
                        self.append(blocks.Latex(content=match.group(2)))
                    else:
                        self.append(blocks.Code(content=match.group(2), language=match.group(1)))
                elif pattern_name == "table":
                    self.append(blocks.Table(content=content[match_start:match_end]))
                elif pattern_name == "latex":
                    expression = match.group(1)
                    if not expression:
                        expression = match.group(2)
                    if '\\' in expression:
                        self.append(blocks.Latex(content=expression))
                    else:
                        if isinstance(list(self)[-1], blocks.Text):
                            list(self)[-1].append_content(expression)
                        else:
                            self.append(blocks.Text(content=expression))
                else:
                    if isinstance(list(self)[-1], blocks.Text):
                        list(self)[-1].append_content('\n\n{}'.format(expression))
                    else:
                        self.append(blocks.Text(content=expression))
                pos = match_end

    def get_content(self) -> str:
        content = [block.get_content() for block in list(self) if not isinstance(block, None) and not isinstance(block, None)] # TODO if block is not image or attachment container
        return '\n\n'.join(content)

class MessageHeader(Gtk.Box):
    __gtype_name__ = 'AlpacaMessageHeader'

    def __init__(self, message:Message, dt:datetime.datetime, popover=None):
        self.message = message
        super().__init__(
            orientation=0,
            hexpand=True,
            spacing=5,
            halign=0
        )
        if popover:
            options_button = Gtk.MenuButton(
                icon_name='view-more-horizontal-symbolic',
                css_classes=['message_options_button', 'flat', 'circular', 'dim-label'],
                popover=popover
            )
            self.append(options_button)

        label = Gtk.Label(
            hexpand=True,
            wrap=True,
            wrap_mode=2,
            margin_end=5,
            margin_start=0 if popover else 5,
            xalign=0,
            focusable=True,
            css_classes=['dim-label'] if popover else []
        )

        author = self.message.author

        if ':' in author:
            author = author.split(':')
            if author[1].lower() not in ('latest', 'custom'):
                author = '{} ({})'.format(author[0], author[1])
            else:
                author = author[0]
        author = author.title()

        if popover:
            label.set_markup(
                "<span weight='bold'>{}</span>\n<small>{}</small>".format(
                    author,
                    GLib.markup_escape_text(self.format_datetime(dt))
                )
            )
        else:
            label.set_markup(
                "<small>{}{}</small>".format(
                    ('{} • ' if self.message.author else '{}').format(author),
                    GLib.markup_escape_text(self.format_datetime(dt))
                )
            )
        self.append(label)

    def format_datetime(self, dt) -> str:
        date = GLib.DateTime.new(
            GLib.DateTime.new_now_local().get_timezone(),
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second
        )
        current_date = GLib.DateTime.new_now_local()
        if date.format("%Y/%m/%d") == current_date.format("%Y/%m/%d"):
            return date.format("%I:%M %p")
        if date.format("%Y") == current_date.format("%Y"):
            return date.format("%b %d, %I:%M %p")
        return date.format("%b %d %Y, %I:%M %p")

class Message(Gtk.Box):
    __gtype_name__ = 'AlpacaMessage'

    def __init__(self, message_id:str=-1, chat=None, mode:int=0, author:str=None):
        """
        Mode 0: User
        Mode 1: Assistant
        Mode 2: System
        Mode 3: Attachment
        """

        ##TODO PFP: prepend to self to add pfp
        self.chat = chat
        self.mode = mode
        self.author = author

        super().__init__(
            css_classes=["message"],
            name=message_id,
            halign=2 if mode==0 else 0,
            spacing=2
        )
        self.pfp_container = Adw.Bin()
        self.append(pfp_container)

        main_container = Gtk.Box(
            orientation=1,
            halign=0,
            css_classes=["card", "user_message"] if mode==0 else ["response_message"],
            spacing=5,
            width_request=100 if mode==0 else -1
        )
        self.append(main_container)

        self.header_container = Adw.Bin(
            hexpand=True
        )
        main_container.append(self.header_container)
        self.block_container = BlockContainer(
            message=self
        )
        main_container.append(self.block_container)

    def get_model(self) -> str or None:
        """
        Get the model name if the author is a model
        """
        if self.mode == 1:
            return self.author

    def update_message(self, data:dict) -> None:
        """
        Data API:
        {'done': True}              = Renders the content using blocks
        {'content': 'TEXT'}         = Text to append
        {'clear': True}             = Clears the generating block
        {'add_css', 'css_class'}    = Adds CSS class to generating block
        {'remove_css': 'css_class'} = Removes CSS class from generating block
        """

        if data.get('done'):
            print('Generation finished')
        elif data.get('content'):
            GLib.idle_add(self.block_container.get_generating_block().append_content, data.get('content'))
        elif data.get('clear'):
            GLib.idle_add(self.block_container.get_generating_block().set_content, None)
        elif data.get('add_css'):
            self.block_container.get_generating_block().add_css_class(data.get('add_css'))
        elif data.get('remove_css'):
            self.block_container.get_generating_block().remove_css_class(data.get('remove_css'))
