# bookmarks.py
"""
Bookmarks widget for viewing and managing bookmarked messages
"""

import gi
from gi.repository import Gtk, Adw, GLib
import logging
import threading
from datetime import datetime
from typing import Optional

from ..sql_manager import Instance as SQL, format_datetime

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path='/com/jeffser/Alpaca/widgets/bookmarks/bookmarks.ui')
class Bookmarks(Adw.Dialog):
    __gtype_name__ = 'AlpacaBookmarks'

    bookmarks_stack = Gtk.Template.Child()
    bookmarks_listbox = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_bookmarks = []
        
        # Load bookmarks when dialog opens
        GLib.idle_add(self._load_bookmarks)

    @Gtk.Template.Callback()
    def on_close(self, button=None):
        """Close the dialog"""
        self.close()

    def _load_bookmarks(self) -> bool:
        """Load bookmarks in a background thread"""
        # Show loading state
        self.bookmarks_stack.set_visible_child_name('loading')
        
        # Run loading in background thread
        threading.Thread(
            target=self._load_bookmarks_thread,
            daemon=True
        ).start()
        
        return False

    def _load_bookmarks_thread(self):
        """Background thread for loading bookmarks"""
        try:
            # Get all bookmarks from database
            bookmarks = SQL.get_bookmarks()
            
            # Update UI on main thread
            GLib.idle_add(self._display_bookmarks, bookmarks)
            
        except Exception as e:
            logger.error(f"Error loading bookmarks: {e}")
            GLib.idle_add(self.bookmarks_stack.set_visible_child_name, 'error')

    def _display_bookmarks(self, bookmarks: list) -> bool:
        """Display bookmarks in the UI"""
        # Clear existing bookmarks
        self.bookmarks_listbox.remove_all()
        self._current_bookmarks = bookmarks
        
        if not bookmarks:
            self.bookmarks_stack.set_visible_child_name('empty')
            return False
        
        # Add bookmark rows
        for bookmark in bookmarks:
            row = self._create_bookmark_row(bookmark)
            self.bookmarks_listbox.append(row)
        
        self.bookmarks_stack.set_visible_child_name('bookmarks')
        return False

    def _create_bookmark_row(self, bookmark: tuple) -> Gtk.ListBoxRow:
        """Create a list box row for a bookmark
        
        bookmark tuple format:
        (bookmark_id, message_id, bookmark_created_at, message_content, 
         message_date_time, message_role, message_model, chat_id, chat_name)
        """
        row = Gtk.ListBoxRow()
        row.bookmark_data = {
            'bookmark_id': bookmark[0],
            'message_id': bookmark[1],
            'bookmark_created_at': bookmark[2],
            'message_content': bookmark[3],
            'message_date_time': bookmark[4],
            'message_role': bookmark[5],
            'message_model': bookmark[6],
            'chat_id': bookmark[7],
            'chat_name': bookmark[8]
        }
        
        # Main container
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12
        )
        
        # Content box (left side)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            hexpand=True
        )
        
        # Header with chat name and message timestamp
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12
        )
        
        # Chat name
        chat_label = Gtk.Label(
            label=row.bookmark_data['chat_name'],
            xalign=0,
            hexpand=True,
            ellipsize=3,  # ELLIPSIZE_END
            max_width_chars=40
        )
        chat_label.add_css_class('heading')
        header_box.append(chat_label)
        
        # Message timestamp
        try:
            msg_datetime = datetime.strptime(
                row.bookmark_data['message_date_time'] + (":00" if row.bookmark_data['message_date_time'].count(":") == 1 else ""),
                '%Y/%m/%d %H:%M:%S'
            )
            time_str = format_datetime(msg_datetime)
        except Exception as e:
            logger.warning(f"Error parsing datetime: {e}")
            time_str = row.bookmark_data['message_date_time']
        
        time_label = Gtk.Label(
            label=time_str,
            xalign=1
        )
        time_label.add_css_class('dim-label')
        time_label.add_css_class('caption')
        header_box.append(time_label)
        
        box.append(header_box)
        
        # Role indicator (User/Assistant/System)
        role_label = Gtk.Label(
            label=row.bookmark_data['message_role'].capitalize(),
            xalign=0
        )
        role_label.add_css_class('caption')
        role_label.add_css_class('dim-label')
        box.append(role_label)
        
        # Message content preview
        content = row.bookmark_data['message_content']
        preview_label = Gtk.Label(
            label=content,
            xalign=0,
            wrap=True,
            wrap_mode=2,  # WRAP_WORD
            max_width_chars=60,
            lines=4,
            ellipsize=3  # ELLIPSIZE_END
        )
        preview_label.add_css_class('body')
        box.append(preview_label)
        
        main_box.append(box)
        
        # Remove button (right side)
        remove_button = Gtk.Button(
            icon_name='user-trash-symbolic',
            valign=Gtk.Align.CENTER,
            tooltip_text=_('Remove bookmark')
        )
        remove_button.add_css_class('flat')
        remove_button.add_css_class('circular')
        remove_button.connect('clicked', self._on_remove_bookmark, row)
        main_box.append(remove_button)
        
        row.set_child(main_box)
        return row

    @Gtk.Template.Callback()
    def on_bookmark_activated(self, listbox, row):
        """Handle clicking on a bookmark"""
        if not hasattr(row, 'bookmark_data'):
            return
        
        bookmark_data = row.bookmark_data
        
        try:
            # Get the main window
            window = self.get_root()
            
            # Navigate to the chat containing the message
            self._navigate_to_message(window, bookmark_data)
            
            # Close the bookmarks dialog
            self.close()
            
        except Exception as e:
            logger.error(f"Error navigating to bookmarked message: {e}")

    def _navigate_to_message(self, window, bookmark_data: dict):
        """Navigate to the chat and message"""
        # Find the chat in the chat list
        chat_list_page = window.get_chat_list_page()
        
        # Search through all chat rows to find the matching chat
        target_chat_row = None
        for row in list(chat_list_page.chat_list_box):
            if hasattr(row, 'chat') and row.chat.chat_id == bookmark_data['chat_id']:
                target_chat_row = row
                break
        
        if target_chat_row:
            # Select the chat row to load it
            chat_list_page.chat_list_box.select_row(target_chat_row)
            
            # Wait a moment for the chat to load, then scroll to the message
            GLib.timeout_add(100, self._scroll_to_message, window, bookmark_data['message_id'])
        else:
            logger.warning(f"Could not find chat with ID: {bookmark_data['chat_id']}")

    def _scroll_to_message(self, window, message_id: str) -> bool:
        """Scroll to and highlight the specific message"""
        try:
            current_chat = window.chat_bin.get_child()
            if not current_chat:
                return False
            
            # Find the message widget
            for message in list(current_chat.container):
                if hasattr(message, 'message_id') and message.message_id == message_id:
                    # Scroll to the message
                    message.grab_focus()
                    
                    # Optionally add a temporary highlight effect
                    # This could be done with CSS classes if desired
                    
                    break
            
        except Exception as e:
            logger.error(f"Error scrolling to message: {e}")
        
        return False  # Don't repeat timeout

    def _on_remove_bookmark(self, button, row):
        """Handle removing a bookmark"""
        if not hasattr(row, 'bookmark_data'):
            return
        
        message_id = row.bookmark_data['message_id']
        
        # Remove from database
        success = SQL.remove_bookmark(message_id)
        
        if success:
            # Remove the row from the UI
            self.bookmarks_listbox.remove(row)
            
            # Update the current bookmarks list
            self._current_bookmarks = [
                b for b in self._current_bookmarks 
                if b[1] != message_id  # b[1] is message_id
            ]
            
            # If no bookmarks left, show empty state
            if not self._current_bookmarks:
                self.bookmarks_stack.set_visible_child_name('empty')
            
            # Update the message's bookmark state if it's currently visible
            self._update_message_bookmark_state(message_id)
            
            logger.info(f"Bookmark removed for message: {message_id}")
        else:
            logger.error(f"Failed to remove bookmark for message: {message_id}")

    def _update_message_bookmark_state(self, message_id: str):
        """Update the bookmark state of a message if it's currently visible"""
        try:
            window = self.get_root()
            if not window:
                return
            
            # Get the current chat
            current_chat = window.chat_bin.get_child()
            if not current_chat:
                return
            
            # Find the message widget and update its bookmark state
            for message in list(current_chat.container):
                if hasattr(message, 'message_id') and message.message_id == message_id:
                    message.update_bookmark_state()
                    break
        except Exception as e:
            logger.warning(f"Could not update message bookmark state: {e}")

    @Gtk.Template.Callback()
    def on_refresh(self, button=None):
        """Refresh the bookmarks list"""
        self._load_bookmarks()
