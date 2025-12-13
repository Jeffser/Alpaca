"""
Search service for Alpaca application.
Provides global search functionality across all chats and messages.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import sqlite3
import os


def _get_data_dir():
    """Get the data directory for Alpaca database."""
    try:
        from ..constants import data_dir
        return data_dir
    except ImportError:
        try:
            from constants import data_dir
            return data_dir
        except (ImportError, NameError):
            # Fallback for testing - use XDG_DATA_HOME or default
            base = os.getenv("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
            return os.path.join(base, "com.jeffser.Alpaca")


@dataclass
class SearchResult:
    """
    Represents a single search result from the global search.
    
    Attributes:
        chat_id: Unique identifier of the chat containing the message
        chat_name: Display name of the chat
        message_id: Unique identifier of the matching message
        message_preview: Preview text of the message content
        timestamp: When the message was created
        relevance_score: Score indicating relevance of the match (0.0 to 1.0)
    """
    chat_id: str
    chat_name: str
    message_id: str
    message_preview: str
    timestamp: datetime
    relevance_score: float


class SearchService:
    """
    Service for searching across all chats and messages in the Alpaca database.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the search service with database connection.
        
        Args:
            db_path: Optional custom database path (mainly for testing)
        """
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = os.path.join(_get_data_dir(), "alpaca.db")
    
    def search_all_chats(
        self, 
        query: str, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        context_chars: int = 100
    ) -> List[SearchResult]:
        """
        Search across all chats with optional date filtering.
        
        Args:
            query: The search query string to match against message content
            date_from: Optional start date for filtering results
            date_to: Optional end date for filtering results
            context_chars: Number of characters to include in preview (default: 100)
        
        Returns:
            List of SearchResult objects ordered by relevance and recency
        """
        if not query or not query.strip():
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build the SQL query with optional date filtering
            sql_query = """
                SELECT 
                    m.id as message_id,
                    m.content,
                    m.date_time,
                    c.id as chat_id,
                    c.name as chat_name
                FROM message m
                JOIN chat c ON m.chat_id = c.id
                WHERE m.content LIKE ?
            """
            
            params = [f"%{query}%"]
            
            # Add date filtering if provided
            if date_from is not None:
                sql_query += " AND m.date_time >= ?"
                params.append(date_from.strftime("%Y/%m/%d %H:%M:%S"))
            
            if date_to is not None:
                sql_query += " AND m.date_time <= ?"
                params.append(date_to.strftime("%Y/%m/%d %H:%M:%S"))
            
            # Order by date (most recent first)
            sql_query += " ORDER BY m.date_time DESC"
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            for row in rows:
                message_id, content, date_time_str, chat_id, chat_name = row
                
                # Parse the datetime
                try:
                    timestamp = datetime.strptime(date_time_str, "%Y/%m/%d %H:%M:%S")
                except ValueError:
                    # Fallback if datetime format is different
                    timestamp = datetime.now()
                
                # Generate preview with context around the match
                preview = self.get_search_result_preview(
                    message_content=content, query=query, context_chars=context_chars
                )
                
                # Calculate relevance score (simple implementation)
                relevance_score = self._calculate_relevance(content, query)
                
                results.append(SearchResult(
                    chat_id=chat_id,
                    chat_name=chat_name,
                    message_id=message_id,
                    message_preview=preview,
                    timestamp=timestamp,
                    relevance_score=relevance_score
                ))
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error during search: {e}")
            return []
        
        # Sort by relevance score (descending) then by timestamp (descending)
        results.sort(key=lambda x: (x.relevance_score, x.timestamp), reverse=True)
        
        return results
    
    def get_search_result_preview(
        self, 
        message_id: str = None,
        message_content: str = None,
        query: str = None,
        context_chars: int = 100
    ) -> str:
        """
        Get preview text for a search result with context around the match.
        
        Can be called in two ways:
        1. With message_id to fetch content from database
        2. With message_content directly for efficiency during search
        
        Args:
            message_id: Optional message ID to fetch content from database
            message_content: Optional full message content (used if message_id not provided)
            query: Optional search query to highlight context around
            context_chars: Number of characters to show around the match
        
        Returns:
            Preview string with ellipsis if truncated
        """
        # If message_id provided, fetch content from database
        if message_id is not None:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT content FROM message WHERE id=?", (message_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    message_content = row[0]
                else:
                    return ""
            except sqlite3.Error as e:
                print(f"Database error fetching message preview: {e}")
                return ""
        
        if not message_content:
            return ""
        
        # If no query provided, return truncated content from start
        if not query:
            if len(message_content) <= context_chars * 2:
                return message_content
            return message_content[:context_chars * 2] + "..."
        
        # Find the position of the query in the content (case-insensitive)
        query_lower = query.lower()
        content_lower = message_content.lower()
        match_pos = content_lower.find(query_lower)
        
        if match_pos == -1:
            # Query not found (shouldn't happen), return start of content
            if len(message_content) <= context_chars * 2:
                return message_content
            return message_content[:context_chars * 2] + "..."
        
        # Calculate start and end positions for preview
        half_context = context_chars // 2
        start_pos = max(0, match_pos - half_context)
        end_pos = min(len(message_content), match_pos + len(query) + half_context)
        
        # Extract preview
        preview = message_content[start_pos:end_pos]
        
        # Add ellipsis if truncated
        if start_pos > 0:
            preview = "..." + preview
        if end_pos < len(message_content):
            preview = preview + "..."
        
        # Clean up whitespace
        preview = " ".join(preview.split())
        
        return preview
    
    def _calculate_relevance(self, content: str, query: str) -> float:
        """
        Calculate a relevance score for a search result.
        
        Args:
            content: The message content
            query: The search query
        
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not content or not query:
            return 0.0
        
        content_lower = content.lower()
        query_lower = query.lower()
        
        # Count occurrences of the query
        occurrences = content_lower.count(query_lower)
        
        # Check if query appears as a whole word
        words = content_lower.split()
        whole_word_matches = sum(1 for word in words if query_lower in word)
        
        # Calculate score based on:
        # - Number of occurrences (more is better)
        # - Position of first occurrence (earlier is better)
        # - Whole word matches (better than partial)
        
        first_occurrence = content_lower.find(query_lower)
        position_score = 1.0 - (first_occurrence / max(len(content), 1))
        
        occurrence_score = min(occurrences / 10.0, 1.0)  # Cap at 10 occurrences
        word_match_score = min(whole_word_matches / 5.0, 1.0)  # Cap at 5 word matches
        
        # Weighted average
        relevance = (
            position_score * 0.3 +
            occurrence_score * 0.4 +
            word_match_score * 0.3
        )
        
        return min(relevance, 1.0)
