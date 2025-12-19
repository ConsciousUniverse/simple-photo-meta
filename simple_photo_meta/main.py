#!/usr/bin/env python3
import sys, os, sqlite3, subprocess, re, time, io
from appdirs import user_data_dir

# Register HEIF support for HEIC/HEIF images
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # HEIF support optional

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QListView,
    QAbstractItemView,
    QSplitter,
    QDialog,
    QComboBox,
    QSizePolicy,
    QCompleter,
    QScrollArea,
    QStyledItemDelegate,
    QFrame,
    QProgressBar,
    QProgressDialog,
    QMenuBar,
    QMenu,
)
from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QStandardItemModel,
    QStandardItem,
    QFont,
    QTextCursor,
    QTransform,
    QTextCharFormat,
    QColor,
    QTextBlockFormat,
    QFontMetrics,
    QPalette,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QGuiApplication,
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QTimer, QStringListModel
import hashlib
from PIL import Image, ImageOps
from datetime import datetime

from simple_photo_meta import iptc_tags, exif_tags
from simple_photo_meta.exiv2bind import Exiv2Bind


PREVIEW_CACHE_DIR_NAME = ".previews"
THUMBNAIL_DIR_NAME = ".thumbnails"
DEFAULT_PREVIEW_MAX_EDGE = 2048


def _preview_cache_path(image_path, edge_length):
    folder = os.path.dirname(image_path)
    cache_dir = os.path.join(folder, PREVIEW_CACHE_DIR_NAME)
    os.makedirs(cache_dir, exist_ok=True)
    hash_input = f"{os.path.abspath(image_path)}::{edge_length}"
    hash_str = hashlib.sha256(hash_input.encode()).hexdigest()
    return os.path.join(cache_dir, f"{hash_str}.jpg")


def _preview_is_current(image_path, preview_path):
    try:
        return os.path.getmtime(preview_path) >= os.path.getmtime(image_path)
    except OSError:
        return False


def _thumbnail_cache_path(image_path):
    folder = os.path.dirname(image_path)
    thumb_dir = os.path.join(folder, THUMBNAIL_DIR_NAME)
    os.makedirs(thumb_dir, exist_ok=True)
    hash_str = hashlib.sha256(os.path.abspath(image_path).encode()).hexdigest()
    return os.path.join(thumb_dir, f"{hash_str}.jpg")


def ensure_thumbnail_image(image_path, size=(250, 250)):
    thumb_path = _thumbnail_cache_path(image_path)
    if not os.path.exists(thumb_path):
        try:
            with Image.open(image_path) as img:
                # Handle multi-frame images (like animated GIFs)
                if hasattr(img, "n_frames") and img.n_frames > 1:
                    img.seek(0)
                
                # Handle EXIF orientation
                img = ImageOps.exif_transpose(img)
                
                # Convert to RGB for compatibility with all modes
                if img.mode == "CMYK":
                    # CMYK requires inversion before conversion
                    from PIL import ImageChops
                    img = ImageChops.invert(img)
                    img = img.convert("RGB")
                    img = ImageChops.invert(img)
                elif img.mode.startswith("I;") or img.mode == "I":
                    # 16-bit or 32-bit integer modes - normalize to full range
                    img = img.point(lambda x: x / 256).convert("L")
                    img = ImageOps.autocontrast(img)  # Stretch to full 0-255 range
                    img = img.convert("RGB")
                elif img.mode not in ("RGB", "RGBA", "L"):
                    img = img.convert("RGB")
                
                # Create thumbnail
                img.thumbnail(size, Image.LANCZOS)
                
                # Ensure RGB for JPEG save
                if img.mode != "RGB":
                    img = img.convert("RGB")
                
                img.save(thumb_path, "JPEG", quality=85)
        except Exception as exc:
            print(f"Failed to create thumbnail for {image_path}: {exc}")
            # Write a lightweight placeholder so we do not retry (avoids repeated failures on unsupported formats like HEIC without plugins)
            try:
                placeholder = Image.new("RGB", size, (210, 210, 210))
                placeholder.save(thumb_path, "JPEG", quality=60)
                print(f"Wrote placeholder thumbnail for {image_path} -> {thumb_path}")
            except Exception as placeholder_exc:
                print(f"Failed to write placeholder thumbnail for {image_path}: {placeholder_exc}")
                return None
    return thumb_path


def ensure_preview_image(image_path, edge_length=DEFAULT_PREVIEW_MAX_EDGE):
    start = time.perf_counter()
    preview_path = _preview_cache_path(image_path, edge_length)
    if os.path.exists(preview_path) and _preview_is_current(image_path, preview_path):
        elapsed = time.perf_counter() - start
        print(
            f"[PreviewCache] Hit {image_path} edge={edge_length} -> {preview_path} ({elapsed:.2f}s)"
        )
        sys.stdout.flush()
        return preview_path
    print(
        f"[PreviewCache] Build {image_path} edge={edge_length} -> {preview_path}"
    )
    sys.stdout.flush()
    try:
        with Image.open(image_path) as img:
            # Handle multi-frame images (like animated GIFs)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                img.seek(0)
            
            # Handle EXIF orientation
            img = ImageOps.exif_transpose(img)
            
            # Convert to RGB for compatibility with all modes
            if img.mode == "CMYK":
                # CMYK requires inversion before conversion
                from PIL import ImageChops
                img = ImageChops.invert(img)
                img = img.convert("RGB")
                img = ImageChops.invert(img)
            elif img.mode.startswith("I;") or img.mode == "I":
                # 16-bit or 32-bit integer modes - normalize to full range
                img = img.point(lambda x: x / 256).convert("L")
                img = ImageOps.autocontrast(img)  # Stretch to full 0-255 range
                img = img.convert("RGB")
            elif img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGB")
            
            # Create thumbnail
            target_size = (edge_length, edge_length)
            img.thumbnail(target_size, Image.LANCZOS)
            
            # Ensure RGB for JPEG save
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            img.save(preview_path, "JPEG", quality=90)
        try:
            mtime = os.path.getmtime(image_path)
            os.utime(preview_path, (mtime, mtime))
        except OSError:
            pass
        elapsed = time.perf_counter() - start
        print(
            f"[PreviewCache] Built {image_path} edge={edge_length} in {elapsed:.2f}s"
        )
        sys.stdout.flush()
        return preview_path
    except Exception as exc:
        print(f"Failed to prepare preview for {image_path}: {exc}")
        sys.stdout.flush()
        try:
            if os.path.exists(preview_path):
                os.remove(preview_path)
        except OSError:
            pass
        return None

# === SIZE VARIABLES ===

# Buttons
SIZE_ADD_BUTTON_WIDTH = 75
SIZE_ADD_BUTTON_HEIGHT = 45
SIZE_TAG_ITEM_HEIGHT = 56  # Height for tag list items in display list

# === FONT SIZE VARIABLES (ALL FONT SIZES DEFINED HERE) ===
FONT_SIZE_DEFAULT = 12
FONT_SIZE_TAG_INPUT = 18
FONT_SIZE_TAG_LIST = 14
FONT_SIZE_INFO_BANNER = 12
FONT_SIZE_TAG_LABEL = 12
FONT_SIZE_TAG_LIST_ITEM = 12
FONT_SIZE_COMBOBOX = 14
FONT_SIZE_BUTTON = 14
FONT_SIZE_POPUP = 12

# Shared UI strings
TAG_SEARCH_PLACEHOLDER = "Search library for tag(s)"


class TagDatabase:
    """
    Note: Tags DB created at platform default:
    Platform | Database location
    macOS | ~/Library/Application Support/SPM/tags.db
    Linux | ~/.local/share/SPM/tags.db
    Windows | %LOCALAPPDATA%\\SPM\\tags.db
    """

    def __init__(self, db_path=None):
        appname = "SimplePhotoMeta"
        appauthor = "Zaziork"
        if db_path is None:
            db_dir = user_data_dir(appname, appauthor)
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "spm_tags.db")
        else:
            self.db_path = db_path
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        # Allow longer wait times when the writer thread is active and enable WAL so readers are not blocked.
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError as pragma_err:
            print(f"Warning: failed to configure SQLite pragmas: {pragma_err}")
        self._create_table()
        # Simple in-memory cache: tag_type -> sorted list of tags
        self._tag_cache = {}

    def _create_table(self):
        c = self.conn.cursor()
        # Tags table (add tag_type column)
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT,
                tag_type TEXT,
                UNIQUE(tag, tag_type)
            )
            """
        )
        # Images table
        c.execute(
            "CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE)"
        )
        # Image-Tags relationship table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS image_tags (
                image_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (image_id, tag_id),
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS scanned_dirs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                last_scan TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def flush_commit(self):
        """Commit and force flush any pending transactions, including WAL checkpoint."""
        self.conn.commit()
        # Force WAL checkpoint to ensure data is written to main database
        try:
            self.conn.execute("PRAGMA wal_checkpoint(FULL)")
        except:
            pass
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.commit()

    def cleanup_invalid_tags(self):
        """Remove tags that are empty, whitespace-only, or contain only invalid characters."""
        try:
            c = self.conn.cursor()
            # Get all tags
            c.execute("SELECT id, tag FROM tags")
            all_tags = c.fetchall()
            
            deleted_count = 0
            for tag_id, tag_text in all_tags:
                # Delete if empty, whitespace-only, or doesn't match valid pattern
                if not tag_text or not tag_text.strip():
                    c.execute("DELETE FROM tags WHERE id=?", (tag_id,))
                    deleted_count += 1
                elif not re.fullmatch(r"^[A-Za-z0-9\-\(\):\'\?\|\ ]+$", tag_text):
                    c.execute("DELETE FROM tags WHERE id=?", (tag_id,))
                    deleted_count += 1
            
            self.conn.commit()
            if deleted_count > 0:
                print(f"[DB Cleanup] Removed {deleted_count} invalid/empty tags from database")
                sys.stdout.flush()
                # Invalidate cache when tags change
                self._tag_cache.clear()
        except Exception as e:
            print(f"[DB Cleanup] Error during cleanup: {e}")
            sys.stdout.flush()

    def add_tag(self, tag, tag_type):
        try:
            c = self.conn.cursor()
            # Check if tag already exists
            c.execute("SELECT id FROM tags WHERE tag=? AND tag_type=?", (tag, tag_type))
            existing = c.fetchone()
            if existing:
                print(f"[DB] Tag '{tag}' already exists in DB with id={existing[0]}")
                sys.stdout.flush()
                return
            
            c.execute(
                "INSERT OR IGNORE INTO tags (tag, tag_type) VALUES (?, ?)",
                (tag, tag_type),
            )
            self.conn.commit()
            print(f"[DB] Inserted tag '{tag}' for tag_type '{tag_type}' into database")
            sys.stdout.flush()
            # Invalidate cache for this tag_type
            self._tag_cache.pop(tag_type, None)
            
            # Verify it was inserted
            c.execute("SELECT id FROM tags WHERE tag=? AND tag_type=?", (tag, tag_type))
            verify = c.fetchone()
            if verify:
                print(f"[DB] Verified: Tag '{tag}' now in DB with id={verify[0]}")
            else:
                print(f"[DB] WARNING: Tag '{tag}' was NOT found after insertion!")
            sys.stdout.flush()
        except Exception as e:
            print("Error inserting tag", tag, tag_type, e)
            sys.stdout.flush()

    def get_tag_id(self, tag, tag_type):
        c = self.conn.cursor()
        c.execute("SELECT id FROM tags WHERE tag=? AND tag_type=?", (tag, tag_type))
        row = c.fetchone()
        return row[0] if row else None

    def add_image(self, path):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO images (path) VALUES (?)", (path,))
        c.execute("SELECT id FROM images WHERE path=?", (path,))
        row = c.fetchone()
        return row[0] if row else None

    def get_image_id(self, path):
        c = self.conn.cursor()
        c.execute("SELECT id FROM images WHERE path=?", (path,))
        row = c.fetchone()
        return row[0] if row else None

    def add_image_tag(self, image_path, tag, tag_type):
        image_id = self.add_image(image_path)
        self.add_tag(tag, tag_type)
        tag_id = self.get_tag_id(tag, tag_type)
        if image_id and tag_id:
            c = self.conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                (image_id, tag_id),
            )
            self.conn.commit()

    def set_image_tags(self, image_path, tags, tag_type):
        image_id = self.add_image(image_path)
        c = self.conn.cursor()
        # Remove all existing tag associations for this image for this tag_type
        c.execute(
            "DELETE FROM image_tags WHERE image_id IN (SELECT images.id FROM images WHERE images.path=?) AND tag_id IN (SELECT id FROM tags WHERE tag_type=?)",
            (image_path, tag_type),
        )
        # Add new tags
        for tag in tags:
            self.add_tag(tag, tag_type)
            tag_id = self.get_tag_id(tag, tag_type)
            if tag_id:
                c.execute(
                    "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                    (image_id, tag_id),
                )
        self.conn.commit()
        # Invalidate cache for this tag_type
        self._tag_cache.pop(tag_type, None)
        # Force WAL checkpoint to ensure search sees updated data
        try:
            self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except:
            pass

    def bulk_update_image_tags(self, image_path, tags_by_type):
        """Update all tag associations for an image in a single transaction."""
        if tags_by_type is None:
            tags_by_type = {}
        with self.conn:
            image_id = self.add_image(image_path)
            if image_id is None:
                image_id = self.get_image_id(image_path)
            if image_id is None:
                return
            tag_types = list(tags_by_type.keys())
            if tag_types:
                placeholders = ",".join(["?"] * len(tag_types))
                params = [image_path] + tag_types
                self.conn.execute(
                    f"""
                    DELETE FROM image_tags
                    WHERE image_id IN (SELECT id FROM images WHERE path=?)
                    AND tag_id IN (
                        SELECT id FROM tags WHERE tag_type IN ({placeholders})
                    )
                    """,
                    params,
                )
            else:
                self.conn.execute(
                    "DELETE FROM image_tags WHERE image_id IN (SELECT id FROM images WHERE path=?)",
                    (image_path,),
                )
            for tag_type, tags in tags_by_type.items():
                for tag in tags:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO tags (tag, tag_type) VALUES (?, ?)",
                        (tag, tag_type),
                    )
                    row = self.conn.execute(
                        "SELECT id FROM tags WHERE tag=? AND tag_type=?",
                        (tag, tag_type),
                    ).fetchone()
                    if row:
                        self.conn.execute(
                            "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                            (image_id, row[0]),
                        )
            # Invalidate caches for all modified tag types
            for tag_type in tag_types:
                self._tag_cache.pop(tag_type, None)

    def get_tags(self, tag_type=None):
        # Return cached tags when available to avoid repeated DB fetch for large tag sets
        if tag_type in self._tag_cache:
            cached = self._tag_cache[tag_type]
            print(f"[DB] get_tags(tag_type='{tag_type}') cache hit: {len(cached)} tags")
            sys.stdout.flush()
            return cached

        c = self.conn.cursor()
        if tag_type:
            c.execute(
                "SELECT tag FROM tags WHERE tag_type=? ORDER BY tag ASC", (tag_type,)
            )
            result = [row[0] for row in c.fetchall()]
            self._tag_cache[tag_type] = result
            print(f"[DB] get_tags(tag_type='{tag_type}'): Found {len(result)} tags (cached)")
            sys.stdout.flush()
            return result
        else:
            c.execute("SELECT tag FROM tags ORDER BY tag ASC")
            result = [row[0] for row in c.fetchall()]
            # Cache under None for 'all tags'
            self._tag_cache[None] = result
            print(f"[DB] get_tags(tag_type=None): Found {len(result)} tags (cached)")
            sys.stdout.flush()
            return result

    def get_images_with_tags(self, tags, tag_type=None):
        c = self.conn.cursor()
        if not tags:
            if tag_type:
                # Return images that do NOT have any tags of this tag_type
                query = """
                    SELECT i.path FROM images i
                    WHERE i.id NOT IN (
                        SELECT it.image_id FROM image_tags it
                        JOIN tags t ON t.id = it.tag_id
                        WHERE t.tag_type = ?
                    )
                    ORDER BY i.path ASC
                """
                c.execute(query, (tag_type,))
                return [row[0] for row in c.fetchall()]
            else:
                c.execute("SELECT path FROM images ORDER BY path ASC")
                return [row[0] for row in c.fetchall()]
        base_query = """SELECT i.path FROM images i\n"""
        join_clauses = []
        where_clauses = []
        params = []
        for idx, tag in enumerate(tags):
            join_clauses.append(
                f"JOIN image_tags it{idx} ON i.id = it{idx}.image_id JOIN tags t{idx} ON t{idx}.id = it{idx}.tag_id"
            )
            where_clauses.append(f"t{idx}.tag LIKE ?")
            params.append(f"%{tag}%")
            if tag_type:
                where_clauses.append(f"t{idx}.tag_type = ?")
                params.append(tag_type)
        query = base_query + " ".join(join_clauses)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " GROUP BY i.id ORDER BY i.path ASC"
        c.execute(query, params)
        return [row[0] for row in c.fetchall()]

    def get_image_count_in_folder(self, folder_path, tags=None, tag_type=None):
        c = self.conn.cursor()
        if tags:
            base_query = """SELECT COUNT(DISTINCT i.id) FROM images i\n"""
            join_clauses = []
            where_clauses = []
            params = []
            for idx, tag in enumerate(tags):
                join_clauses.append(
                    f"JOIN image_tags it{idx} ON i.id = it{idx}.image_id JOIN tags t{idx} ON t{idx}.id = it{idx}.tag_id"
                )
                # Normalize both search term and stored tag by removing common punctuation
                normalized_tag = tag.replace("'", "").replace('"', "").replace("-", "").replace(".", "").replace(",", "").replace("!", "").replace("?", "")
                where_clauses.append(
                    f"REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(t{idx}.tag, '''', ''), '\"', ''), '-', ''), '.', ''), ',', ''), '!', ''), '?', '') LIKE ?"
                )
                params.append(f"%{normalized_tag}%")
                if tag_type:
                    where_clauses.append(f"t{idx}.tag_type = ?")
                    params.append(tag_type)
            query = base_query + " ".join(join_clauses)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " AND " if where_clauses else " WHERE "
            query += "i.path LIKE ?"
            params.append(os.path.join(os.path.abspath(folder_path), "%"))
            c.execute(query, params)
        else:
            query = "SELECT COUNT(*) FROM images WHERE path LIKE ?"
            c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"),))
        row = c.fetchone()
        return row[0] if row else 0

    def get_images_in_folder_paginated(
        self, folder_path, page, page_size, tags=None, tag_type=None
    ):
        c = self.conn.cursor()
        offset = page * page_size
        if tags:
            base_query = """SELECT i.path FROM images i\n"""
            join_clauses = []
            where_clauses = []
            params = []
            for idx, tag in enumerate(tags):
                join_clauses.append(
                    f"JOIN image_tags it{idx} ON i.id = it{idx}.image_id JOIN tags t{idx} ON t{idx}.id = it{idx}.tag_id"
                )
                # Normalize both search term and stored tag by removing common punctuation
                normalized_tag = tag.replace("'", "").replace('"', "").replace("-", "").replace(".", "").replace(",", "").replace("!", "").replace("?", "")
                where_clauses.append(
                    f"REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(t{idx}.tag, '''', ''), '\"', ''), '-', ''), '.', ''), ',', ''), '!', ''), '?', '') LIKE ?"
                )
                params.append(f"%{normalized_tag}%")
                if tag_type:
                    where_clauses.append(f"t{idx}.tag_type = ?")
                    params.append(tag_type)
            query = base_query + " ".join(join_clauses)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " AND " if where_clauses else " WHERE "
            query += "i.path LIKE ?"
            params.append(os.path.join(os.path.abspath(folder_path), "%"))
            query += " GROUP BY i.id ORDER BY i.path ASC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            print(f"[DB Query] Searching for tags={tags}, tag_type={tag_type}")
            print(f"[DB Query] SQL: {query}")
            print(f"[DB Query] Params: {params}")
            sys.stdout.flush()
            c.execute(query, params)
            results = [row[0] for row in c.fetchall()]
            print(f"[DB Query] Found {len(results)} matching images")
            sys.stdout.flush()
            return results
        else:
            query = "SELECT path FROM images WHERE path LIKE ? ORDER BY path ASC LIMIT ? OFFSET ?"
            c.execute(
                query,
                (os.path.join(os.path.abspath(folder_path), "%"), page_size, offset),
            )
        return [row[0] for row in c.fetchall()]

    def get_untagged_images_in_folder_paginated(self, folder_path, page, page_size):
        c = self.conn.cursor()
        offset = page * page_size
        # Select images in folder that have no tags
        query = """
            SELECT i.path FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            WHERE i.path LIKE ? AND it.tag_id IS NULL
            ORDER BY i.path ASC LIMIT ? OFFSET ?
        """
        c.execute(
            query, (os.path.join(os.path.abspath(folder_path), "%"), page_size, offset)
        )
        return [row[0] for row in c.fetchall()]

    def get_untagged_image_count_in_folder(self, folder_path):
        c = self.conn.cursor()
        query = """
            SELECT COUNT(*) FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            WHERE i.path LIKE ? AND it.tag_id IS NULL
        """
        c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"),))
        row = c.fetchone()
        return row[0] if row else 0

    def get_untagged_images_of_type_in_folder_paginated(
        self, folder_path, page, page_size, tag_type
    ):
        c = self.conn.cursor()
        offset = page * page_size
        query = """
            SELECT i.path FROM images i
            WHERE i.path LIKE ? AND i.id NOT IN (
                SELECT it.image_id FROM image_tags it
                JOIN tags t ON t.id = it.tag_id
                WHERE t.tag_type = ?
            )
            ORDER BY i.path ASC LIMIT ? OFFSET ?
        """
        c.execute(
            query,
            (
                os.path.join(os.path.abspath(folder_path), "%"),
                tag_type,
                page_size,
                offset,
            ),
        )
        return [row[0] for row in c.fetchall()]

    def get_untagged_image_count_of_type_in_folder(self, folder_path, tag_type):
        c = self.conn.cursor()
        query = """
            SELECT COUNT(*) FROM images i
            WHERE i.path LIKE ? AND i.id NOT IN (
                SELECT it.image_id FROM image_tags it
                JOIN tags t ON t.id = it.tag_id
                WHERE t.tag_type = ?
            )
        """
        c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"), tag_type))
        row = c.fetchone()
        return row[0] if row else 0

    def get_images_with_type_in_folder_paginated(
        self, folder_path, page, page_size, tag_type
    ):
        """Get images that have ANY tags of the specified type."""
        c = self.conn.cursor()
        offset = page * page_size
        query = """
            SELECT DISTINCT i.path FROM images i
            JOIN image_tags it ON i.id = it.image_id
            JOIN tags t ON t.id = it.tag_id
            WHERE i.path LIKE ? AND t.tag_type = ?
            ORDER BY i.path ASC LIMIT ? OFFSET ?
        """
        c.execute(
            query,
            (
                os.path.join(os.path.abspath(folder_path), "%"),
                tag_type,
                page_size,
                offset,
            ),
        )
        return [row[0] for row in c.fetchall()]

    def get_image_count_with_type_in_folder(self, folder_path, tag_type):
        """Count images that have ANY tags of the specified type."""
        c = self.conn.cursor()
        query = """
            SELECT COUNT(DISTINCT i.id) FROM images i
            JOIN image_tags it ON i.id = it.image_id
            JOIN tags t ON t.id = it.tag_id
            WHERE i.path LIKE ? AND t.tag_type = ?
        """
        c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"), tag_type))
        row = c.fetchone()
        return row[0] if row else 0

    def mark_directory_scanned(self, dir_path):
        c = self.conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO scanned_dirs (path, last_scan) VALUES (?, datetime('now'))",
            (os.path.abspath(dir_path),),
        )
        self.conn.commit()

    def was_directory_scanned(self, dir_path):
        c = self.conn.cursor()
        c.execute(
            "SELECT last_scan FROM scanned_dirs WHERE path=?",
            (os.path.abspath(dir_path),),
        )
        row = c.fetchone()
        return row[0] if row else None

    def remove_missing_images(self, dir_path):
        c = self.conn.cursor()
        c.execute(
            "SELECT path FROM images WHERE path LIKE ?",
            (os.path.join(os.path.abspath(dir_path), "%"),),
        )
        all_paths = [row[0] for row in c.fetchall()]
        removed = 0
        for path in all_paths:
            if not os.path.exists(path):
                c.execute("DELETE FROM images WHERE path=?", (path,))
                removed += 1
        self.conn.commit()
        return removed

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def purge_cache_images(self):
        patterns = [
            f"%{os.sep}{PREVIEW_CACHE_DIR_NAME}{os.sep}%",
            f"%{os.sep}.thumbnails{os.sep}%",
        ]
        with self.conn:
            for pattern in patterns:
                self.conn.execute(
                    "DELETE FROM images WHERE path LIKE ?",
                    (pattern,),
                )


class ScanWorker(QThread):
    scan_finished = Signal(str, bool)
    scan_progress = Signal(str, int)
    batch_ready = Signal(str, int)

    def __init__(self, folder_path, db_path, batch_size=25):
        super().__init__()
        self.folder_path = folder_path
        self.db_path = db_path
        self._batch_size = max(1, batch_size)

    def run(self):
        processed = 0
        cancelled = False
        db = None
        try:
            db = TagDatabase(self.db_path)
            supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif")
            for root, dirs, files in os.walk(self.folder_path):
                if self.isInterruptionRequested():
                    cancelled = True
                    break
                if ".thumbnails" in dirs:
                    dirs.remove(".thumbnails")
                if PREVIEW_CACHE_DIR_NAME in dirs:
                    dirs.remove(PREVIEW_CACHE_DIR_NAME)
                for fname in files:
                    if self.isInterruptionRequested():
                        cancelled = True
                        break
                    if not fname.lower().endswith(supported):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        meta = Exiv2Bind(fpath)
                        result = meta.to_dict()
                        iptc_data = result.get("iptc", {})
                        tags_by_type = {}
                        for field in iptc_tags.iptc_writabable_fields_list:
                            value = iptc_data.get(field)
                            if isinstance(value, list):
                                tags = [tag for tag in value if tag]
                            elif isinstance(value, str):
                                tags = [value] if value else []
                            else:
                                tags = []
                            tags_by_type[field] = tags
                        db.bulk_update_image_tags(fpath, tags_by_type)
                    except Exception as e:
                        print(f"Error: {e}")
                    processed += 1
                    if processed == 1 or processed % self._batch_size == 0:
                        self.batch_ready.emit(self.folder_path, processed)
                        self.scan_progress.emit(self.folder_path, processed)
                if cancelled:
                    break
        except Exception as err:
            print(f"ScanWorker error: {err}")
        finally:
            if db:
                db.close()
            if processed and (processed % self._batch_size):
                self.batch_ready.emit(self.folder_path, processed)
                self.scan_progress.emit(self.folder_path, processed)
            self.scan_finished.emit(self.folder_path, not cancelled)


class PreviewWorker(QThread):
    preview_ready = Signal(str, str, int)
    preview_failed = Signal(str, str, int)

    def __init__(self, image_path, edge_length):
        super().__init__()
        self.image_path = image_path
        self.edge_length = max(512, int(edge_length))

    def run(self):
        start = time.perf_counter()
        print(f"[PreviewWorker] Start {self.image_path} edge={self.edge_length}")
        sys.stdout.flush()
        if self.isInterruptionRequested():
            print(f"[PreviewWorker] Cancelled before work {self.image_path}")
            sys.stdout.flush()
            return
        try:
            preview_path = ensure_preview_image(self.image_path, self.edge_length)
            if self.isInterruptionRequested() or not preview_path:
                elapsed = time.perf_counter() - start
                print(
                    f"[PreviewWorker] Failed {self.image_path} edge={self.edge_length} in {elapsed:.2f}s"
                )
                sys.stdout.flush()
                self.preview_failed.emit(
                    self.image_path, "Preview generation failed.", self.edge_length
                )
                return
            elapsed = time.perf_counter() - start
            print(
                f"[PreviewWorker] Done {self.image_path} edge={self.edge_length} in {elapsed:.2f}s"
            )
            sys.stdout.flush()
            self.preview_ready.emit(self.image_path, preview_path, self.edge_length)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(
                f"[PreviewWorker] Exception {self.image_path} edge={self.edge_length} in {elapsed:.2f}s: {exc}"
            )
            sys.stdout.flush()
            self.preview_failed.emit(self.image_path, str(exc), self.edge_length)


class MetadataWorker(QThread):
    metadata_ready = Signal(str, str, list)
    metadata_failed = Signal(str, str, str)

    def __init__(self, image_path, tag_type, metadata_type="iptc"):
        super().__init__()
        self.image_path = image_path
        self.tag_type = tag_type
        self.metadata_type = metadata_type

    def run(self):
        start = time.perf_counter()
        print(
            f"[MetadataWorker] Start {self.image_path} type={self.metadata_type} tag={self.tag_type}"
        )
        sys.stdout.flush()
        if self.isInterruptionRequested():
            print(f"[MetadataWorker] Cancelled before work {self.image_path}")
            sys.stdout.flush()
            return
        try:
            meta = Exiv2Bind(self.image_path)
            result = meta.to_dict()
            metadata_section = result.get(self.metadata_type, {})
            tags = []
            for field, value in metadata_section.items():
                if field == self.tag_type:
                    if isinstance(value, list):
                        tags.extend(value)
                    elif isinstance(value, str):
                        tags.append(value)
            tags = [t.strip() for t in tags if t and t.strip()]
            if self.isInterruptionRequested():
                print(
                    f"[MetadataWorker] Cancelled after read {self.image_path}"
                )
                sys.stdout.flush()
                return
            elapsed = time.perf_counter() - start
            print(
                f"[MetadataWorker] Done {self.image_path} type={self.metadata_type} tag={self.tag_type} in {elapsed:.2f}s"
            )
            sys.stdout.flush()
            self.metadata_ready.emit(self.image_path, self.tag_type, tags)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(
                f"[MetadataWorker] Exception {self.image_path} type={self.metadata_type} tag={self.tag_type} in {elapsed:.2f}s: {exc}"
            )
            sys.stdout.flush()
            if not self.isInterruptionRequested():
                self.metadata_failed.emit(self.image_path, self.tag_type, str(exc))


class ThumbnailBatchWorker(QThread):
    thumbnail_ready = Signal(int, str, str, int)  # row, path, thumb_path, generation_id
    finished = Signal()

    def __init__(self, tasks, generation_id=0, size=(250, 250)):
        super().__init__()
        self.tasks = tasks  # List of (row_index, image_path)
        self.generation_id = generation_id
        self.size = size

    def run(self):
        try:
            for row_index, image_path in self.tasks:
                if self.isInterruptionRequested():
                    print(f"[ThumbnailWorker gen={self.generation_id}] Interrupted before processing")
                    sys.stdout.flush()
                    break
                try:
                    thumb_path = ensure_thumbnail_image(image_path, self.size)
                except Exception as exc:
                    print(f"[ThumbnailWorker gen={self.generation_id}] Failed {image_path}: {exc}")
                    sys.stdout.flush()
                    continue
                if self.isInterruptionRequested():
                    print(f"[ThumbnailWorker gen={self.generation_id}] Interrupted after processing")
                    sys.stdout.flush()
                    break
                if thumb_path:
                    self.thumbnail_ready.emit(row_index, image_path, thumb_path, self.generation_id)
        finally:
            print(f"[ThumbnailWorker gen={self.generation_id}] Worker run() complete")
            sys.stdout.flush()
            self.finished.emit()


class CustomMessageDialog(QDialog):
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        layout.addWidget(self.label)
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.setMinimumWidth(350)
        self.setMinimumHeight(120)
        self.adjustSize()
        self.setStyleSheet("")


class CustomPopupDialog(QDialog):
    def __init__(self, parent=None, title="", message="", icon: QPixmap = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        # Icon and text row
        row = QHBoxLayout()
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(
                icon.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            icon_label.setContentsMargins(12, 12, 12, 12)
            row.addWidget(icon_label, alignment=Qt.AlignTop)
        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setContentsMargins(12, 12, 12, 12)
        text_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        row.addWidget(text_label)
        layout.addLayout(row)
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        btn.setStyleSheet("")
        layout.addWidget(btn, alignment=Qt.AlignRight)
        self.setMinimumWidth(420)
        self.setMinimumHeight(160)
        self.setStyleSheet("")
        self.adjustSize()


class IPTCEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Photo Meta (alpha)")
        
        # Set window icon for taskbar
        self._set_window_icon()
        
        # Dynamically set initial window size based on available screen size
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        # Use 80% of available screen, but max 1200x800, min 800x600
        if available:
            width = min(int(available.width() * 0.8), 1200)
            height = min(int(available.height() * 0.8), 800)
            width = max(width, 800)
            height = max(height, 600)
            self.resize(width, height)
        else:
            self.resize(1200, 800)
        # Do NOT set minimum or maximum size for the main window, to allow maximize to work on all platforms
        self.folder_path = ""
        self.image_list = []
        self.current_image_path = None
        self.current_page = 0
        self.page_size = 25
        self.total_pages = 1
        self.selected_iptc_tag = None  # <-- Store selected tag dict
        self._preview_retry_counts = {}
        self._preview_timers = {}
        self._metadata_timers = {}
        self._metadata_pending_key = None
        self.cleaned_keywords = []
        # Create or open the SQLite database
        self.db = TagDatabase()
        self.db.cleanup_invalid_tags()  # Clean up any invalid/empty tags on startup
        self.db.purge_cache_images()
        self._preview_log_path = self._init_preview_log()
        self.worker = None
        self._active_scan_folder = None
        self.preview_worker = None
        self._active_preview_workers = set()
        self._pending_preview_key = None
        self.metadata_worker = None
        self._active_metadata_workers = set()
        self.thumbnail_worker = None
        self._active_thumbnail_workers = set()
        self._thumbnail_generation_id = 0  # Track which thumbnail batch is current
        
        # Set a single variable for consistent corner radius across all UI elements
        self.corner_radius = 16
        
        # Use native system styling - no custom stylesheets
        self.setStyleSheet("")

        self._tag_item_cache = {}
        self._tag_order = []
        
        self.create_menu_bar()
        self.create_widgets()
        self.load_previous_tags()
        self._scan_refresh_timer = QTimer(self)
        self._scan_refresh_timer.setSingleShot(True)
        self._scan_refresh_timer.timeout.connect(self._refresh_view_after_scan)
        self._scan_status_clear_timer = QTimer(self)
        self._scan_status_clear_timer.setSingleShot(True)
        self._scan_status_clear_timer.timeout.connect(self.clear_scan_status)

    def _set_window_icon(self):
        """Set window icon for taskbar display"""
        # Try to find icon in different locations based on execution context
        icon_paths = []
        
        if self._is_compiled_binary():
            if sys.platform == 'darwin':
                # macOS app bundle
                app_bundle = self._find_macos_app_bundle()
                if app_bundle:
                    icon_paths.append(os.path.join(app_bundle, 'Contents', 'Resources', 'SimplePhotoMeta.icns'))
            else:
                # Linux AppImage
                appdir = os.environ.get('APPDIR', '')
                if appdir:
                    icon_paths.extend([
                        os.path.join(appdir, 'usr', 'share', 'icons', 'hicolor', '256x256', 'apps', 'simple-photo-meta.png'),
                        os.path.join(appdir, 'simple-photo-meta.png'),
                    ])
                # Also check relative to executable
                exe_dir = os.path.dirname(sys.executable)
                icon_paths.append(os.path.join(exe_dir, 'simple-photo-meta.png'))
        else:
            # Running from source
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_paths.extend([
                os.path.join(base_dir, 'icons', 'icon_appimage.png'),
                os.path.join(base_dir, 'icons', 'SimplePhotoMeta.icns'),
            ])
        
        # Try each path and set the first valid icon found
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    return

    def style_dialog(self, dialog, min_width=380, min_height=120, padding=18):
        """
        Apply minimum size and padding to dialogs for better readability, and set background/text color for Linux compatibility.
        Also set button text color to gold.
        For QMessageBox, do not force fixed size—let it autosize, but ensure word wrap and margins.
        """
        dialog.setMinimumWidth(min_width)
        dialog.setMinimumHeight(min_height)
        dialog.setStyleSheet("")
        # If it's a QMessageBox, set word wrap and margins for the label and icon, but do not force fixed size
        if isinstance(dialog, QMessageBox):
            dialog.setMinimumWidth(max(min_width, 380))
            dialog.setMinimumHeight(max(min_height, 120))
            layout = dialog.layout()
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    widget = item.widget()
                    if isinstance(widget, QLabel):
                        widget.setWordWrap(True)
                        widget.setContentsMargins(24, 18, 24, 18)
                        if widget.pixmap() is not None:
                            widget.setContentsMargins(24, 24, 24, 24)

    def create_menu_bar(self):
        """Create menu bar with Help menu"""
        menu_bar = self.menuBar()
        
        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        
        # About action
        about_action = help_menu.addAction("&About Simple Photo Meta")
        about_action.triggered.connect(self.show_about_dialog)
        
        # View Licenses action
        licenses_action = help_menu.addAction("View &Licenses")
        licenses_action.triggered.connect(self.open_licenses_folder)
    
    def show_about_dialog(self):
        """Show About dialog with app info"""
        about_text = (
            "<h3>Simple Photo Meta</h3>"
            "<p>Version 0.1.0 (alpha)</p>"
            "<p>A GUI tool for editing IPTC and EXIF metadata in images.</p>"
            "<p>Copyright © 2025 Dan Bright</p>"
            "<p>Licensed under GNU General Public License v3.0</p>"
            "<p><a href='licenses'>View Third-Party Licenses</a></p>"
        )
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About Simple Photo Meta")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(about_text)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        # Enable link interaction and connect to licenses folder
        for label in msg_box.findChildren(QLabel):
            if label.textFormat() == Qt.RichText:
                label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                label.setOpenExternalLinks(False)
                label.linkActivated.connect(lambda url: self.open_licenses_folder())
        
        self.style_dialog(msg_box, min_width=400, min_height=200)
        msg_box.exec()
    
    def _is_compiled_binary(self):
        """Check if running as a compiled Nuitka binary"""
        # Nuitka sets __compiled__ on modules, or we can check for temp extraction
        return (
            getattr(sys, 'frozen', False) or 
            '__compiled__' in dir() or
            hasattr(sys, '__compiled__') or
            'nuitka' in sys.executable.lower() or
            '/var/folders/' in sys.executable or  # macOS temp extraction
            '/tmp/' in sys.executable  # Linux temp extraction
        )
    
    def _find_macos_app_bundle(self):
        """Find the .app bundle path on macOS when running as Nuitka onefile"""
        
        # Method 1: Check lsappinfo for this process
        try:
            result = subprocess.run(
                ['lsappinfo', 'info', '-only', 'bundlepath', '-app', 'SPM'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                # Parse output like: "bundlepath"="/Applications/SPM.app"
                for line in result.stdout.strip().split('\n'):
                    if 'bundlepath' in line and '=' in line:
                        path = line.split('=', 1)[1].strip().strip('"')
                        if os.path.exists(path):
                            return path
        except Exception:
            pass
        
        # Method 2: Check common install locations
        common_paths = [
            '/Applications/SPM.app',
            os.path.expanduser('~/Applications/SPM.app'),
            '/Applications/Simple Photo Meta.app',
            os.path.expanduser('~/Applications/Simple Photo Meta.app'),
        ]
        for app_path in common_paths:
            if os.path.exists(app_path):
                return app_path
        
        return None
    
    def open_licenses_folder(self):
        """Open the licenses directory in file manager"""
        licenses_path = None
        
        if self._is_compiled_binary():
            # Running as compiled binary
            if sys.platform == 'darwin':
                # macOS: Find the .app bundle
                app_bundle = self._find_macos_app_bundle()
                if app_bundle:
                    licenses_path = os.path.join(app_bundle, 'Contents', 'Resources', 'licenses')
            else:
                # Linux AppImage: uses APPDIR environment variable
                appdir = os.environ.get('APPDIR', '')
                if appdir:
                    licenses_path = os.path.join(appdir, 'usr', 'share', 'licenses', 'simple-photo-meta')
                else:
                    base_path = os.path.dirname(sys.executable)
                    licenses_path = os.path.join(base_path, '..', 'share', 'licenses', 'simple-photo-meta')
        else:
            # Running from source: licenses are in repo root
            licenses_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'licenses')
        
        # Normalize and resolve the path
        if licenses_path:
            licenses_path = os.path.normpath(os.path.abspath(licenses_path))
        
        if not licenses_path or not os.path.exists(licenses_path):
            QMessageBox.warning(
                self,
                "Licenses Not Found",
                f"Could not locate licenses directory.\n\nSearched path: {licenses_path or 'None'}\n\n"
                f"If installed, licenses should be in:\n/Applications/SPM.app/Contents/Resources/licenses"
            )
            return
        
        # Open in file manager
        try:
            if sys.platform == 'darwin':
                result = subprocess.run(['open', licenses_path], capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"open command failed: {result.stderr}")
            elif sys.platform.startswith('linux'):
                subprocess.run(['xdg-open', licenses_path], check=True)
            elif sys.platform == 'win32':
                os.startfile(licenses_path)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Opening Licenses",
                f"Could not open licenses folder:\n{e}\n\nPath: {licenses_path}"
            )
    
    def _refresh_view_after_scan(self):
        if self.folder_path:
            self.show_current_page()

    def show_auto_close_message(
        self, title, message, icon=QMessageBox.Information, timeout=1000
    ):
        """
        Shows a QMessageBox that automatically closes after 'timeout' milliseconds.

        :param title: The title of the message box.
        :param message: The message text.
        :param icon: The icon of the message box (e.g., QMessageBox.Information, etc.).
        :param timeout: Time in milliseconds before the message box is automatically closed.
        """
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        self.style_dialog(msg_box)

        # Set the timer to automatically close the message box.
        QTimer.singleShot(timeout, msg_box.close)
        msg_box.exec()

    def show_custom_popup(self, title, message, icon: QPixmap = None):
        dlg = CustomPopupDialog(self, title, message, icon)
        dlg.exec()

    def show_custom_confirm(
        self,
        title,
        message,
        yes_text="Yes",
        no_text="No",
        cancel_text=None,
        icon: QPixmap = None,
    ):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        layout = QVBoxLayout(dlg)
        row = QHBoxLayout()
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(
                icon.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            icon_label.setContentsMargins(12, 12, 12, 12)
            row.addWidget(icon_label, alignment=Qt.AlignTop)
        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setContentsMargins(12, 12, 12, 12)
        row.addWidget(text_label)
        layout.addLayout(row)
        btn_row = QHBoxLayout()
        btn_yes = QPushButton(yes_text)
        btn_no = QPushButton(no_text)
        btn_yes.setStyleSheet("")
        btn_no.setStyleSheet("")
        btn_row.addWidget(btn_yes)
        btn_row.addWidget(btn_no)
        if cancel_text:
            btn_cancel = QPushButton(cancel_text)
            btn_cancel.setStyleSheet("")
            btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)
        result = {"value": None}

        def yes():
            result["value"] = "yes"
            dlg.accept()

        def no():
            result["value"] = "no"
            dlg.accept()

        def cancel():
            result["value"] = "cancel"
            dlg.reject()

        btn_yes.clicked.connect(yes)
        btn_no.clicked.connect(no)
        if cancel_text:
            btn_cancel.clicked.connect(cancel)
        dlg.setMinimumWidth(420)
        dlg.setMinimumHeight(160)
        dlg.setStyleSheet("")
        dlg.exec()
        return result["value"]

    def create_widgets(self):
        # ============================================================================
        # CENTRALIZED STYLESHEETS - All widget styles defined here (using system palette)
        # ============================================================================
        
        # Scrollbar styles (using palette)
        scrollbar_style = ""
        scrollbar_style_wide = ""
        
        # Main window and container styles - use native
        style_central_widget = ""
        style_outer_container = ""
        style_bottom_spacer = ""
        
        # Metadata dropdown styles - use native
        style_metadata_dropdown = ""

        def build_metadata_view_stylesheet(min_width=None):
            return ""

        style_metadata_format_dropdown_view = ""
        style_metadata_type_dropdown_view = ""

        def apply_metadata_combobox_style(combo, view_stylesheet):
            combo.setStyleSheet("")

        def apply_default_font(widgets):
            for widget in widgets:
                widget.setFont(self.font())
        
        # Scan status label - native
        style_scan_status_label = ""
        
        # Thumbnail list view - native
        style_list_view = ""
        
        # Image preview label - native
        style_image_label = ""
        
        # Tag input container - native
        style_iptc_input_container = ""
        
        # Tag display list - palette colors with row separation
        style_tag_display_list = """
            QListWidget {
                background: palette(window);
                border: 2px solid palette(dark);
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                background: palette(base);
                border: 1px solid palette(dark);
                border-radius: 4px;
                padding: 6px;
                margin: 2px;
            }
        """
        
        # Tag input field - palette colors
        style_iptc_text_edit = """
            QLineEdit {
                background: palette(base);
                border: 2px solid palette(dark);
                border-radius: 6px;
                color: palette(text);
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: palette(highlight);
            }
        """
        
        # Tag suggestions list - palette colors
        style_tag_suggestions_list = """
            QListWidget {
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
        """
        
        # Tags list widget (right panel) - palette colors
        style_tags_list_widget = """
            QListWidget {
                background: palette(window);
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 6px;
                margin: 2px;
            }
        """
        
        # Search bars - palette colors
        style_search_bar = """
            QTextEdit {
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 6px;
            }
            QTextEdit:focus {
                border-color: palette(highlight);
            }
        """

        style_tags_search_bar = """
            QLineEdit {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
                color: palette(text);
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: palette(highlight);
            }
        """
        
        # Buttons - native
        style_button = ""

        def apply_button_style(buttons):
            for button in buttons:
                button.setStyleSheet(style_button)
        
        # Page label - native
        self.style_page_label = ""
        
        # ============================================================================
        # END OF CENTRALIZED STYLESHEETS
        # ============================================================================
        
        central_widget = QWidget()
        # Note: WA_TranslucentBackground removed - was causing tooltip transparency issues on Linux
        central_widget.setStyleSheet(style_central_widget)
        central_widget.setContentsMargins(0,0,0,0)
        self.setCentralWidget(central_widget)

        # === BEGIN: Wrap all widgets in a single outer QWidget ===
        outer_container = QWidget()
        outer_container.setAttribute(Qt.WA_StyledBackground)
        outer_container.setAutoFillBackground(True)
        outer_container.setStyleSheet(style_outer_container)
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(0)
        outer_container.setLayout(outer_layout)
        
        # Add a bottom spacer to prevent widgets from extending to the very bottom
        bottom_spacer = QWidget()
        bottom_spacer.setFixedHeight(4)
        bottom_spacer.setStyleSheet(style_bottom_spacer)

        # Use a QSplitter for user-adjustable left pane
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL: folder and image list
        left_panel = QVBoxLayout()
        
        # Metadata Type Selector (IPTC/EXIF tabs with dropdowns) - at top
        # Initialize metadata type tracking first
        self.current_metadata_type = "iptc"  # Start with IPTC
        
        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        self.btn_scan_directory = QPushButton("Scan Directory")
        self.btn_scan_directory.clicked.connect(self.scan_directory)
        self.search_bar = QTextEdit()
        self.search_bar.setMaximumHeight(50)  # Increased from 30 to 50
        self.search_bar.setPlaceholderText(TAG_SEARCH_PLACEHOLDER)
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        self.search_bar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.search_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self.update_search)

        # Metadata selector container (format + field in one row)
        self.current_metadata_type = "iptc"
        metadata_selector_container = QWidget()
        metadata_selector_layout = QHBoxLayout(metadata_selector_container)
        metadata_selector_layout.setContentsMargins(0, 0, 0, 0)
        metadata_selector_layout.setSpacing(8)
        
        # Metadata format selector (IPTC/EXIF) - left side
        self.metadata_format_dropdown = QComboBox()
        self.metadata_format_dropdown.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.metadata_format_dropdown.setMinimumHeight(38)
        self.metadata_format_dropdown.setMaximumWidth(100)
        self.metadata_format_dropdown.addItem("IPTC", "iptc")
        self.metadata_format_dropdown.addItem("EXIF", "exif")
        self.metadata_format_dropdown.currentIndexChanged.connect(self.on_metadata_format_changed)
        apply_metadata_combobox_style(self.metadata_format_dropdown, style_metadata_format_dropdown_view)
        
        # Metadata field selector (tag type within selected format) - right side
        self.metadata_type_dropdown = QComboBox()
        self.metadata_type_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.metadata_type_dropdown.setMinimumHeight(38)
        self.metadata_type_dropdown.currentIndexChanged.connect(self.on_metadata_field_changed)
        apply_metadata_combobox_style(self.metadata_type_dropdown, style_metadata_type_dropdown_view)
        
        # Populate IPTC fields initially
        keyword_index = 0
        for i, tag in enumerate(iptc_tags.iptc_writable_tags):
            display_name = tag["name"].upper()
            self.metadata_type_dropdown.addItem(display_name, tag)
            if tag["tag"] == "Keywords":
                keyword_index = i
        
        self.metadata_type_dropdown.setCurrentIndex(keyword_index)
        self.selected_iptc_tag = iptc_tags.iptc_writable_tags[keyword_index]
        self.selected_exif_tag = None
        
        # Add both dropdowns to container
        metadata_selector_layout.addWidget(self.metadata_format_dropdown)
        metadata_selector_layout.addWidget(self.metadata_type_dropdown)
        
        left_panel.addWidget(self.btn_select_folder)
        left_panel.addWidget(self.btn_scan_directory)
        left_panel.addWidget(metadata_selector_container)
        left_panel.addWidget(self.search_bar)
        self.scan_status_label = QLabel()
        self.scan_status_label.setStyleSheet(style_scan_status_label)
        self.scan_status_label.setVisible(False)
        left_panel.addWidget(self.scan_status_label)

        # Thumbnails list
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.IconMode)
        # Increase icon size for two-abreast layout
        self.list_view.setIconSize(QPixmap(175, 175).size())
        self.list_view.setResizeMode(QListView.Adjust)
        self.list_view.setSpacing(14)  # Increased spacing for two columns
        self.list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_view.setMovement(QListView.Static)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setMinimumHeight(250)
        # Remove fixed width constraints so it expands with the splitter
        self.list_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list_view.clicked.connect(self.image_selected)
        # Add context menu policy and handler for right-click
        self.list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(
            self.show_image_filename_context_menu
        )
        self.list_view.setStyleSheet(style_list_view)
        left_panel.addWidget(self.list_view)

        # Pagination controls
        self.pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.next_page)
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignCenter)
        self.pagination_layout.addWidget(self.btn_prev)
        self.pagination_layout.addWidget(self.page_label, 1)  # Stretch factor 1 to center
        self.pagination_layout.addWidget(self.btn_next)
        left_panel.addLayout(self.pagination_layout)

        # Add left panel to main layout
        left_panel_widget = QWidget()
        left_panel_widget.setContentsMargins(0,0,0,0)
        left_panel_widget.setLayout(left_panel)
        main_splitter.addWidget(left_panel_widget)

        # CENTER PANEL: image display and IPTC metadata editor in a vertical splitter
        center_splitter = QSplitter(Qt.Vertical)

        # Canvas for image display (expandable) with buttons overlaid at bottom
        image_widget = QWidget()
        image_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # Don't use layout for image_widget, manage children manually for proper overlay positioning

        self.image_label = QLabel("Image preview will appear here ...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(style_image_label)
        self.image_label.setScaledContents(True)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_label.setCursor(Qt.PointingHandCursor)
        self.image_label.mouseDoubleClickEvent = self.on_preview_image_clicked
        self.image_label.setParent(image_widget)

        # Create overlay widget for buttons (positioned at bottom with absolute positioning)
        button_overlay = QWidget(image_widget)
        button_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        button_overlay.setAttribute(Qt.WA_TranslucentBackground, True)
        button_overlay_layout = QHBoxLayout(button_overlay)
        button_overlay_layout.setContentsMargins(0, 0, 0, 8)
        button_overlay_layout.setSpacing(12)
        button_overlay_layout.addStretch()
        
        self.btn_rotate_left = QPushButton()
        self.btn_rotate_right = QPushButton()
        self.btn_rotate_left.setAttribute(Qt.WA_TranslucentBackground, False)
        self.btn_rotate_right.setAttribute(Qt.WA_TranslucentBackground, False)
        self.btn_rotate_left.setAutoFillBackground(True)
        self.btn_rotate_right.setAutoFillBackground(True)
        # Use system theme rotation icons with fallbacks to undo/redo
        self.btn_rotate_left.setIcon(QIcon.fromTheme("object-rotate-left", QIcon.fromTheme("edit-undo")))
        self.btn_rotate_right.setIcon(QIcon.fromTheme("object-rotate-right", QIcon.fromTheme("edit-redo")))
        self.btn_rotate_left.setIconSize(QSize(24, 24))
        self.btn_rotate_right.setIconSize(QSize(24, 24))
        self.btn_rotate_left.setMinimumSize(44, 44)
        self.btn_rotate_right.setMinimumSize(44, 44)
        self.btn_rotate_left.setMaximumSize(44, 44)
        self.btn_rotate_right.setMaximumSize(44, 44)
        self.btn_rotate_left.setToolTip("Rotate Left")
        self.btn_rotate_right.setToolTip("Rotate Right")
        self.btn_rotate_left.clicked.connect(self.rotate_left)
        self.btn_rotate_right.clicked.connect(self.rotate_right)
        button_overlay_layout.addWidget(self.btn_rotate_left)
        button_overlay_layout.addWidget(self.btn_rotate_right)
        button_overlay_layout.addStretch()
        
        # Use resizeEvent to position elements properly
        def reposition_overlay():
            if image_widget.width() > 0 and image_widget.height() > 0:
                self.image_label.setGeometry(0, 0, image_widget.width(), image_widget.height())
                button_overlay.setGeometry(0, image_widget.height() - 60, image_widget.width(), 60)
                button_overlay.raise_()
        
        # Connect resize event
        image_widget.resizeEvent = lambda event: (reposition_overlay(), QWidget.resizeEvent(image_widget, event))

        center_splitter.addWidget(image_widget)
        # Initial positioning
        QTimer.singleShot(100, reposition_overlay)

        # --- Tag Input Pane with persistent rounded corners and matching width ---
        iptc_input_container = QWidget()
        iptc_input_container.setContentsMargins(0,0,0,0)
        iptc_input_container.setObjectName("IptcInputContainer")
        iptc_input_container.setStyleSheet(style_iptc_input_container)
        iptc_layout = QVBoxLayout(iptc_input_container)
        iptc_layout.setContentsMargins(8, 8, 8, 18)
        iptc_layout.setSpacing(8)
        
        # Top part: Read-only display of existing tags (clickable)
        self.tag_display_list = QListWidget()
        self.tag_display_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.tag_display_list.setFocusPolicy(Qt.NoFocus)
        self.tag_display_list.setSpacing(3)
        self.tag_display_list.setViewportMargins(0, 0, 12, 0)
        self.tag_display_list.setStyleSheet(style_tag_display_list)
        iptc_layout.addWidget(self.tag_display_list)
        
        # Bottom part: Single-line input field for editing
        self.iptc_text_edit = QLineEdit()
        self.iptc_text_edit.setPlaceholderText("Add new tag")
        self.iptc_text_edit.setMinimumHeight(50)
        
        # Set up autocomplete for tags - use custom implementation for stability
        self.tag_completer_model = QStringListModel()
        self.tag_suggestions_list = QListWidget(self)  # Child of main window
        self.tag_suggestions_list.setWindowFlags(Qt.SubWindow)
        self.tag_suggestions_list.setFocusPolicy(Qt.NoFocus)
        self.tag_suggestions_list.setFocusProxy(None)
        self.tag_suggestions_list.resize(500, 300)  # Increased width to 500 to avoid clipping
        self.tag_suggestions_list.setMinimumSize(500, 300)
        self.tag_suggestions_list.setMouseTracking(True)
        self.tag_suggestions_list.setAttribute(Qt.WA_ShowWithoutActivating)
        self.tag_suggestions_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tag_suggestions_list.setStyleSheet(style_tag_suggestions_list)
        self.tag_suggestions_list.itemClicked.connect(self.on_suggestion_clicked)
        self.tag_suggestions_list.hide()
        
        # Install event filter to handle Ctrl+Space for autocomplete
        self.iptc_text_edit.installEventFilter(self)
        
        # Track which tag is being edited
        self.editing_tag_index = None
        
        iptc_layout.addWidget(self.iptc_text_edit)
        
        # Ensure the container expands horizontally to match the image preview
        iptc_input_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        iptc_input_container.setMinimumHeight(150)
        center_splitter.addWidget(iptc_input_container)
        
        # Make tag input section collapsible
        center_splitter.setCollapsible(0, False)  # Image preview cannot be collapsed
        center_splitter.setCollapsible(1, False)  # Tag input cannot be collapsed
        center_splitter.setChildrenCollapsible(True)
        
        center_splitter.setSizes([600, 320])  # image, tag_input_with_button
        self.iptc_text_edit.textChanged.connect(self.on_tag_input_text_changed)
        self.iptc_text_edit.returnPressed.connect(self.on_tag_input_return_pressed)
        # --- end tag input pane wrap ---

        main_splitter.addWidget(center_splitter)

        # RIGHT PANEL: tags list (not split)
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(8, 8, 8, 8)

        # Add tag search bar before anything that uses it
        self.tags_search_bar = QLineEdit()
        self.tags_search_bar.setMinimumHeight(50)
        self.tags_search_bar.setPlaceholderText(TAG_SEARCH_PLACEHOLDER)
        self.tags_search_bar.textChanged.connect(self.update_tags_search)
        right_panel.addWidget(self.tags_search_bar)

        # Create tags_list_widget for displaying available tags
        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setStyleSheet(style_tags_list_widget)
        self.tags_list_widget.setWordWrap(True)
        self.tags_list_widget.setSpacing(10)
        self.tags_list_widget.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.tags_list_widget.setViewportMargins(0, 0, 0, 0)
        right_panel.addWidget(self.tags_list_widget)

        right_panel_widget = QWidget()
        right_panel_widget.setContentsMargins(0, 0, 0, 0)  # Add margin (left, top, right, bottom)
        right_panel_widget.setLayout(right_panel)
        main_splitter.addWidget(right_panel_widget)
        
        # Hide the right panel - using autocomplete instead
        right_panel_widget.setVisible(False)

        apply_default_font(
            [
                self.btn_select_folder,
                self.btn_scan_directory,
                self.metadata_format_dropdown,
                self.metadata_type_dropdown,
                self.scan_status_label,
                self.list_view,
                self.btn_prev,
                self.btn_next,
                self.page_label,
                self.image_label,
                self.btn_rotate_left,
                self.btn_rotate_right,
                self.tag_display_list,
                self.tags_list_widget,
            ]
        )

        # Add the splitter to the outer layout
        outer_layout.addWidget(main_splitter)
        outer_layout.addWidget(bottom_spacer)
        # === END: All widgets are now inside outer_container ===

        # Set the outer_container as the only child of the central widget
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(outer_container)
        central_widget.setLayout(central_layout)

        self._preview_rotation_angle = 0
        self._preview_image_cache = None

        # Make search input font match tag input
        search_font = QFont()
        search_font.setPointSize(FONT_SIZE_TAG_INPUT)
        self.search_bar.setFont(search_font)
        self.tags_search_bar.setFont(search_font)
        self.search_bar.setStyleSheet(style_search_bar)
        self.tags_search_bar.setStyleSheet(style_tags_search_bar)
        # Only increase font size for the tag input pane
        tag_input_font = QFont()
        tag_input_font.setPointSize(FONT_SIZE_TAG_INPUT)
        self.iptc_text_edit.setFont(tag_input_font)
        self.iptc_text_edit.setStyleSheet(style_iptc_text_edit)
        # Style QComboBox (iptc_tag_dropdown) for rounded corners
        # Dropdown stylesheets now applied immediately after creation (lines ~1260 and ~1290)

        apply_button_style(
            [
                self.btn_select_folder,
                self.btn_scan_directory,
                self.btn_prev,
                self.btn_next,
                self.btn_rotate_left,
                self.btn_rotate_right,
            ]
        )

        # Apply wide scrollbar to list_view
        self.list_view.setStyleSheet(self.list_view.styleSheet() + scrollbar_style_wide)

    def rotate_left(self):
        if self.current_image_path:
            self._preview_rotation_angle = (self._preview_rotation_angle - 90) % 360
            self._apply_rotation()

    def rotate_right(self):
        if self.current_image_path:
            self._preview_rotation_angle = (self._preview_rotation_angle + 90) % 360
            self._apply_rotation()

    def on_preview_image_clicked(self, event):
        """Open full-size image in a new window when preview is clicked"""
        if not self.current_image_path or not os.path.exists(self.current_image_path):
            return
        
        # Create a new top-level window
        full_image_window = QDialog(self)
        full_image_window.setWindowTitle(os.path.basename(self.current_image_path))
        full_image_window.setModal(False)
        full_image_window.resize(1200, 900)
        
        # Create layout
        layout = QVBoxLayout(full_image_window)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area for large images
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        # Create label for the image
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        
        # Load the full-size image with rotation applied
        pixmap = QPixmap(self.current_image_path)
        if not pixmap.isNull():
            # Apply the same rotation as preview
            if self._preview_rotation_angle != 0:
                transform = QTransform().rotate(self._preview_rotation_angle)
                pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
            image_label.setPixmap(pixmap)
        
        scroll_area.setWidget(image_label)
        layout.addWidget(scroll_area)
        
        full_image_window.show()

    def update_pagination(self):
        start = time.perf_counter()
        total_images = 0
        # Use the database to get the count of images in the current folder (with search tags)
        if not self.folder_path:
            self.current_page = 0
            self.total_pages = 1
            self.image_list = []
        else:
            text = self.search_bar.toPlainText().strip()
            tags = [t.strip() for t in re.split(r",|\s", text) if t.strip()]
            metadata_type, tag_name = self.get_current_tag_and_type()
            tag_type = tag_name
            if not tags:
                if tag_type:
                    # Count images WITHOUT any tags of this type
                    total_images = self.db.get_untagged_image_count_of_type_in_folder(
                        self.folder_path, tag_type
                    )
                else:
                    total_images = self.db.get_untagged_image_count_in_folder(
                        self.folder_path
                    )
            else:
                total_images = self.db.get_image_count_in_folder(
                    self.folder_path, tags, tag_type
                )
            self.total_pages = (
                (total_images - 1) // self.page_size + 1 if total_images > 0 else 1
            )
            if self.current_page >= self.total_pages:
                self.current_page = self.total_pages - 1
            if self.current_page < 0:
                self.current_page = 0
        elapsed = time.perf_counter() - start
        query_text = self.search_bar.toPlainText().strip() if self.folder_path else ""
        self._log_search_event(
            f"Pagination updated: total_images={total_images} page={self.current_page + 1}/{self.total_pages} tags_mode={'yes' if query_text else 'no'} in {elapsed:.3f}s"
        )
        self.page_label.setText(f"Page {self.current_page + 1} / {self.total_pages}")
        self.page_label.setStyleSheet(self.style_page_label)
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < self.total_pages - 1)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_current_page()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.show_current_page()

    def show_current_page(self):
        page_start = time.perf_counter()
        # Use the database to get the images for the current page
        if not self.folder_path:
            self.image_list = []
            model = QStandardItemModel()
            self.list_view.setModel(model)
            self.update_pagination()
            self._log_search_event("show_current_page skipped (no folder)")
            return
        text = self.search_bar.toPlainText().strip()
        tags = [t.strip() for t in re.split(r",|\s", text) if t.strip()]
        metadata_type, tag_name = self.get_current_tag_and_type()
        tag_type = tag_name
        query_start = time.perf_counter()
        if not tags:
            # No search terms - show images based on tag type selection
            if tag_type:
                # Show images WITHOUT any tags of this type
                page_items = self.db.get_untagged_images_of_type_in_folder_paginated(
                    self.folder_path, self.current_page, self.page_size, tag_type
                )
            else:
                # Show all images without any tags
                page_items = self.db.get_untagged_images_in_folder_paginated(
                    self.folder_path, self.current_page, self.page_size
                )
        else:
            # Search terms provided - filter by those terms (and optionally tag type)
            page_items = self.db.get_images_in_folder_paginated(
                self.folder_path, self.current_page, self.page_size, tags, tag_type
            )
        query_elapsed = time.perf_counter() - query_start
        self._log_search_event(
            f"Page query fetched {len(page_items)} items in {query_elapsed:.3f}s (page={self.current_page + 1}, tags_mode={'yes' if tags else 'no'}, tag_type={tag_type or 'ALL'})"
        )
        self.cancel_thumbnail_worker()
        self.image_list = page_items  # Store full paths, not just basenames
        build_start = time.perf_counter()
        self.list_view.setUpdatesEnabled(False)
        try:
            model = QStandardItemModel()
            supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif")
            thumbnail_tasks = []
            placeholder_icon = QIcon()
            for fpath in page_items:
                if not fpath.lower().endswith(supported):
                    continue
                row_index = model.rowCount()
                item = QStandardItem()
                item.setEditable(False)
                item.setText("")
                item.setSizeHint(QSize(175, 175))
                item.setData(fpath, Qt.UserRole + 1)  # Store full path
                item.setIcon(placeholder_icon)
                model.appendRow(item)
                thumbnail_tasks.append((row_index, fpath))
            self.list_view.setModel(model)
        finally:
            self.list_view.setUpdatesEnabled(True)
        self.update_pagination()
        build_elapsed = time.perf_counter() - build_start
        total_elapsed = time.perf_counter() - page_start
        self._log_search_event(
            f"Model built with {model.rowCount()} rows in {build_elapsed:.3f}s; total show_current_page={total_elapsed:.3f}s"
        )
        if thumbnail_tasks:
            self.start_thumbnail_worker(thumbnail_tasks)

    def start_thumbnail_worker(self, tasks):
        # Cancel old worker (requests interruption but doesn't wait)
        self.cancel_thumbnail_worker()
        
        # Increment generation ID to invalidate old workers
        current_gen = self._thumbnail_generation_id
        
        if not tasks:
            return
        
        self._log_search_event(f"Starting thumbnail worker gen={current_gen} for {len(tasks)} items")
        worker = ThumbnailBatchWorker(tasks, generation_id=current_gen)
        worker.thumbnail_ready.connect(
            lambda row, path, thumb, gen=current_gen: self.on_thumbnail_ready(row, path, thumb, gen)
        )
        worker.finished.connect(lambda w=worker: self.on_thumbnail_worker_finished(w))
        
        self.thumbnail_worker = worker
        self._active_thumbnail_workers.add(worker)
        worker.start()

    def on_thumbnail_ready(self, row_index, image_path, thumb_path, generation_id):
        # Ignore thumbnails from old workers
        if generation_id != self._thumbnail_generation_id:
            return
        
        model = self.list_view.model()
        if model is None:
            return
        item = model.item(row_index)
        if item is None:
            return
        current_path = item.data(Qt.UserRole + 1)
        if current_path != image_path:
            return
        pixmap = QPixmap(thumb_path) if os.path.exists(thumb_path) else QPixmap(image_path)
        if pixmap.isNull():
            return
        icon = QIcon(
            pixmap.scaled(
                self.list_view.iconSize(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        item.setIcon(icon)

    def show_image_filename_context_menu(self, pos):
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return
        model = self.list_view.model()
        item = model.itemFromIndex(index)
        fpath = item.data(Qt.UserRole + 1)
        if fpath:
            self.show_custom_popup("Filename", os.path.basename(fpath))
        self.list_view.clearFocus()

    def show_scan_status(self, message):
        if not message:
            self.clear_scan_status()
            return
        self._scan_status_clear_timer.stop()
        self.scan_status_label.setText(message)
        self.scan_status_label.setVisible(True)

    def clear_scan_status(self):
        self._scan_status_clear_timer.stop()
        self.scan_status_label.clear()
        self.scan_status_label.setVisible(False)

    def cancel_active_scan(self):
        if hasattr(self, "worker") and self.worker:
            self.worker.requestInterruption()
            if self.worker.isRunning():
                self.worker.wait()
            self.worker = None
        self._active_scan_folder = None
        self._scan_refresh_timer.stop()
        self._scan_status_clear_timer.stop()

    def cancel_preview_worker(self, wait=False):
        for worker in list(self._active_preview_workers):
            worker.requestInterruption()
            if wait:
                worker.wait()
                self._on_preview_worker_finished(worker)
        self.preview_worker = None
        self._pending_preview_key = None

    def cancel_metadata_worker(self, wait=False):
        for worker in list(self._active_metadata_workers):
            worker.requestInterruption()
            self._metadata_timers.pop((worker.image_path, worker.tag_type), None)
            if wait:
                worker.wait()
                self._on_metadata_worker_finished(worker)
        if self._metadata_pending_key:
            self._metadata_timers.pop(self._metadata_pending_key, None)
            self._metadata_pending_key = None
        if wait:
            self.metadata_worker = None

    def cancel_thumbnail_worker(self, wait=False):
        # Request interruption on old worker so it exits early
        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.requestInterruption()
            if wait:
                # Wait for the thread to finish before destroying it
                self.thumbnail_worker.wait(2000)  # Wait up to 2 seconds
            else:
                # Even for non-wait cases, give it a brief moment to stop gracefully
                self.thumbnail_worker.wait(100)  # Wait up to 100ms
        
        # Increment generation ID to ignore results from old workers
        self._thumbnail_generation_id += 1
        self.thumbnail_worker = None

    def _on_preview_worker_finished(self, worker):
        if worker in self._active_preview_workers:
            self._active_preview_workers.discard(worker)
            worker.deleteLater()
        if worker is self.preview_worker:
            self.preview_worker = None

    def _on_metadata_worker_finished(self, worker):
        if worker in self._active_metadata_workers:
            self._active_metadata_workers.discard(worker)
            worker.deleteLater()
        if worker is self.metadata_worker:
            self.metadata_worker = None

    def on_thumbnail_worker_finished(self, worker):
        if worker in self._active_thumbnail_workers:
            self._active_thumbnail_workers.discard(worker)
            worker.deleteLater()
        if worker is self.thumbnail_worker:
            self.thumbnail_worker = None
        self._log_search_event("Thumbnail worker finished")

    def start_directory_scan(self, folder_path, remove_missing=False):
        if not folder_path:
            return
        self.cancel_active_scan()
        self.cancel_preview_worker()
        self.cancel_thumbnail_worker()
        if remove_missing:
            self.db.remove_missing_images(folder_path)
        self._active_scan_folder = folder_path
        self._scan_refresh_timer.stop()
        worker = ScanWorker(folder_path, self.db.db_path)
        worker.batch_ready.connect(self.on_scan_batch_ready)
        worker.scan_progress.connect(self.on_scan_progress)
        worker.scan_finished.connect(self.on_scan_finished)
        self.worker = worker
        worker.start()

    def on_scan_progress(self, folder_path, processed):
        if folder_path != self.folder_path:
            return
        if processed:
            status = f"Scanning directory… Indexed {processed} images"
        else:
            status = "Scanning directory…"
        self.show_scan_status(status)

    def on_scan_batch_ready(self, folder_path, processed):
        if folder_path != self.folder_path:
            return
        delay = 0 if processed <= self.page_size else 200
        self._scan_refresh_timer.start(delay)

    def _desired_preview_edge(self):
        label_width = max(self.image_label.width(), 600)
        label_height = max(self.image_label.height(), 400)
        edge = max(label_width, label_height, 1024)
        return min(max(edge, 512), DEFAULT_PREVIEW_MAX_EDGE)

    def start_preview_loading(self, image_path, retry=False):
        if not image_path:
            return
        if not retry:
            self._preview_retry_counts[image_path] = 0
            self._preview_timers[image_path] = time.perf_counter()
        self._log_preview_event(f"Requesting preview for {image_path}; retry={retry}")
        self.cancel_preview_worker()
        self._preview_image_cache = None
        edge = self._desired_preview_edge()
        self._pending_preview_key = (image_path, edge)
        preview_path = _preview_cache_path(image_path, edge)
        if os.path.exists(preview_path) and _preview_is_current(image_path, preview_path):
            load_start = time.perf_counter()
            pixmap = QPixmap(preview_path)
            load_elapsed = time.perf_counter() - load_start
            self._log_preview_event(
                f"Cached preview load via Qt for {image_path} ({preview_path}) took {load_elapsed:.2f}s"
            )
            if not pixmap.isNull():
                self._preview_image_cache = pixmap
                self._pending_preview_key = None
                self._log_preview_event(
                    self._format_duration_message(
                        image_path, "Cached preview ready; applying rotation"
                    )
                )
                self._apply_rotation()
                return
            self._log_preview_event(f"Cached preview unreadable: {preview_path}")
        self.image_label.setText("Loading preview…")
        self._log_preview_event(
            f"Starting preview worker for {image_path} (edge={edge})"
        )
        worker = PreviewWorker(image_path, edge)
        worker.preview_ready.connect(self.on_preview_ready)
        worker.preview_failed.connect(self.on_preview_failed)
        worker.finished.connect(lambda: self._on_preview_worker_finished(worker))
        self.preview_worker = worker
        self._active_preview_workers.add(worker)
        worker.start()

    def on_preview_ready(self, image_path, preview_path, edge_length):
        if image_path != self.current_image_path:
            return
        if self._pending_preview_key != (image_path, edge_length):
            return
        self._log_preview_event(
            f"Preview ready for {image_path}; file={preview_path} edge={edge_length}"
        )
        pixmap = QPixmap(preview_path)
        if pixmap.isNull():
            self._log_preview_event(
                f"Qt decode failed for preview {preview_path}; trying Pillow"
            )
            pixmap = self._load_preview_pixmap(preview_path)
        if pixmap is None or pixmap.isNull():
            self._log_preview_event(
                f"Preview decode failed for {image_path}; attempt {self._preview_retry_counts.get(image_path, 0)}"
            )
            attempts = self._preview_retry_counts.get(image_path, 0)
            if attempts < 1:
                self._preview_retry_counts[image_path] = attempts + 1
                try:
                    os.remove(preview_path)
                except OSError:
                    pass
                self._pending_preview_key = None
                self._log_preview_event(
                    f"Deleted cached preview {preview_path}; retrying generation"
                )
                self.start_preview_loading(image_path, retry=True)
                return
            self._preview_retry_counts.pop(image_path, None)
            self._log_preview_event(
                self._format_duration_message(
                    image_path, "Preview decode permanently failed; using full image"
                )
            )
            self._pending_preview_key = None
            self._display_full_image_fallback(image_path)
            return
        self._pending_preview_key = None
        self._preview_retry_counts.pop(image_path, None)
        self._preview_image_cache = pixmap
        self._log_preview_event(
            self._format_duration_message(image_path, "Preview cached; applying rotation")
        )
        self._apply_rotation()

    def on_preview_failed(self, image_path, error_message, edge_length):
        if image_path != self.current_image_path:
            return
        if self._pending_preview_key != (image_path, edge_length):
            return
        self._pending_preview_key = None
        self._preview_retry_counts.pop(image_path, None)
        if error_message:
            self._log_preview_event(
                self._format_duration_message(
                    image_path, f"Preview worker failed: {error_message}"
                ),
                level="warning",
            )
        self._display_full_image_fallback(image_path)

    def _prepare_metadata_ui_loading(self):
        self.cleaned_keywords = []
        self.last_loaded_keywords = ""
        self.iptc_text_edit.blockSignals(True)
        self.iptc_text_edit.clear()
        self.iptc_text_edit.blockSignals(False)
        self.iptc_text_edit.setPlaceholderText("Loading IPTC tags…")
        self.iptc_text_edit.setEnabled(False)

    def start_metadata_loading(self, image_path):
        if not image_path:
            return
        metadata_type, tag_type = self.get_current_tag_and_type()
        self.cancel_metadata_worker()
        key = (image_path, tag_type)
        self._metadata_pending_key = key
        self._metadata_timers[key] = time.perf_counter()
        self._log_metadata_event(
            f"Starting metadata worker for {image_path}; type={metadata_type} tag={tag_type}"
        )
        worker = MetadataWorker(image_path, tag_type, metadata_type)
        worker.metadata_ready.connect(self.on_metadata_ready)
        worker.metadata_failed.connect(self.on_metadata_failed)
        worker.finished.connect(lambda: self._on_metadata_worker_finished(worker))
        self.metadata_worker = worker
        self._active_metadata_workers.add(worker)
        worker.start()

    def on_metadata_ready(self, image_path, tag_type, tags):
        start_time = self._metadata_timers.pop((image_path, tag_type), None)
        elapsed = (
            time.perf_counter() - start_time if start_time is not None else None
        )
        current_metadata_type, current_tag_type = self.get_current_tag_and_type()
        if (
            image_path != self.current_image_path
            or tag_type != current_tag_type
        ):
            self._log_metadata_event(
                f"Discarding metadata for stale request image={image_path} tag={tag_type}",
                level="warning",
            )
            if self._metadata_pending_key == (image_path, tag_type):
                self._metadata_pending_key = None
            return
        message = (
            f"{image_path} ({elapsed:.2f}s) - Metadata loaded"
            if elapsed is not None
            else f"{image_path} - Metadata loaded"
        )
        self._log_metadata_event(message)
        self.cleaned_keywords = tags
        self.last_loaded_keywords = "\n".join(tags)
        
        # Sync database with actual file metadata to prevent stale data
        try:
            self.db.set_image_tags(image_path, tags, tag_type)
            self.db.conn.commit()
        except Exception as e:
            self._log_metadata_event(f"Failed to sync DB with metadata: {e}", level="warning")
        
        self.iptc_text_edit.setPlaceholderText("Add new tag")
        self.iptc_text_edit.setEnabled(True)
        if tags:
            self.set_tag_input_html(tags)
        else:
            self.set_tag_input_html([])
        if self._metadata_pending_key == (image_path, tag_type):
            self._metadata_pending_key = None

    def on_metadata_failed(self, image_path, tag_type, error_message):
        start_time = self._metadata_timers.pop((image_path, tag_type), None)
        elapsed = (
            time.perf_counter() - start_time if start_time is not None else None
        )
        current_metadata_type, current_tag_type = self.get_current_tag_and_type()
        if (
            image_path != self.current_image_path
            or tag_type != current_tag_type
        ):
            if self._metadata_pending_key == (image_path, tag_type):
                self._metadata_pending_key = None
            return
        message = (
            f"{image_path} ({elapsed:.2f}s) - Metadata load failed: {error_message}"
            if elapsed is not None
            else f"{image_path} - Metadata load failed: {error_message}"
        )
        self._log_metadata_event(message, level="warning")
        self.cleaned_keywords = []
        self.last_loaded_keywords = ""
        self.set_tag_input_html([])
        self.iptc_text_edit.setPlaceholderText(f"Unable to load {current_metadata_type.upper()} tags.")
        self.iptc_text_edit.setEnabled(True)
        if self._metadata_pending_key == (image_path, tag_type):
            self._metadata_pending_key = None

    def _load_preview_pixmap(self, path):
        """Load a cached preview using Pillow when Qt lacks a JPEG plugin."""
        try:
            from PIL.ImageQt import ImageQt

            with Image.open(path) as pil_img:
                if hasattr(pil_img, "n_frames") and pil_img.n_frames > 1:
                    pil_img.seek(0)
                pil_img = ImageOps.exif_transpose(pil_img)
                if pil_img.mode not in ("RGB", "RGBA"):
                    pil_img = pil_img.convert("RGB")
                qt_image = ImageQt(pil_img)
            pixmap = QPixmap.fromImage(qt_image)
            return pixmap if not pixmap.isNull() else None
        except Exception as exc:
            self._log_preview_event(
                f"Preview Pillow decode failed for {path}: {exc}", level="warning"
            )
            return None

    def _log_event(self, category, message, level="info"):
        """Unified logging method for all event types (Preview, Metadata, Selection, Search, Save)."""
        prefix = f"[{category}]"
        if level == "warning":
            print(f"{prefix} WARNING: {message}")
        else:
            print(f"{prefix} {message}")
        if getattr(self, "_preview_log_path", None):
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self._preview_log_path, "a", encoding="utf-8") as log_file:
                    log_file.write(f"{timestamp} {prefix} {level.upper()}: {message}\n")
            except OSError:
                self._preview_log_path = None

    # Convenience wrappers for backward compatibility
    def _log_preview_event(self, message, level="info"):
        self._log_event("Preview", message, level)

    def _log_metadata_event(self, message, level="info"):
        self._log_event("Metadata", message, level)

    def _log_selection_event(self, message, level="info"):
        self._log_event("Selection", message, level)

    def _log_search_event(self, message, level="info"):
        self._log_event("Search", message, level)

    def _log_save_event(self, message, level="info"):
        self._log_event("Save", message, level)

    def _format_duration_message(self, image_path, message):
        start = self._preview_timers.pop(image_path, None)
        if start is None:
            return f"{image_path} - {message}"
        elapsed = time.perf_counter() - start
        return f"{image_path} ({elapsed:.2f}s) - {message}"

    def _init_preview_log(self):
        try:
            log_dir = os.path.join(os.path.dirname(self.db.db_path), "logs")
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, "preview.log")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "a", encoding="utf-8") as log_file:
                log_file.write(f"\n=== Session start {timestamp} ===\n")
            return path
        except OSError:
            return None

    def _display_full_image_fallback(self, image_path):
        fallback_start = time.perf_counter()
        self._log_preview_event(
            f"{image_path} - starting full-image fallback load", level="warning"
        )
        try:
            pixmap = self._load_full_pixmap(image_path)
        except Exception as exc:
            self.show_custom_popup("Error", f"Could not open image: {exc}")
            return
        self._preview_image_cache = pixmap
        elapsed = time.perf_counter() - fallback_start
        self._log_preview_event(
            f"{image_path} ({elapsed:.2f}s) - full-image fallback ready", level="warning"
        )
        self._apply_rotation()

    def _load_full_pixmap(self, path):
        """Load full resolution pixmap, using PIL for large/special format files."""
        FILESIZE_THRESHOLD = 25 * 1024 * 1024  # 25MB
        file_size = os.path.getsize(path)
        ext = os.path.splitext(path)[1].lower()
        if file_size > FILESIZE_THRESHOLD or ext in [".tif", ".tiff", ".heic", ".heif"]:
            import io
            with Image.open(path) as pil_img:
                if hasattr(pil_img, "n_frames") and pil_img.n_frames > 1:
                    pil_img.seek(0)
                pil_img = ImageOps.exif_transpose(pil_img)
                max_dim = max(self.image_label.width(), self.image_label.height(), 2000)
                pil_img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
        else:
            pixmap = QPixmap(path)
        if pixmap.isNull():
            raise ValueError("Unable to decode image")
        return pixmap

    def _apply_rotation(self):
        """Apply current rotation angle to cached preview image."""
        if not getattr(self, "_preview_image_cache", None):
            return
        pixmap = self._preview_image_cache
        if getattr(self, "_preview_rotation_angle", 0):
            transform = QTransform().rotate(self._preview_rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self._render_pixmap_to_label(pixmap)

    def _render_pixmap_to_label(self, pixmap):
        """Scale pixmap to fit label with rounded corners and shadow effect."""
        if pixmap.isNull():
            return
        label_width = max(self.image_label.width(), 1)
        label_height = max(self.image_label.height(), 1)
        margin = 16
        max_img_width = max(1, label_width - 2 * margin)
        max_img_height = max(1, label_height - 2 * margin)
        scaled_pixmap = pixmap.scaled(
            max_img_width,
            max_img_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        final_pixmap = QPixmap(label_width, label_height)
        final_pixmap.fill(Qt.transparent)
        painter = QPainter(final_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = self.corner_radius
        path = QPainterPath()
        path.addRoundedRect(1, 1, label_width - 2, label_height - 2, radius, radius)
        painter.fillPath(path, self.palette().color(QPalette.Base))
        pen = QPen(self.palette().color(QPalette.Mid))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        x = (label_width - scaled_pixmap.width()) // 2
        y = (label_height - scaled_pixmap.height()) // 2
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()
        self.image_label.setPixmap(final_pixmap)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        self.cancel_active_scan()
        self.cancel_preview_worker()
        self.cancel_thumbnail_worker()
        self.folder_path = folder
        self.current_page = 0
        self.image_list = []
        self._scan_refresh_timer.stop()
        self.list_view.setModel(QStandardItemModel())
        self.update_pagination()
        if not self.db.was_directory_scanned(folder):
            self.show_scan_status("Scanning directory…")
            self.start_directory_scan(folder)
        else:
            self.clear_scan_status()
            self.show_current_page()

    def on_scan_finished(self, folder_path, completed):
        if folder_path != self.folder_path:
            if completed:
                self.db.mark_directory_scanned(folder_path)
            return
        self.worker = None
        self._active_scan_folder = None
        self._scan_refresh_timer.stop()
        if completed:
            self.db.mark_directory_scanned(folder_path)
            self.remove_unused_tags_from_db()
            self.db.purge_cache_images()
            self.show_scan_status("Scan complete.")
        else:
            self.show_scan_status("Scan cancelled.")
        self._scan_status_clear_timer.start(1500)
        self.load_previous_tags()
        self.update_search()
        self.update_tags_search()
        self.show_current_page()

    def save_tags_to_file_and_db(self, show_dialogs=False):
        if not self.current_image_path:
            return True
        # Get tags from display list
        keywords = [self.tag_display_list.item(i).text() 
                   for i in range(self.tag_display_list.count())]
        raw_input = "\n".join(keywords)
        tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
        multi_valued = (
            self.selected_iptc_tag.get("multi_valued", False)
            if self.selected_iptc_tag
            else False
        )
        invalid_tags = [kw for kw in keywords if not self.is_valid_tag(kw)]
        try:
            meta = Exiv2Bind(self.current_image_path)
            meta.from_dict({"iptc": {tag_type: []}})
        except Exception as e:
            if show_dialogs:
                self.show_custom_popup(
                    "exiv2 Error", f"Failed to delete IPTC tag {tag_type}:\n{e}"
                )
        if not raw_input:
            self.db.set_image_tags(self.current_image_path, [], tag_type)
            return True
        if invalid_tags:
            if show_dialogs:
                self.show_custom_popup(
                    "Invalid Tag(s)",
                    f"Invalid tag(s) found: {', '.join(invalid_tags)}. Tags must be alphanumeric or dashes only.",
                )
            return False
        try:
            if multi_valued:
                meta.from_dict({"iptc": {tag_type: keywords}})
                self.db.set_image_tags(self.current_image_path, keywords, tag_type)
            else:
                # For single-valued tags, only use the last value entered
                single_value = keywords[-1] if keywords else ""
                meta.from_dict({"iptc": {tag_type: [single_value]}})
                self.db.set_image_tags(
                    self.current_image_path,
                    [single_value] if single_value else [],
                    tag_type,
                )
        except Exception as e:
            if show_dialogs:
                self.show_custom_popup(
                    "exiv2 Error", f"Failed to write IPTC tag {tag_type}:\n{e}"
                )
            return True

    def remove_unused_tags_from_db(self):
        c = self.db.conn.cursor()
        # Remove tag-image associations for tags not present in any image
        c.execute(
            """
            DELETE FROM tags WHERE id NOT IN (
                SELECT tag_id FROM image_tags
            )
        """
        )
        self.db.conn.commit()

    def handle_unsaved_changes(self):
        # Get current tags from display list
        current_tags = [self.tag_display_list.item(i).text() 
                       for i in range(self.tag_display_list.count())]
        current_input = "\n".join(current_tags)
        
        if (
            hasattr(self, "last_loaded_keywords")
            and self.current_image_path is not None
            and current_input != self.last_loaded_keywords
        ):
            result = self.show_custom_confirm(
                "Save Changes?",
                "You have unsaved changes to the tags. Save before switching?",
                yes_text="Yes",
                no_text="No",
                cancel_text="Cancel",
            )
            if result == "cancel":
                return False
            elif result == "yes":
                save_result = self.save_tags_to_file_and_db(show_dialogs=True)
                if save_result is False:
                    return False
                return True
            elif result == "no":
                return True
        return True

    def image_selected(self, index):
        selection_start = time.perf_counter()
        last_checkpoint = selection_start

        def log_step(label, level="info", path_hint=None):
            nonlocal last_checkpoint
            now = time.perf_counter()
            delta = now - last_checkpoint
            total = now - selection_start
            path_value = (
                path_hint
                if path_hint is not None
                else getattr(self, "current_image_path", None) or "N/A"
            )
            self._log_selection_event(
                f"{path_value} - {label} (+{delta:.3f}s / {total:.3f}s)",
                level=level,
            )
            last_checkpoint = now

        selected_index = index.row()
        self._log_selection_event(
            f"Row {selected_index} selected; image count={len(self.image_list)}"
        )
        save_result = self.handle_save_events()
        if not save_result:
            log_step("Selection blocked by unsaved changes", level="warning", path_hint="N/A")
            return  # Don't switch images
        # If tags were saved, refresh the thumbnail view to update visibility
        if save_result == "saved":
            self.show_current_page()
        log_step("Unsaved-change check complete", path_hint="N/A")
        if selected_index < 0 or selected_index >= len(self.image_list):
            log_step("Selection index out of range", level="warning", path_hint="N/A")
            return
        # Always get the image path after handle_unsaved_changes
        image_path = self.image_list[selected_index]
        log_step("Resolved image path", path_hint=image_path)
        self.current_image_path = image_path
        self._preview_rotation_angle = 0
        self.display_image(self.current_image_path)
        log_step("Preview request queued", path_hint=image_path)
        self._prepare_metadata_ui_loading()
        log_step("Metadata UI prepared", path_hint=image_path)
        self.start_metadata_loading(self.current_image_path)
        log_step("Metadata worker started", path_hint=image_path)
        self.load_previous_tags()
        log_step("Previous tags loaded", path_hint=image_path)
        log_step("Selection handling complete", path_hint=image_path)

    def display_image(self, path):
        self.start_preview_loading(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Always redraw the image and border at the new size to avoid artifacts
        if self.current_image_path:
            if getattr(self, "_preview_image_cache", None):
                self._apply_rotation()
            else:
                self.display_image(self.current_image_path)
        else:
            # Draw empty preview with border
            label_width = self.image_label.width()
            label_height = self.image_label.height()
            final_pixmap = QPixmap(label_width, label_height)
            final_pixmap.fill(Qt.transparent)
            painter = QPainter(final_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            radius = self.corner_radius
            path = QPainterPath()
            path.addRoundedRect(1, 1, label_width - 2, label_height - 2, radius, radius)
            painter.fillPath(path, self.palette().color(QPalette.Base))
            pen = QPen(self.palette().color(QPalette.Mid))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            painter.end()
            self.image_label.setPixmap(final_pixmap)

    def eventFilter(self, obj, event):
        """Handle keyboard events for autocomplete trigger."""
        if obj == self.iptc_text_edit and event.type() == event.Type.KeyPress:
            # Ctrl+Space triggers autocomplete
            if event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
                current_text = self.iptc_text_edit.text().strip()
                # Only trigger if there's some text
                if current_text and len(current_text) >= 1:
                    self.update_tag_completer()
                return True  # Event handled
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self.cancel_preview_worker(wait=True)
        self.cancel_metadata_worker(wait=True)
        self.cancel_thumbnail_worker(wait=True)
        self.cancel_active_scan()
        super().closeEvent(event)

    def load_previous_tags(self):
        # Load unique tags for the selected tag type from the SQLite database and populate the list widget.
        metadata_type, tag_type = self.get_current_tag_and_type()
        load_start = time.perf_counter()
        self.all_tags = self.db.get_tags(tag_type)
        elapsed = time.perf_counter() - load_start
        self._log_selection_event(
            f"{self.current_image_path or 'N/A'} - Loaded {len(self.all_tags)} tags for type '{metadata_type.upper()}:{tag_type}' in {elapsed:.3f}s",
        )

    def _find_tag_insert_index(self, tag):
        """Return the sorted insert position for a tag in the cached order."""
        lower_tag = tag.lower()
        for idx, existing in enumerate(self._tag_order):
            if lower_tag < existing.lower():
                return idx
        return len(self._tag_order)

    def _create_tag_list_item_widget(self, tag):
        widget = QWidget()
        widget.setStyleSheet(
            "background: palette(base); border-radius: 4px; border: 1px solid palette(mid);"
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        tag_label = QLabel(tag)
        tag_label.setStyleSheet("")
        tag_label.setWordWrap(True)
        tag_label.setMinimumWidth(100)
        tag_label.setMaximumWidth(240)
        tag_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(tag_label)

        btn_add = QPushButton("Add")
        btn_add.setStyleSheet("")
        btn_add.setMinimumHeight(36)
        btn_add.setMinimumWidth(SIZE_ADD_BUTTON_WIDTH)
        btn_add.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_add.clicked.connect(lambda checked=False, t=tag: self.add_tag_to_input(t))
        layout.addWidget(btn_add, 0, Qt.AlignVCenter | Qt.AlignRight)

        widget.setLayout(layout)
        margins = layout.contentsMargins()
        content_height = max(tag_label.sizeHint().height(), btn_add.sizeHint().height())
        widget_min_height = content_height + margins.top() + margins.bottom()
        widget.setMinimumHeight(widget_min_height)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        return widget

    def update_tags_list_widget(self, tags):
        if not hasattr(self, "_tag_item_cache"):
            self._tag_item_cache = {}
            self._tag_order = []

        list_widget = self.tags_list_widget
        list_widget.setUpdatesEnabled(False)
        list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        list_widget.setEnabled(True)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        all_tags = self.all_tags or []
        all_sorted = sorted(all_tags, key=lambda t: t.lower())
        cached_tags = set(self._tag_item_cache.keys())
        current_set = set(all_sorted)

        # Remove tags that no longer exist
        for removed_tag in cached_tags - current_set:
            item, widget = self._tag_item_cache.pop(removed_tag)
            row = list_widget.row(item)
            if row != -1:
                list_widget.setItemWidget(item, None)
                taken_item = list_widget.takeItem(row)
                if taken_item is not None:
                    del taken_item
            widget.deleteLater()
            if removed_tag in self._tag_order:
                self._tag_order.remove(removed_tag)

        # Add any new tags
        for tag in all_sorted:
            if tag not in self._tag_item_cache:
                item = QListWidgetItem()
                widget = self._create_tag_list_item_widget(tag)
                insert_index = self._find_tag_insert_index(tag)
                list_widget.insertItem(insert_index, item)
                list_widget.setItemWidget(item, widget)
                size_hint = widget.sizeHint()
                if size_hint.height() < widget.minimumHeight():
                    size_hint.setHeight(widget.minimumHeight())
                item.setSizeHint(size_hint)
                self._tag_item_cache[tag] = (item, widget)
                self._tag_order.insert(insert_index, tag)

        visible_tags = set(tags)
        for tag, (item, widget) in self._tag_item_cache.items():
            item.setHidden(tag not in visible_tags)
            size_hint = widget.sizeHint()
            if size_hint.height() < widget.minimumHeight():
                size_hint.setHeight(widget.minimumHeight())
            item.setSizeHint(size_hint)

        list_widget.setUpdatesEnabled(True)

    def add_tag_to_input(self, tag):
        # Check if tag already exists (case-insensitive)
        existing_tags_lower = [t.lower() for t in (self.cleaned_keywords or [])]
        if tag.lower() in existing_tags_lower:
            # Tag already exists, don't add it again
            return

        # Block invalid tags before they reach the in-memory list
        if not self.is_valid_tag(tag):
            self.show_custom_popup(
                "Invalid Tag",
                "Tag contains invalid characters. Allowed: letters, numbers, spaces, dash, parentheses, colon, apostrophe, question mark, and vertical bar.",
            )
            return
        
        # Insert tag at the end of the input
        if hasattr(self, "cleaned_keywords") and self.cleaned_keywords:
            tags = self.cleaned_keywords + [tag]
        else:
            tags = [tag]
        self.set_tag_input_html(tags)
        self.cleaned_keywords = tags
        self.iptc_text_edit.setFocus()
        # Move cursor to end
        cursor = self.iptc_text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.iptc_text_edit.setTextCursor(cursor)

    def update_tags_search(self):
        # Get search text, filter tags, and update the list widget
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
        if not hasattr(self, "all_tags") or not self.all_tags:
            self.all_tags = self.db.get_tags(tag_type)
        search_text = self.tags_search_bar.text().strip().lower()
        if not search_text:
            filtered = self.all_tags
        else:
            filtered = [tag for tag in self.all_tags if search_text in tag.lower()]
        self.update_tags_list_widget(filtered)

    def is_valid_tag(self, tag):
        """Check if tag contains only allowed characters."""
        if not tag or not tag.strip():
            return False
        return bool(re.fullmatch(r"^[A-Za-z0-9\-\(\):\'\?\|\ ]+$", tag))

    def show_loading_dialog(self, message="Scanning directories..."):
        """Display a modal loading dialog with indeterminate progress bar."""
        self.loading_dialog = QDialog(self)
        self.loading_dialog.setModal(True)
        self.loading_dialog.setWindowTitle("Please Wait")
        layout = QVBoxLayout()
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate/busy
        layout.addWidget(progress)
        self.loading_dialog.setLayout(layout)
        self.loading_dialog.setStyleSheet("")
        self.loading_dialog.setMinimumWidth(420)
        self.loading_dialog.show()
        QApplication.processEvents()

    def hide_loading_dialog(self):
        if hasattr(self, "loading_dialog") and self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None

    def scan_directory(self):
        if not self.folder_path:
            dlg = CustomMessageDialog(
                self, "No Folder Selected", "Please select a folder first."
            )
            dlg.exec()
            return
        # Confirmation dialog before scanning
        result = self.show_custom_confirm(
            "Confirm Scan",
            f"Are you sure you want to scan the directory?\n\n{self.folder_path}",
            yes_text="Yes",
            no_text="No",
        )
        if result != "yes":
            return
        self.show_scan_status("Rescanning directory…")
        self.start_directory_scan(self.folder_path, remove_missing=True)

    def update_search(self):
        search_start = time.perf_counter()
        text = self.search_bar.toPlainText().strip()
        tags = [t.strip() for t in re.split(r",|\s", text) if t.strip()]
        metadata_type, tag_name = self.get_current_tag_and_type()
        tag_type = tag_name
        truncated = text[:40] + ("…" if len(text) > 40 else "")
        self._log_search_event(
            f"Search update start: query='{truncated}' tags={len(tags)} tag_type={tag_type or 'ALL'}"
        )
        self.current_page = 0
        self.update_pagination()
        self.show_current_page()
        total_elapsed = time.perf_counter() - search_start
        self._log_search_event(
            f"Search update complete in {total_elapsed:.3f}s (page={self.current_page + 1}/{self.total_pages})"
        )

    def get_thumbnail_path(self, image_path):
        """Return the path to the cached thumbnail for a given image."""
        return _thumbnail_cache_path(image_path)

    def ensure_thumbnail(self, image_path, size=(250, 250)):
        """Create a thumbnail for the image if it doesn't exist. Return the thumbnail path."""
        return ensure_thumbnail_image(image_path, size)

    def on_search_text_changed(self):
        # Debounce: restart timer on every keystroke
        self.search_debounce_timer.start(350)  # 400ms delay

    def on_metadata_format_changed(self, index):
        # Get the selected format
        format_type = self.metadata_format_dropdown.itemData(index)
        if not format_type:
            return
            
        # Prompt to save unsaved changes before switching
        if not self.handle_save_events():
            # Revert to previous selection
            self.metadata_format_dropdown.blockSignals(True)
            prev_index = 0 if self.current_metadata_type == "iptc" else 1
            self.metadata_format_dropdown.setCurrentIndex(prev_index)
            self.metadata_format_dropdown.blockSignals(False)
            return
        
        # Update format and repopulate field dropdown
        self.current_metadata_type = format_type
        self.metadata_type_dropdown.blockSignals(True)
        self.metadata_type_dropdown.clear()
        
        if format_type == "iptc":
            # Populate IPTC fields
            keyword_index = 0
            for i, tag in enumerate(iptc_tags.iptc_writable_tags):
                display_name = tag["name"].upper()
                self.metadata_type_dropdown.addItem(display_name, tag)
                if tag["tag"] == "Keywords":
                    keyword_index = i
            self.metadata_type_dropdown.setCurrentIndex(keyword_index)
            self.selected_iptc_tag = iptc_tags.iptc_writable_tags[keyword_index]
        else:
            # Populate EXIF fields
            artist_index = 0
            for i, tag in enumerate(exif_tags.exif_writable_tags):
                display_name = tag["name"].upper()
                self.metadata_type_dropdown.addItem(display_name, tag)
                if tag["tag"] == "Artist":
                    artist_index = i
            self.metadata_type_dropdown.setCurrentIndex(artist_index)
            self.selected_exif_tag = exif_tags.exif_writable_tags[artist_index]
        
        self.metadata_type_dropdown.blockSignals(False)
        self.load_previous_tags()
        self.update_tags_search()
        
        # Always update the preview pane for the current image and tag type
        if self.current_image_path:
            self._prepare_metadata_ui_loading()
            self.start_metadata_loading(self.current_image_path)
        else:
            self.set_tag_input_html([])
            self.last_loaded_keywords = ""
            self.iptc_text_edit.setPlaceholderText("Add new tag")
            self.iptc_text_edit.setEnabled(True)
        # Refresh search results for the newly selected metadata format/tag type
        QTimer.singleShot(0, self.update_search)
    
    def on_metadata_field_changed(self, index):
        # Get the selected field data
        field_data = self.metadata_type_dropdown.itemData(index)
        if not field_data:
            return
            
        # Prompt to save unsaved changes before switching
        if not self.handle_save_events():
            # Revert to previous selection
            self.metadata_type_dropdown.blockSignals(True)
            # Find previous field index
            for i in range(self.metadata_type_dropdown.count()):
                data = self.metadata_type_dropdown.itemData(i)
                if data:
                    if self.current_metadata_type == "iptc" and data == self.selected_iptc_tag:
                        self.metadata_type_dropdown.setCurrentIndex(i)
                        break
                    elif self.current_metadata_type == "exif" and data == self.selected_exif_tag:
                        self.metadata_type_dropdown.setCurrentIndex(i)
                        break
            self.metadata_type_dropdown.blockSignals(False)
            return
        
        # Update selected tag for current format
        if self.current_metadata_type == "iptc":
            self.selected_iptc_tag = field_data
        else:
            self.selected_exif_tag = field_data
            
        self.load_previous_tags()
        
        # Use QTimer to defer UI updates and keep interface responsive
        QTimer.singleShot(0, lambda: self._deferred_tag_type_update())

    def _deferred_tag_type_update(self):
        """Refresh search results after tag field changes."""
        self.update_search()
    
    def get_current_tag_and_type(self):
        """Returns (metadata_type, tag_name) tuple based on active tab."""
        if self.current_metadata_type == "iptc":
            tag = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
            return ("iptc", tag)
        else:
            tag = self.selected_exif_tag["tag"] if self.selected_exif_tag else "Artist"
            return ("exif", tag)
    
    def _create_tag_widget(self, tag_text, index):
        """Create a custom widget for a tag with text and delete button."""
        widget = QFrame()
        widget.setFrameShape(QFrame.StyledPanel)
        widget.setFrameShadow(QFrame.Raised)
        widget.setLineWidth(1)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # Use QLabel for the tag - no click action
        tag_label = QLabel(tag_text)
        tag_label.setFont(self.font())
        
        # Delete button
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self._on_tag_delete_clicked(index))
        
        layout.addWidget(tag_label)
        layout.addWidget(delete_btn)
        layout.addStretch()
        
        return widget
    
    def _add_tag_item_to_list(self, tag_text, index, list_widget=None):
        """Add a tag widget to the display list. Returns (item, widget) tuple."""
        if list_widget is None:
            list_widget = self.tag_display_list
        item = QListWidgetItem()
        widget = self._create_tag_widget(tag_text, index)
        item.setSizeHint(QSize(widget.sizeHint().width(), SIZE_TAG_ITEM_HEIGHT))
        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)
        return item, widget
    
    def _update_tag_item_widget(self, item, tag_text, index):
        """Update an existing tag item with new widget."""
        widget = self._create_tag_widget(tag_text, index)
        item.setSizeHint(QSize(widget.sizeHint().width(), SIZE_TAG_ITEM_HEIGHT))
        self.tag_display_list.setItemWidget(item, widget)
    
    def _on_tag_label_clicked(self, index):
        """Handle clicking on a tag label for editing."""
        if index < len(self.cleaned_keywords):
            tag_text = self.cleaned_keywords[index]
            self.iptc_text_edit.setText(tag_text)
            self.iptc_text_edit.setFocus()
            self.iptc_text_edit.selectAll()
            self.editing_tag_index = index
    
    def _on_tag_delete_clicked(self, index):
        """Handle clicking the delete button on a tag."""
        if index < len(self.cleaned_keywords):
            # Remove from keywords list
            del self.cleaned_keywords[index]
            
            # Rebuild the entire display list to fix indices
            self.tag_display_list.clear()
            for i, tag in enumerate(self.cleaned_keywords):
                self._add_tag_item_to_list(tag, i)
            
            # Save to file immediately without popup
            self.save_tags_and_notify(force=True, refresh_ui=True, show_notification=False)
    
    def set_tag_input_html(self, tags):
        """Update the read-only tag display list with given tags."""
        self.tag_display_list.clear()
        for i, tag in enumerate(tags or []):
            self._add_tag_item_to_list(tag, i)
        
        # Clear the input field
        self.iptc_text_edit.clear()
        self.editing_tag_index = None

    def on_tag_input_text_changed(self):
        """Update autocomplete suggestions as user types."""
        self.update_tag_completer()
    
    def on_tag_input_return_pressed(self):
        """Handle Return key in the input field - save the tag and update file."""
        input_text = self.iptc_text_edit.text().strip()

        if input_text and not self.is_valid_tag(input_text):
            self.show_custom_popup(
                "Invalid Tag",
                "Tag contains invalid characters. Allowed: letters, numbers, spaces, dash, parentheses, colon, apostrophe, question mark, and vertical bar.",
            )
            self.iptc_text_edit.setFocus()
            return
        
        if self.editing_tag_index is not None:
            # Editing an existing tag
            if input_text:
                self.cleaned_keywords[self.editing_tag_index] = input_text
                item = self.tag_display_list.item(self.editing_tag_index)
                self._update_tag_item_widget(item, input_text, self.editing_tag_index)
            else:
                # Empty input = delete the tag
                del self.cleaned_keywords[self.editing_tag_index]
                self.tag_display_list.takeItem(self.editing_tag_index)
            self.editing_tag_index = None
        elif input_text:
            # Check for duplicate (case-insensitive)
            existing_tags_lower = [t.lower() for t in self.cleaned_keywords]
            if input_text.lower() not in existing_tags_lower:
                # Adding a new tag - only if not duplicate
                new_index = len(self.cleaned_keywords)
                self.cleaned_keywords.append(input_text)
                self._add_tag_item_to_list(input_text, new_index)
        
        # Clear the input field and save
        self.iptc_text_edit.clear()
        self.save_tags_and_notify(force=True, refresh_ui=True, show_notification=False)
    
    def on_save_edits_clicked(self):
        """Handle Save Edits button click - commit any pending input first, then save."""
        if self.iptc_text_edit.text().strip():
            input_text = self.iptc_text_edit.text().strip()

            if not self.is_valid_tag(input_text):
                self.show_custom_popup(
                    "Invalid Tag",
                    "Tag contains invalid characters. Allowed: letters, numbers, spaces, dash, parentheses, colon, apostrophe, question mark, and vertical bar.",
                )
                self.iptc_text_edit.setFocus()
                return
            
            if self.editing_tag_index is not None:
                # Editing an existing tag
                self.cleaned_keywords[self.editing_tag_index] = input_text
                item = self.tag_display_list.item(self.editing_tag_index)
                self._update_tag_item_widget(item, input_text, self.editing_tag_index)
                self.editing_tag_index = None
            else:
                # Check for duplicate (case-insensitive)
                existing_tags_lower = [t.lower() for t in self.cleaned_keywords]
                if input_text.lower() not in existing_tags_lower:
                    # Adding a new tag - only if not duplicate
                    new_index = len(self.cleaned_keywords)
                    self.cleaned_keywords.append(input_text)
                    self._add_tag_item_to_list(input_text, new_index)
            
            self.iptc_text_edit.clear()
        
        # Save to file
        self.save_tags_and_notify(force=True, refresh_ui=True)

    def update_tag_completer(self):
        """Update the completer based on the current word being typed."""
        try:
            current_line = self.iptc_text_edit.text().strip()
            
            if not current_line or len(current_line) < 1:
                self.tag_suggestions_list.hide()
                return
            
            # Reload tag list to ensure we have the latest tags including newly added ones
            metadata_type, tag_type = self.get_current_tag_and_type()
            all_tags = self.db.get_tags(tag_type)
            # Filter out empty/whitespace-only tags
            all_tags = [t for t in all_tags if t and t.strip()]
            print(f"[DEBUG] update_tag_completer: loaded {len(all_tags)} tags from DB for tag_type '{tag_type}'")
            print(f"[DEBUG] update_tag_completer: tags = {sorted(all_tags)[:20]}...")  # Show first 20 sorted
            sys.stdout.flush()
            
            # Get all tags already in the display list to exclude them
            existing_tags = set(self.cleaned_keywords or [])
            print(f"[DEBUG] update_tag_completer: current_line='{current_line}'")
            print(f"[DEBUG] update_tag_completer: existing_tags={existing_tags}")
            sys.stdout.flush()
            
            # Filter suggestions: match partial string anywhere in tag and exclude already-added tags
            suggestions = [
                tag for tag in all_tags
                if current_line.lower() in tag.lower() and tag not in existing_tags
            ]
            print(f"[DEBUG] update_tag_completer: found {len(suggestions)} suggestions: {suggestions[:10]}")
            sys.stdout.flush()
            
            if suggestions:
                # Update list widget with suggestions
                self.tag_suggestions_list.clear()
                sorted_suggestions = sorted(suggestions, key=str.lower)[:10]
                for tag in sorted_suggestions:  # Show max 10
                    self.tag_suggestions_list.addItem(tag)
                
                print(f"[DEBUG] update_tag_completer: added {self.tag_suggestions_list.count()} items to list widget")
                print(f"[DEBUG] update_tag_completer: widget size={self.tag_suggestions_list.size()}, visible={self.tag_suggestions_list.isVisible()}")
                sys.stdout.flush()
                
                # Position widget above the text input field - anchor to the top of the text edit widget
                text_edit_rect = self.iptc_text_edit.rect()
                local_pos = text_edit_rect.topLeft()
                global_pos = self.iptc_text_edit.mapToGlobal(local_pos)
                parent_pos = self.mapFromGlobal(global_pos)
                
                # Move it above by subtracting the height of the suggestions list
                parent_pos.setY(parent_pos.y() - self.tag_suggestions_list.height())
                
                # Shift slightly to the left to avoid overhanging the right edge
                parent_pos.setX(parent_pos.x() - 50)
                
                self.tag_suggestions_list.move(parent_pos)
                self.tag_suggestions_list.show()
                self.tag_suggestions_list.raise_()
                self.tag_suggestions_list.setCurrentRow(0)
            else:
                self.tag_suggestions_list.hide()
        except Exception as e:
            print(f"[Autocomplete] Error updating suggestions: {e}")
            sys.stdout.flush()
            self.tag_suggestions_list.hide()

    def on_suggestion_clicked(self, item):
        """Handle clicking on a suggestion - add tag directly."""
        try:
            tag_text = item.text()
            
            if self.editing_tag_index is not None:
                # Replace the existing tag being edited
                self.cleaned_keywords[self.editing_tag_index] = tag_text
                list_item = self.tag_display_list.item(self.editing_tag_index)
                self._update_tag_item_widget(list_item, tag_text, self.editing_tag_index)
                self.editing_tag_index = None
            else:
                # Check for duplicate (case-insensitive)
                existing_tags_lower = [t.lower() for t in self.cleaned_keywords]
                if tag_text.lower() not in existing_tags_lower:
                    # Add as new tag - only if not duplicate
                    new_index = len(self.cleaned_keywords)
                    self.cleaned_keywords.append(tag_text)
                    self._add_tag_item_to_list(tag_text, new_index)
            
            self.iptc_text_edit.clear()
            self.tag_suggestions_list.hide()
            self.save_tags_and_notify(force=True, refresh_ui=True, show_notification=False)
            self.iptc_text_edit.setFocus()
        except Exception as e:
            print(f"[Autocomplete] Error inserting suggestion: {e}")
            sys.stdout.flush()

    def handle_save_events(self):
        """
        Unified save handler for switching images/tag types. Only saves if there are unsaved changes and user chooses Yes.
        Returns "saved" if save occurred, True if no save needed or user chose No, False if cancelled or failed.
        """
        # Check if iptc_text_edit exists (may not during initialization)
        if not hasattr(self, 'iptc_text_edit'):
            return True
        
        # Check if there's unsaved input in the edit field
        current_input = self.iptc_text_edit.text().strip()
        if current_input:
            # User has typed something but not pressed Enter
            result = self.show_custom_confirm(
                "Save Changes?",
                "You have unsaved input in the edit field. Save before switching?",
                yes_text="Yes",
                no_text="No",
                cancel_text="Cancel",
            )
            if result == "cancel":
                return False
            elif result == "yes":
                # Simulate pressing Enter to save the current input
                self.on_tag_input_return_pressed()
                return "saved"
            elif result == "no":
                return True
        
        # Check if tags in display list differ from loaded tags
        current_tags_str = "\n".join(self.cleaned_keywords)
        
        if (
            hasattr(self, "last_loaded_keywords")
            and self.current_image_path is not None
            and current_tags_str != self.last_loaded_keywords
        ):
            result = self.show_custom_confirm(
                "Save Changes?",
                "You have unsaved changes to the tags. Save before switching?",
                yes_text="Yes",
                no_text="No",
                cancel_text="Cancel",
            )
            if result == "cancel":
                return False
            elif result == "yes":
                save_success = self.save_tags_and_notify(force=True, refresh_ui=False)
                return "saved" if save_success else False
            elif result == "no":
                return True
        # No unsaved changes, just allow switch
        return True

    def save_tags_and_notify(self, force=False, refresh_ui=True, show_notification=True):
        """
        Save tags, update tag list/database, and optionally show success/failure dialog.
        If force=True, always attempt save (used for save button).
        If show_notification=False, suppress the success popup.
        Returns True if save succeeded or not needed, False if failed.
        """
        # Hide autocomplete popup if visible
        if self.tag_suggestions_list.isVisible():
            self.tag_suggestions_list.hide()
        
        if not self.current_image_path:
            return True
        total_start = time.perf_counter()
        
        # Show modal progress immediately to avoid UI freeze perception
        progress_dialog = QProgressDialog("Editing tags, please wait...", None, 0, 0, self)
        progress_dialog.setWindowTitle("Please Wait")
        progress_dialog.setCancelButton(None)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumWidth(420)
        progress_dialog.setValue(0)
        progress_dialog.show()
        QApplication.processEvents()
        
        def pump():
            # Keep UI responsive while blocking work runs
            QApplication.processEvents()
        
        # Get tags from cleaned_keywords
        keywords = self.cleaned_keywords
        raw_input = "\n".join(keywords)
        
        metadata_type, tag_type = self.get_current_tag_and_type()
        
        # Get multi_valued flag from current tag
        if metadata_type == "iptc":
            multi_valued = (
                self.selected_iptc_tag.get("multi_valued", False)
                if self.selected_iptc_tag
                else False
            )
        else:
            # EXIF fields are typically single-valued
            multi_valued = (
                self.selected_exif_tag.get("multi_valued", False)
                if self.selected_exif_tag
                else False
            )
        
        invalid_tags = [kw for kw in keywords if not self.is_valid_tag(kw)]
        self._log_save_event(
            f"Start save for {self.current_image_path} type={metadata_type} tag={tag_type} keywords={len(keywords)} force={force} refresh_ui={refresh_ui}"
        )
        if not raw_input and not force:
            # No changes to save
            self._log_save_event("No changes detected; skipping save")
            progress_dialog.close()
            return True
        try:
            meta = Exiv2Bind(self.current_image_path)
            meta.from_dict({metadata_type: {tag_type: []}})
            pump()
            self._log_save_event(
                f"Cleared {metadata_type.upper()} {tag_type} in {time.perf_counter() - total_start:.3f}s"
            )
        except Exception as e:
            self._log_save_event(
                f"Failed clearing {metadata_type.upper()} {tag_type}: {e}", level="warning"
            )
            self.show_custom_popup(
                "exiv2 Error", f"Failed to delete {metadata_type.upper()} tag {tag_type}:\n{e}"
            )
            progress_dialog.close()
            return False
        if not raw_input:
            self.db.set_image_tags(self.current_image_path, [], tag_type)
            try:
                self.db.flush_commit()
                pump()
            except Exception as e:
                self._log_save_event(f"DB commit failed: {e}", level="warning")
            self._log_save_event(
                f"DB cleared tags for {self.current_image_path} in {time.perf_counter() - total_start:.3f}s"
            )
            # Always reload tag list for autocomplete
            load_start = time.perf_counter()
            self.load_previous_tags()
            load_elapsed = time.perf_counter() - load_start
            pump()
            
            if refresh_ui:
                refresh_start = time.perf_counter()
                search_start = time.perf_counter()
                self.update_tags_search()
                search_elapsed = time.perf_counter() - search_start
                # Refresh thumbnail view to show/hide image based on current search
                thumb_start = time.perf_counter()
                self.show_current_page()
                thumb_elapsed = time.perf_counter() - thumb_start
                message_start = time.perf_counter()
                if show_notification:
                    self.show_auto_close_message(
                        "Tags Saved",
                        "Tags have been saved successfully.",
                        timeout=1200,
                    )
                message_elapsed = time.perf_counter() - message_start
                pump()
                self._log_save_event(
                    "UI refresh complete for empty tag save in "
                    f"{time.perf_counter() - refresh_start:.3f}s "
                    f"(load={load_elapsed:.3f}s search={search_elapsed:.3f}s "
                    f"thumb={thumb_elapsed:.3f}s message={message_elapsed:.3f}s)"
                )
            self.last_loaded_keywords = ""
            self._log_save_event(
                f"Completed empty tag save in {time.perf_counter() - total_start:.3f}s"
            )
            progress_dialog.close()
            return True
        if invalid_tags:
            self._log_save_event(
                f"Invalid tags blocked save: {invalid_tags}", level="warning"
            )
            self.show_custom_popup(
                "Invalid Tag(s)",
                f"Invalid tag(s) found: {', '.join(invalid_tags)}. Tags must be alphanumeric or dashes only.",
            )
            progress_dialog.close()
            return False
        try:
            write_start = time.perf_counter()
            if multi_valued:
                meta.from_dict({metadata_type: {tag_type: keywords}})
                metadata_elapsed = time.perf_counter() - write_start
                pump()
                self.db.set_image_tags(self.current_image_path, keywords, tag_type)
                try:
                    self.db.flush_commit()
                    pump()
                except Exception as e:
                    self._log_save_event(f"DB commit failed: {e}", level="warning")
            else:
                single_value = keywords[-1] if keywords else ""
                meta.from_dict({metadata_type: {tag_type: [single_value]}})
                metadata_elapsed = time.perf_counter() - write_start
                pump()
                self.db.set_image_tags(
                    self.current_image_path,
                    [single_value] if single_value else [],
                    tag_type,
                )
                try:
                    self.db.flush_commit()
                    pump()
                except Exception as e:
                    self._log_save_event(f"DB commit failed: {e}", level="warning")
            db_elapsed = time.perf_counter() - write_start - metadata_elapsed
            self._log_save_event(
                f"Metadata write took {metadata_elapsed:.3f}s; DB update took {db_elapsed:.3f}s"
            )
            # Add new tags to tag DB and update tag list
            tag_insert_start = time.perf_counter()
            valid_tags_added = 0
            for tag in keywords:
                # Only add valid, non-empty tags to database
                if tag and tag.strip() and self.is_valid_tag(tag):
                    self.db.add_tag(tag, tag_type)
                    valid_tags_added += 1
                    print(f"[DEBUG] Added tag '{tag}' to database for tag_type '{tag_type}'")
                    sys.stdout.flush()
                    pump()
                else:
                    print(f"[DEBUG] Skipped invalid/empty tag: '{tag}'")
                    sys.stdout.flush()
            tag_insert_elapsed = time.perf_counter() - tag_insert_start
            if valid_tags_added > 0:
                self._log_save_event(
                    f"Ensured {valid_tags_added} tag entries in {tag_insert_elapsed:.3f}s"
                )
            # Always reload tag list for autocomplete
            load_start = time.perf_counter()
            self.load_previous_tags()
            load_elapsed = time.perf_counter() - load_start
            print(f"[DEBUG] Reloaded tags, now have {len(self.all_tags)} tags in all_tags")
            sys.stdout.flush()
            pump()
            
            if refresh_ui:
                refresh_start = time.perf_counter()
                search_start = time.perf_counter()
                self.update_tags_search()
                search_elapsed = time.perf_counter() - search_start
                # Refresh thumbnail view to show/hide image based on current search
                thumb_start = time.perf_counter()
                self.show_current_page()
                thumb_elapsed = time.perf_counter() - thumb_start
                message_start = time.perf_counter()
                if show_notification:
                    self.show_auto_close_message(
                        "Tags Saved",
                        "Tags have been saved successfully.",
                        timeout=1200,
                    )
                message_elapsed = time.perf_counter() - message_start
                pump()
                
                # Reload tags into input to ensure all are highlighted with blue background
                self.iptc_text_edit.blockSignals(True)
                self.set_tag_input_html(keywords)
                self.iptc_text_edit.blockSignals(False)
                
                self._log_save_event(
                    f"UI refresh complete in {time.perf_counter() - refresh_start:.3f}s "
                    f"(load={load_elapsed:.3f}s search={search_elapsed:.3f}s "
                    f"thumb={thumb_elapsed:.3f}s message={message_elapsed:.3f}s)"
                )
            self.last_loaded_keywords = raw_input
            self._log_save_event(
                f"Save complete in {time.perf_counter() - total_start:.3f}s"
            )
            progress_dialog.close()
            return True
        except Exception as e:
            self._log_save_event(f"Failed to write {metadata_type.upper()} {tag_type}: {e}", level="warning")
            self.show_custom_popup(
                "exiv2 Error", f"Failed to write {metadata_type.upper()} tag {tag_type}:\n{e}"
            )
            progress_dialog.close()
            return False


def main():
    app = QApplication(sys.argv)
    
    # Set application metadata for proper desktop integration (Linux taskbar icon)
    app.setApplicationName("simple-photo-meta")
    app.setDesktopFileName("simple-photo-meta")
    app.setOrganizationName("danbright")
    app.setOrganizationDomain("danbright.uk")
    
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()