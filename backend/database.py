"""
SQLite database module for Simple Photo Meta.
Simple raw SQL queries - no ORM.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from config import DATABASE_PATH


# Thread-local storage for connections
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_local, 'connection') or _local.connection is None:
        _local.connection = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
        _local.connection.row_factory = sqlite3.Row
    return _local.connection


@contextmanager
def get_cursor():
    """Context manager for database cursor."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def init_database():
    """Initialize the database schema."""
    with get_cursor() as cursor:
        # Tags table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT NOT NULL,
                tag_type TEXT NOT NULL,
                UNIQUE(tag, tag_type)
            )
        """)
        
        # Images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE
            )
        """)
        
        # Image-Tag associations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE(image_id, tag_id)
            )
        """)
        
        # Scanned directories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scanned_directories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                last_scan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_path ON images(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_type ON tags(tag_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")


# ============== Tag operations ==============

def get_or_create_tag(tag: str, tag_type: str) -> int:
    """Get or create a tag, return its ID."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM tags WHERE tag = ? AND tag_type = ?",
            (tag, tag_type)
        )
        row = cursor.fetchone()
        if row:
            return row['id']
        
        cursor.execute(
            "INSERT INTO tags (tag, tag_type) VALUES (?, ?)",
            (tag, tag_type)
        )
        return cursor.lastrowid


def get_tags_by_type(tag_type: Optional[str] = None) -> list[str]:
    """Get all unique tags, optionally filtered by type."""
    with get_cursor() as cursor:
        if tag_type:
            cursor.execute(
                "SELECT DISTINCT tag FROM tags WHERE tag_type = ? ORDER BY tag",
                (tag_type,)
            )
        else:
            cursor.execute("SELECT DISTINCT tag FROM tags ORDER BY tag")
        return [row['tag'] for row in cursor.fetchall()]


def search_tags(query: str, tag_type: Optional[str] = None, limit: int = 20) -> list[str]:
    """Search tags by prefix."""
    with get_cursor() as cursor:
        if tag_type:
            cursor.execute(
                """SELECT DISTINCT tag FROM tags 
                   WHERE tag LIKE ? AND tag_type = ? 
                   ORDER BY tag LIMIT ?""",
                (f"%{query}%", tag_type, limit)
            )
        else:
            cursor.execute(
                "SELECT DISTINCT tag FROM tags WHERE tag LIKE ? ORDER BY tag LIMIT ?",
                (f"%{query}%", limit)
            )
        return [row['tag'] for row in cursor.fetchall()]


# ============== Image operations ==============

def get_or_create_image(path: str) -> int:
    """Get or create an image record, return its ID."""
    with get_cursor() as cursor:
        cursor.execute("SELECT id FROM images WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            return row['id']
        
        cursor.execute("INSERT INTO images (path) VALUES (?)", (path,))
        return cursor.lastrowid


def get_image_overlay_info(path: str) -> dict:
    """Get overlay info (DateTimeOriginal, GPS, Keywords) for an image from tags."""
    result = {
        "date_time_original": None,
        "gps_latitude": None,
        "gps_longitude": None,
        "keywords": [],
    }
    
    with get_cursor() as cursor:
        # Get image ID
        cursor.execute("SELECT id FROM images WHERE path = ?", (path,))
        row = cursor.fetchone()
        if not row:
            return result
        
        image_id = row['id']
        
        # Get the relevant tags for this image
        cursor.execute("""
            SELECT t.tag, t.tag_type FROM tags t
            JOIN image_tags it ON t.id = it.tag_id
            WHERE it.image_id = ? AND t.tag_type IN ('DateTimeOriginal', 'GPSLatitude', 'GPSLongitude', 'Keywords')
        """, (image_id,))
        
        for row in cursor.fetchall():
            tag_type = row['tag_type']
            tag_value = row['tag']
            
            if tag_type == 'DateTimeOriginal':
                result['date_time_original'] = tag_value
            elif tag_type == 'GPSLatitude':
                result['gps_latitude'] = tag_value
            elif tag_type == 'GPSLongitude':
                result['gps_longitude'] = tag_value
            elif tag_type == 'Keywords':
                result['keywords'].append(tag_value)
    
    return result


def search_images(folder: str, search: str, tag_type: Optional[str], page: int, page_size: int) -> list[str]:
    """Search images by tag value. Supports multiple words - all words must match (in any tags)."""
    offset = page * page_size
    
    # Split search into words
    words = search.split()
    if not words:
        return []
    
    with get_cursor() as cursor:
        # Build query that requires ALL words to match (each word can be in different tags)
        # For each word, we check if the image has at least one tag containing that word
        base_query = """
            SELECT DISTINCT i.path FROM images i
            WHERE i.path LIKE ?
        """
        params = [f"{folder}%"]
        
        for word in words:
            if tag_type:
                base_query += """
                    AND EXISTS (
                        SELECT 1 FROM image_tags it
                        JOIN tags t ON it.tag_id = t.id
                        WHERE it.image_id = i.id AND t.tag LIKE ? AND t.tag_type = ?
                    )
                """
                params.extend([f"%{word}%", tag_type])
            else:
                base_query += """
                    AND EXISTS (
                        SELECT 1 FROM image_tags it
                        JOIN tags t ON it.tag_id = t.id
                        WHERE it.image_id = i.id AND t.tag LIKE ?
                    )
                """
                params.append(f"%{word}%")
        
        base_query += " ORDER BY i.path LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        cursor.execute(base_query, params)
        return [row['path'] for row in cursor.fetchall()]


def count_search_results(folder: str, search: str, tag_type: Optional[str]) -> int:
    """Count search results. Supports multiple words - all words must match."""
    # Split search into words
    words = search.split()
    if not words:
        return 0
    
    with get_cursor() as cursor:
        base_query = """
            SELECT COUNT(DISTINCT i.id) as cnt FROM images i
            WHERE i.path LIKE ?
        """
        params = [f"{folder}%"]
        
        for word in words:
            if tag_type:
                base_query += """
                    AND EXISTS (
                        SELECT 1 FROM image_tags it
                        JOIN tags t ON it.tag_id = t.id
                        WHERE it.image_id = i.id AND t.tag LIKE ? AND t.tag_type = ?
                    )
                """
                params.extend([f"%{word}%", tag_type])
            else:
                base_query += """
                    AND EXISTS (
                        SELECT 1 FROM image_tags it
                        JOIN tags t ON it.tag_id = t.id
                        WHERE it.image_id = i.id AND t.tag LIKE ?
                    )
                """
                params.append(f"%{word}%")
        
        cursor.execute(base_query, params)
        return cursor.fetchone()['cnt']


def get_tagged_images(folder: str, tag_type: str) -> set[str]:
    """Get set of image paths that have tags of the specified type."""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT i.path FROM images i
            JOIN image_tags it ON i.id = it.image_id
            JOIN tags t ON it.tag_id = t.id
            WHERE i.path LIKE ? AND t.tag_type = ?
        """, (f"{folder}%", tag_type))
        return {row['path'] for row in cursor.fetchall()}


# ============== Image-Tag associations ==============

def clear_image_tags(image_id: int, tag_type: Optional[str] = None):
    """Clear tag associations for an image."""
    with get_cursor() as cursor:
        if tag_type:
            cursor.execute("""
                DELETE FROM image_tags WHERE image_id = ? AND tag_id IN (
                    SELECT id FROM tags WHERE tag_type = ?
                )
            """, (image_id, tag_type))
        else:
            cursor.execute("DELETE FROM image_tags WHERE image_id = ?", (image_id,))


def add_image_tag(image_id: int, tag_id: int):
    """Add a tag association to an image."""
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
            (image_id, tag_id)
        )


def update_image_tags(image_path: str, tag_type: str, values: list[str]):
    """Update tags of a specific type for an image."""
    image_id = get_or_create_image(image_path)
    clear_image_tags(image_id, tag_type)
    
    for value in values:
        if value and value.strip():
            tag_id = get_or_create_tag(value.strip(), tag_type)
            add_image_tag(image_id, tag_id)


def get_indexed_images(folder: str) -> set[str]:
    """Get all image paths that are already indexed for a folder."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT path FROM images WHERE path LIKE ?",
            (f"{folder}%",)
        )
        return {row['path'] for row in cursor.fetchall()}


# ============== Scanned directories ==============

def mark_directory_scanned(path: str):
    """Mark a directory as scanned."""
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT OR REPLACE INTO scanned_directories (path, last_scan)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (path,))


def is_directory_scanned(path: str) -> bool:
    """Check if a directory has been scanned."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM scanned_directories WHERE path = ?",
            (path,)
        )
        return cursor.fetchone() is not None


# ============== Preferences ==============

def get_preference(key: str) -> Optional[str]:
    """Get a preference value."""
    with get_cursor() as cursor:
        cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None


def set_preference(key: str, value: str):
    """Set a preference value."""
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            (key, value)
        )


def get_all_preferences() -> dict:
    """Get all preferences as a dict."""
    with get_cursor() as cursor:
        cursor.execute("SELECT key, value FROM preferences")
        return {row['key']: row['value'] for row in cursor.fetchall()}
