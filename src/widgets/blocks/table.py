#table.py
"""
Handles the table widget shown in messages
"""

import gi
from gi.repository import Gtk, Adw, GObject, Gio
from .text import markdown_to_pango

import re
import pandas as pd
from .. import dialog

class MarkdownTable:
    def __init__(self):
        self.headers = []
        self.rows = Gio.ListStore()
        self.alignments = []

    def __repr__(self):
        table_repr = 'Headers: {}\n'.format(self.headers)
        #table_repr += 'Alignments: {}\n'.format(self.alignments)
        table_repr += 'Rows:\n'
        for row in self.rows:
            table_repr += ' | '.join(row.raw_values) + '\n'
        return table_repr.replace('*', '')

class Row(GObject.GObject):
    def __init__(self, _values:list):
        super().__init__()

        self.values = []
        self.raw_values = []

        for value in _values:
            self.values.append(markdown_to_pango(value))
            self.raw_values.append(value)

    def get_column_value(self, index):
        return self.values[index]

class Table(Gtk.Box):
    __gtype_name__ = 'AlpacaTable'

    def __init__(self, content:str=None):
        super().__init__(
            orientation=1,
            spacing=10
        )
        self.set_margin_start(5)
        self.set_margin_end(5)
        self.table = MarkdownTable()
        self.markdown = ""

        self.set_halign(Gtk.Align.START)

        self.table_widget = Gtk.ColumnView(
            show_column_separators=True,
            show_row_separators=True,
            reorderable=False,
            css_classes=['r10', 'view', 'column-separators']
        )
        self.scrolled_window = Gtk.ScrolledWindow(
            vscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_natural_width=True
        )
        self.append(self.scrolled_window)
        download_button = Gtk.Button(
            icon_name='folder-download-symbolic',
            tooltip_text=_('Download Table'),
            css_classes=['circular'],
            halign=1
        )
        download_button.connect('clicked', lambda btn: self.prompt_download())
        self.append(download_button)

        if content:
            self.set_content(content)

    def get_content_for_dictation(self) -> str:
        return str(self.table)

    def parse_markdown_table(self, markdown_text:str):
        # Define regex patterns for matching the table components
        header_pattern = r'^\|(.+?)\|$'
        separator_pattern = r'^\|(\s*[:-]+:?\s*\|)+$'
        row_pattern = r'^\|(.+?)\|$'

        # Split the text into lines
        lines = markdown_text.strip().split('\n')

        # Extract headers
        header_match = re.match(header_pattern, lines[0], re.MULTILINE)
        if header_match:
            headers = [header.strip() for header in header_match.group(1).replace("*", "").split('|') if header.strip()]
            self.table.headers = headers

        # Extract alignments
        separator_match = re.match(separator_pattern, lines[1], re.MULTILINE)
        if separator_match:
            alignments = []
            separator_columns = lines[1].replace(" ", "").split('|')[1:-1]
            for sep in separator_columns:
                if ':' in sep:
                    if sep.startswith('-') and sep.endswith(':'):
                        alignments.append(1)
                    elif sep.startswith(':') and sep.endswith('-'):
                        alignments.append(0)
                    else:
                        alignments.append(0.5)
                else:
                    alignments.append(0)  # Default alignment is start
            self.table.alignments = alignments

        # Extract rows
        for line in lines[2:]:
            row_match = re.match(row_pattern, line, re.MULTILINE)
            if row_match:
                rows = line.split('|')[1:-1]
                row = Row(rows)
                self.table.rows.append(row)

    def make_table(self):

        def _on_factory_setup(_factory, list_item, align):
            label = Gtk.Label(xalign=align, selectable=True, use_markup=True)
            list_item.set_child(label)

        def _on_factory_bind(_factory, list_item, index):
            label_widget = list_item.get_child()
            row = list_item.get_item()
            label_widget.set_label(row.get_column_value(index))

        for index, column_name in enumerate(self.table.headers):
            column = Gtk.ColumnViewColumn(title=column_name, expand=True)
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", _on_factory_setup, self.table.alignments[index])
            factory.connect("bind", _on_factory_bind, index)
            column.set_factory(factory)
            self.table_widget.append_column(column)

        selection = Gtk.NoSelection.new(model=self.table.rows)
        self.table_widget.set_model(model=selection)

    def get_content(self) -> str:
        return self.markdown

    def set_content(self, value:str) -> None:
        self.markdown = value
        try:
            self.parse_markdown_table(self.markdown)
            self.make_table()
            self.scrolled_window.set_child(self.table_widget)
        except:
            label = Gtk.Label(
                label=self.markdown.lstrip('\n').rstrip('\n'),
                selectable=True,
                margin_top=6,
                margin_bottom=6,
                margin_start=6,
                margin_end=6
            )
            self.scrolled_window.set_child(label)

    def download(self, file_dialog, result):
        file = file_dialog.save_finish(result)
        if file:
            headers = [column.strip() for column in self.table.headers]
            rows = []
            for row in self.table.rows:
                rows.append([])
                for value in row.values:
                    rows[-1].append(value.strip())

            df = pd.DataFrame(rows, columns=headers)
            df.to_excel(file.get_path(), index=False)
            dialog.show_toast(
                message=_('Table saved successfully'),
                root_widget=self.get_root()
            )

    def prompt_download(self):
        file_dialog = Gtk.FileDialog(initial_name="{}.xlsx".format('spreadsheet'))
        file_dialog.save(
            parent=self.get_root(),
            cancellable=None,
            callback=self.download
        )
