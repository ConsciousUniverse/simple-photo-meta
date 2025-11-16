#!/usr/bin/env python3
import sys, os, sqlite3, subprocess, re, time
from appdirs import user_data_dir
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
    QPushButton,
    QFileDialog,
    QMessageBox,
    QListView,
    QAbstractItemView,
    QSplitter,
    QDialog,
    QComboBox,
    QSizePolicy
)
from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QStandardItemModel,
    QStandardItem,
    QFont,
    QTextCursor,
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QTimer
import hashlib
from PIL import Image, ImageOps
from datetime import datetime

from simple_photo_meta import iptc_tags
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
                img.thumbnail(size, Image.LANCZOS)
                img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=85)
        except Exception as exc:
            print(f"Failed to create thumbnail for {image_path}: {exc}")
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
            if hasattr(img, "n_frames") and img.n_frames > 1:
                img.seek(0)
            img = ImageOps.exif_transpose(img)
            target_size = (edge_length, edge_length)
            img.thumbnail(target_size, Image.LANCZOS)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            else:
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

# === COLOUR VARIABLES (ALL COLOURS DEFINED HERE) ===

# Base palette
COLOR_BG_DARK_OLIVE = "#232d18"
COLOR_GOLD = "gold"
COLOR_GOLD_HOVER = "#e6c200"
COLOR_GOLD_PRESSED = "#c9a800"
COLOR_ARMY_GREEN = "#4B5320"
COLOR_PAPER = "#FFFACD"
COLOR_ORANGE = "orange"
COLOR_BLACK = "black"
COLOR_WHITE = "white"
COLOR_GRAY = "#bdbdbd"

# Thumbnails pane
COLOR_THUMB_LIST_PANE_BG = COLOR_BG_DARK_OLIVE
COLOR_THUMB_LIST_PANE_BORDER = COLOR_GOLD

# Image preview
COLOR_IMAGE_PREVIEW_BG = COLOR_BG_DARK_OLIVE
COLOR_IMAGE_PREVIEW_BORDER = COLOR_GOLD
COLOR_IMAGE_PREVIEW_TEXT = COLOR_GOLD

# Tag input pane
COLOR_TAG_INPUT_BG = COLOR_PAPER
COLOR_TAG_INPUT_TEXT = COLOR_BG_DARK_OLIVE
COLOR_TAG_INPUT_BORDER = COLOR_GOLD

# Tag list widget
COLOR_TAG_LIST_BG = COLOR_PAPER
COLOR_TAG_LIST_TEXT = COLOR_BLACK
COLOR_TAG_LIST_SELECTED_BG = COLOR_GOLD
COLOR_TAG_LIST_SELECTED_TEXT = COLOR_BG_DARK_OLIVE
COLOR_TAG_LIST_BORDER = COLOR_GOLD
COLOR_TAG_LIST_ITEM_BORDER = COLOR_GOLD

# Tag label in tag list
COLOR_TAG_LABEL_TEXT = COLOR_BG_DARK_OLIVE

# Tag add button in tag list
COLOR_TAG_ADD_BTN_BG = COLOR_GOLD
COLOR_TAG_ADD_BTN_TEXT = COLOR_BG_DARK_OLIVE
COLOR_TAG_ADD_BTN_BORDER = COLOR_GOLD
COLOR_TAG_ADD_BTN_BG_HOVER = COLOR_GOLD_HOVER
COLOR_TAG_ADD_BTN_BG_PRESSED = COLOR_GOLD_PRESSED

# Search bars (thumbs and tags)
COLOR_SEARCH_INPUT_BG = COLOR_PAPER
COLOR_SEARCH_INPUT_TEXT = COLOR_BLACK
COLOR_SEARCH_INPUT_BORDER = COLOR_GOLD

# Pagination controls
COLOR_PAGINATION_BTN_BG = COLOR_GOLD
COLOR_PAGINATION_BTN_TEXT = COLOR_BG_DARK_OLIVE
COLOR_PAGINATION_BTN_BORDER = COLOR_GOLD
COLOR_PAGINATION_BTN_BG_HOVER = COLOR_GOLD_HOVER
COLOR_PAGINATION_BTN_BG_PRESSED = COLOR_GOLD_PRESSED

# Info banner
COLOR_INFO_BANNER_BG = COLOR_ORANGE
COLOR_INFO_BANNER_TEXT = COLOR_BG_DARK_OLIVE
COLOR_INFO_BANNER_BORDER = COLOR_GOLD

# Dialogs
COLOR_DIALOG_BG = COLOR_BG_DARK_OLIVE
COLOR_DIALOG_TEXT = COLOR_GOLD
COLOR_DIALOG_BTN_BG = COLOR_GOLD
COLOR_DIALOG_BTN_TEXT = COLOR_BG_DARK_OLIVE
COLOR_DIALOG_BTN_BORDER = COLOR_GOLD
COLOR_DIALOG_BTN_BG_HOVER = COLOR_GOLD_HOVER
COLOR_DIALOG_BTN_BG_PRESSED = COLOR_GOLD_PRESSED

# Combobox
COLOR_COMBOBOX_BG = COLOR_BG_DARK_OLIVE
COLOR_COMBOBOX_TEXT = COLOR_GOLD
COLOR_COMBOBOX_BORDER = COLOR_GOLD

# Scrollbars
COLOR_SCROLLBAR_BG = "transparent"
COLOR_SCROLLBAR_HANDLE = COLOR_GOLD
COLOR_SCROLLBAR_BORDER = COLOR_GOLD
COLOR_SCROLLBAR_WIDTH = "16px"
COLOR_SCROLLBAR_WIDTH_WIDE = "21px"

# Buttons
SIZE_ADD_BUTTON_WIDTH = 75
SIZE_ADD_BUTTON_HEIGHT = 45

# === FONT SIZE VARIABLES (ALL FONT SIZES DEFINED HERE) ===
FONT_SIZE_DEFAULT = 12
FONT_SIZE_TAG_INPUT = 12
FONT_SIZE_TAG_LIST = 12
FONT_SIZE_INFO_BANNER = 12
FONT_SIZE_TAG_LABEL = 12
FONT_SIZE_TAG_LIST_ITEM = 12
FONT_SIZE_COMBOBOX = 12
FONT_SIZE_BUTTON = 12
FONT_SIZE_POPUP = 12


class TagDatabase:
    """
    Note: Tags DB created at platform default:
    Platform | Database location
    macOS | ~/Library/Application Support/SPM/tags.db
    Linux | ~/.local/share/SPM/tags.db
    Windows | %LOCALAPPDATA%\SPM\tags.db
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

    def add_tag(self, tag, tag_type):
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO tags (tag, tag_type) VALUES (?, ?)",
                (tag, tag_type),
            )
            self.conn.commit()
        except Exception as e:
            print("Error inserting tag", tag, tag_type, e)

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

    def get_tags(self, tag_type=None):
        c = self.conn.cursor()
        if tag_type:
            c.execute(
                "SELECT tag FROM tags WHERE tag_type=? ORDER BY tag ASC", (tag_type,)
            )
        else:
            c.execute("SELECT tag FROM tags ORDER BY tag ASC")
        return [row[0] for row in c.fetchall()]

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
                where_clauses.append(f"t{idx}.tag LIKE ?")
                params.append(f"%{tag}%")
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
                where_clauses.append(f"t{idx}.tag LIKE ?")
                params.append(f"%{tag}%")
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
            c.execute(query, params)
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
            supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
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

    def __init__(self, image_path, tag_type):
        super().__init__()
        self.image_path = image_path
        self.tag_type = tag_type

    def run(self):
        start = time.perf_counter()
        print(
            f"[MetadataWorker] Start {self.image_path} tag={self.tag_type}"
        )
        sys.stdout.flush()
        if self.isInterruptionRequested():
            print(f"[MetadataWorker] Cancelled before work {self.image_path}")
            sys.stdout.flush()
            return
        try:
            meta = Exiv2Bind(self.image_path)
            result = meta.to_dict()
            iptc_data = result.get("iptc", {})
            tags = []
            for field, value in iptc_data.items():
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
                f"[MetadataWorker] Done {self.image_path} tag={self.tag_type} in {elapsed:.2f}s"
            )
            sys.stdout.flush()
            self.metadata_ready.emit(self.image_path, self.tag_type, tags)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(
                f"[MetadataWorker] Exception {self.image_path} tag={self.tag_type} in {elapsed:.2f}s: {exc}"
            )
            sys.stdout.flush()
            if not self.isInterruptionRequested():
                self.metadata_failed.emit(self.image_path, self.tag_type, str(exc))


class ThumbnailBatchWorker(QThread):
    thumbnail_ready = Signal(int, str, str)
    finished = Signal()

    def __init__(self, tasks, size=(250, 250)):
        super().__init__()
        self.tasks = tasks  # List of (row_index, image_path)
        self.size = size

    def run(self):
        try:
            for row_index, image_path in self.tasks:
                if self.isInterruptionRequested():
                    break
                try:
                    thumb_path = ensure_thumbnail_image(image_path, self.size)
                except Exception as exc:
                    print(f"[ThumbnailWorker] Failed {image_path}: {exc}")
                    sys.stdout.flush()
                    continue
                if self.isInterruptionRequested():
                    break
                if thumb_path:
                    self.thumbnail_ready.emit(row_index, image_path, thumb_path)
        finally:
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
        self.setStyleSheet(
            f"QDialog {{ background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; }} "
            f"QLabel {{ color: {COLOR_DIALOG_TEXT}; }} "
            f"QPushButton {{ background-color: {COLOR_DIALOG_BTN_BG}; color: {COLOR_DIALOG_BTN_TEXT}; font-weight: bold; border-radius: 6px; padding: 6px 18px; }}"
        )


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
        btn.setStyleSheet(
            f"background-color: {COLOR_DIALOG_BTN_BG}; color: {COLOR_DIALOG_BTN_TEXT}; font-weight: bold; border-radius: 6px; padding: 6px 18px;"
        )
        layout.addWidget(btn, alignment=Qt.AlignRight)
        self.setMinimumWidth(420)
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"QDialog {{ background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; }} QLabel {{ color: {COLOR_DIALOG_TEXT}; font-size: {FONT_SIZE_POPUP}pt; }}"
        )
        self.adjustSize()


class IPTCEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Photo Meta (alpha)")
        # Dynamically set initial window size based on available screen size
        from PySide6.QtGui import QGuiApplication
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
        self.page_size = 10
        self.total_pages = 1
        self.selected_iptc_tag = None  # <-- Store selected tag dict
        self._preview_retry_counts = {}
        self._preview_timers = {}
        self._metadata_timers = {}
        self._metadata_pending_key = None
        self.cleaned_keywords = []
        # Create or open the SQLite database
        self.db = TagDatabase()
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
        self.setStyleSheet(f"background-color: {COLOR_BG_DARK_OLIVE};")
        button_css = (
            f"QPushButton {{ background-color: {COLOR_GOLD}; color: {COLOR_ARMY_GREEN}; font-weight: bold; border-radius: 6px; }} "
            f"QPushButton:pressed {{ background-color: {COLOR_GOLD_HOVER}; }}"
        )
        self.setStyleSheet(self.styleSheet() + "\n" + button_css)

        # Set a single variable for consistent corner radius across all UI elements
        self.corner_radius = 16

        self._tag_item_cache = {}
        self._tag_order = []
        self.create_widgets()
        self.load_previous_tags()
        self._scan_refresh_timer = QTimer(self)
        self._scan_refresh_timer.setSingleShot(True)
        self._scan_refresh_timer.timeout.connect(self._refresh_view_after_scan)
        self._scan_status_clear_timer = QTimer(self)
        self._scan_status_clear_timer.setSingleShot(True)
        self._scan_status_clear_timer.timeout.connect(self.clear_scan_status)

    def style_dialog(self, dialog, min_width=380, min_height=120, padding=18):
        """
        Apply minimum size and padding to dialogs for better readability, and set background/text color for Linux compatibility.
        Also set button text color to gold.
        For QMessageBox, do not force fixed size—let it autosize, but ensure word wrap and margins.
        """
        dialog.setMinimumWidth(min_width)
        dialog.setMinimumHeight(min_height)
        dialog.setStyleSheet(
            f"QLabel {{ padding: {padding}px; background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; }} "
            f"QDialog {{ background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; }} "
            f"QMessageBox {{ background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; min-width: {min_width}px; min-height: {min_height}px; }} "
            f"QPushButton {{ background-color: {COLOR_DIALOG_BTN_BG}; color: {COLOR_DIALOG_BTN_TEXT} !important; font-weight: bold; border-radius: 6px; padding: 6px 18px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_GOLD_HOVER}; }} "
            f"QPushButton:pressed {{ background-color: {COLOR_GOLD_PRESSED}; }} "
        )
        # If it's a QMessageBox, set word wrap and margins for the label and icon, but do not force fixed size
        from PySide6.QtWidgets import QMessageBox, QLabel

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
        btn_yes.setStyleSheet(
            f"background-color: {COLOR_DIALOG_BTN_BG}; color: {COLOR_DIALOG_BTN_TEXT}; font-weight: bold; border-radius: 6px; padding: 6px 18px;"
        )
        btn_no.setStyleSheet(
            f"background-color: {COLOR_DIALOG_BTN_BG}; color: {COLOR_DIALOG_BTN_TEXT}; font-weight: bold; border-radius: 6px; padding: 6px 18px;"
        )
        btn_row.addWidget(btn_yes)
        btn_row.addWidget(btn_no)
        if cancel_text:
            btn_cancel = QPushButton(cancel_text)
            btn_cancel.setStyleSheet(
                f"background-color: {COLOR_DIALOG_BTN_BG}; color: {COLOR_DIALOG_BTN_TEXT}; font-weight: bold; border-radius: 6px; padding: 6px 18px;"
            )
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
        dlg.setStyleSheet(
            f"QDialog {{ background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; }} QLabel {{ color: {COLOR_DIALOG_TEXT}; font-size: {FONT_SIZE_POPUP}pt; }}"
        )
        dlg.exec()
        return result["value"]

    def create_widgets(self):
        scrollbar_style = (
            f"QScrollBar:vertical {{"
            f"    background: {COLOR_SCROLLBAR_BG};"
            f"    width: {COLOR_SCROLLBAR_WIDTH};"
            f"    margin: 0px 0px 0px 0px;"
            f"    border-radius: 8px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"    background: {COLOR_SCROLLBAR_HANDLE};"
            f"    min-height: 24px;"
            f"    border-radius: 8px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"    background: none;"
            f"    height: 0px;"
            f"}}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{"
            f"    background: none;"
            f"}}"
        )
        central_widget = QWidget()
        central_widget.setContentsMargins(0,0,0,0)
        self.setCentralWidget(central_widget)

        # === BEGIN: Wrap all widgets in a single outer QWidget ===
        outer_container = QWidget()
        outer_container.setStyleSheet("padding-bottom: 11px;")
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_container.setLayout(outer_layout)

        # Use a QSplitter for user-adjustable left pane
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL: folder and image list
        left_panel = QVBoxLayout()
        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.setFont(self.font())
        self.btn_select_folder.clicked.connect(self.select_folder)
        self.btn_scan_directory = QPushButton("Scan Directory")
        self.btn_scan_directory.setFont(self.font())
        self.btn_scan_directory.clicked.connect(self.scan_directory)
        self.search_bar = QTextEdit()
        self.search_bar.setFont(self.font())
        self.search_bar.setMaximumHeight(50)  # Increased from 30 to 50
        self.search_bar.setPlaceholderText("ENTER TAGS(S) TO SEARCH IMAGES FOR ...")
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        self.search_bar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.search_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self.update_search)

        left_panel.addWidget(self.btn_select_folder)
        left_panel.addWidget(self.btn_scan_directory)
        left_panel.addWidget(self.search_bar)
        self.scan_status_label = QLabel()
        self.scan_status_label.setFont(self.font())
        self.scan_status_label.setStyleSheet(
            f"background: {COLOR_INFO_BANNER_BG}; color: {COLOR_INFO_BANNER_TEXT}; border-radius: {self.corner_radius - 6}px; padding: 6px 12px;"
        )
        self.scan_status_label.setVisible(False)
        left_panel.addWidget(self.scan_status_label)

        # Thumbnails list
        self.list_view = QListView()
        self.list_view.setFont(self.font())
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
        self.list_view.setStyleSheet(
            f"QListView {{ background: {COLOR_THUMB_LIST_PANE_BG}; border-radius: {self.corner_radius}px; border: 1px solid {COLOR_THUMB_LIST_PANE_BORDER}; padding: 16px; }}" + scrollbar_style
        )
        left_panel.addWidget(self.list_view)

        # Pagination controls
        self.pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.setFont(self.font())
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("Next")
        self.btn_next.setFont(self.font())
        self.btn_next.clicked.connect(self.next_page)
        self.page_label = QLabel()
        self.page_label.setFont(self.font())
        self.pagination_layout.addWidget(self.btn_prev)
        self.pagination_layout.addWidget(self.page_label)
        self.pagination_layout.addWidget(self.btn_next)
        left_panel.addLayout(self.pagination_layout)

        # Add left panel to main layout
        left_panel_widget = QWidget()
        left_panel_widget.setContentsMargins(0,0,0,0)
        left_panel_widget.setLayout(left_panel)
        main_splitter.addWidget(left_panel_widget)

        # CENTER PANEL: image display and IPTC metadata editor in a vertical splitter
        center_splitter = QSplitter(Qt.Vertical)

        # Canvas for image display (expandable)
        self.image_label = QLabel("Image preview will appear here ...")
        self.image_label.setFont(self.font())
        self.image_label.setAlignment(Qt.AlignCenter)
        # Restore border-radius in stylesheet for rounded corners (no border in CSS)
        self.image_label.setStyleSheet(
            f"background-color: {COLOR_IMAGE_PREVIEW_BG}; color: {COLOR_IMAGE_PREVIEW_TEXT}; border-radius: {self.corner_radius}px;margin: 5px;"
        )
        self.image_label.setScaledContents(True)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # Add rotation controls below image_label
        rotate_controls = QHBoxLayout()
        self.btn_rotate_left = QPushButton("⟲ Rotate Left")
        self.btn_rotate_right = QPushButton("⟳ Rotate Right")
        self.btn_rotate_left.setFont(self.font())
        self.btn_rotate_right.setFont(self.font())
        self.btn_rotate_left.clicked.connect(self.rotate_left)
        self.btn_rotate_right.clicked.connect(self.rotate_right)
        rotate_controls.addWidget(self.btn_rotate_left)
        # Add save button (icon) between rotate buttons
        self.btn_save_tags = QPushButton()
        self.btn_save_tags.setToolTip("Save tags for this image")
        # Use a standard checkmark icon from Qt for the save button, and center it vertically
        from PySide6.QtWidgets import QApplication, QStyle
        style = QApplication.instance().style() if QApplication.instance() else None
        icon_size = 18
        self.btn_save_tags.setFixedSize(icon_size + 6, icon_size + 6)  # Add padding for centering
        if style:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
            self.btn_save_tags.setIcon(icon)
            self.btn_save_tags.setIconSize(QSize(icon_size, icon_size))
        else:
            self.btn_save_tags.setText("✓")  # fallback
        self.btn_save_tags.setStyleSheet(f"QPushButton {{ background-color: {COLOR_DIALOG_BTN_BG}; border-radius: 8px; border: 2px solid {COLOR_DIALOG_BTN_BORDER}; padding: 3px; }} QPushButton:hover {{ background-color: {COLOR_DIALOG_BTN_BG_HOVER}; border: 2px solid {COLOR_DIALOG_BTN_BORDER}; }} QPushButton:pressed {{ background-color: {COLOR_DIALOG_BTN_BG_PRESSED}; border: 2px solid {COLOR_DIALOG_BTN_BORDER}; }}")
        self.btn_save_tags.clicked.connect(
            lambda: self.save_tags_and_notify(force=True, refresh_ui=True)
        )
        rotate_controls.addWidget(self.btn_save_tags)
        rotate_controls.addWidget(self.btn_rotate_right)
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(
            0, 8, 0, 0  # Reduced top margin for better alignment
        )
        image_layout.addWidget(self.image_label)
        image_layout.addLayout(rotate_controls)
        center_splitter.addWidget(image_widget)

        # --- Tag Input Pane with persistent rounded corners and matching width ---
        iptc_input_container = QWidget()
        iptc_input_container.setContentsMargins(0,0,0,0)
        iptc_input_container.setObjectName("IptcInputContainer")
        iptc_input_container.setStyleSheet(
            f"""
            QWidget#IptcInputContainer {{
                background: {COLOR_TAG_INPUT_BG};
                border-radius: {self.corner_radius - 4}px;
                border: 1px solid {COLOR_TAG_INPUT_BORDER};
                margin-left: 0px;
                margin-right: 0px;
                margin-bottom: 12px;
            }}
            """
        )
        iptc_layout = QVBoxLayout(iptc_input_container)
        iptc_layout.setContentsMargins(0, 0, 0, 0)
        self.iptc_text_edit = QTextEdit()
        self.iptc_text_edit.setFont(self.font())
        self.iptc_text_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none; color: {COLOR_TAG_INPUT_TEXT}; font-weight: bold; font-size: {FONT_SIZE_TAG_INPUT}pt; padding-left: 18px; padding-right: 18px; padding-top: 10px; padding-bottom: 10px;}}"
        )
        iptc_layout.addWidget(self.iptc_text_edit)
        # Ensure the container expands horizontally to match the image preview
        iptc_input_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        center_splitter.addWidget(iptc_input_container)
        center_splitter.setSizes([600, 200])
        self.iptc_text_edit.textChanged.connect(self.on_tag_input_text_changed)
        # --- end tag input pane wrap ---

        main_splitter.addWidget(center_splitter)

        # RIGHT PANEL: tags list (not split)
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(8, 8, 8, 8)

        # Add tag search bar before anything that uses it
        self.tags_search_bar = QTextEdit()
        self.tags_search_bar.setFont(self.font())
        self.tags_search_bar.setMaximumHeight(50)  # Increased from 30 to 50
        self.tags_search_bar.setPlaceholderText("ENTER TAGS TO SEARCH LIST FOR ...")
        self.tags_search_bar.textChanged.connect(self.update_tags_search)
        self.tags_search_bar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tags_search_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_panel.addWidget(self.tags_search_bar)

        # Create tags_list_widget early so it's available for other methods
        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setFont(self.font())
        # Use itemClicked instead of clicked for more reliable tag selection
        self.tags_list_widget.itemClicked.connect(self.tag_clicked)
        self.tags_list_widget.setStyleSheet(
            f"""
            QListWidget {{
                font-weight: bold;
                padding: 12px 8px 12px 12px;
                border: none;
            }}
            QListWidget::item {{
                background: transparent;
                color: {COLOR_TAG_LIST_TEXT};
                font-size: {FONT_SIZE_TAG_LIST}pt;
                font-weight: bold;
                border: none;
                padding: 0px;
                margin: 0px;
                white-space: pre-wrap;
            }}
            QListWidget::item:selected {{
                background: {COLOR_TAG_LIST_SELECTED_BG};
                color: {COLOR_TAG_LIST_SELECTED_TEXT};
            }}
            """
            + scrollbar_style
        )
        self.tags_list_widget.setWordWrap(True)
        self.tags_list_widget.setSpacing(10)
        self.tags_list_widget.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.tags_list_widget.setViewportMargins(0, 0, 0, 0)
        self.tags_list_widget.setStyleSheet(
            self.tags_list_widget.styleSheet()
            + f"QListWidget {{ border-radius: {self.corner_radius - 4}px; border: 1px solid {COLOR_TAG_LIST_BORDER}; }} "
        )
        right_panel.addWidget(self.tags_list_widget)

        # IPTC Application2 Tag Dropdown
        self.iptc_tag_dropdown = QComboBox()
        self.iptc_tag_dropdown.setFont(self.font())
        self.iptc_tag_dropdown.setToolTip("Select an IPTC tag")
        right_panel.addWidget(self.iptc_tag_dropdown)
        # Populate dropdown with name and set description as tooltip
        keyword_index = 0
        for i, tag in enumerate(iptc_tags.iptc_writable_tags):
            display_name = tag["name"].upper()
            self.iptc_tag_dropdown.addItem(display_name, tag)
            self.iptc_tag_dropdown.setItemData(i, tag["description"], Qt.ToolTipRole)
            if tag["tag"] == "Keywords":
                keyword_index = i
        self.iptc_tag_dropdown.currentIndexChanged.connect(self.on_iptc_tag_changed)
        # Set initial value to 'Keywords' if present
        self.iptc_tag_dropdown.setCurrentIndex(keyword_index)
        self.selected_iptc_tag = self.iptc_tag_dropdown.itemData(keyword_index)

        right_panel_widget = QWidget()
        right_panel_widget.setContentsMargins(0, 0, 0, 0)  # Add margin (left, top, right, bottom)
        right_panel_widget.setLayout(right_panel)
        main_splitter.addWidget(right_panel_widget)

        # Add the splitter to the outer layout
        outer_layout.addWidget(main_splitter)
        # === END: All widgets are now inside outer_container ===

        # Set the outer_container as the only child of the central widget
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(outer_container)
        central_widget.setLayout(central_layout)

        self._preview_rotation_angle = 0
        self._preview_image_cache = None

        # Set background color for all input fields (search bars and tag input) to match tag blue
        skyblue_css = (
            f"background: {COLOR_SEARCH_INPUT_BG}; color: {COLOR_SEARCH_INPUT_TEXT}; font-size: {FONT_SIZE_TAG_INPUT}pt; font-weight: bold; "
            f"border-radius: {self.corner_radius - 4}px; border: 1.5px solid {COLOR_SEARCH_INPUT_BORDER}; "
            f"padding-left: 18px; padding-right: 18px; padding-top: 10px; padding-bottom: 10px;"
        )
        # Make search input font slightly smaller
        search_font = QFont()
        search_font.setPointSize(FONT_SIZE_DEFAULT)
        self.search_bar.setFont(search_font)
        self.tags_search_bar.setFont(search_font)
        self.search_bar.setStyleSheet(f"QTextEdit {{{skyblue_css} font-size: {FONT_SIZE_DEFAULT}pt;}}")
        self.tags_search_bar.setStyleSheet(
            f"QTextEdit {{{skyblue_css} font-size: {FONT_SIZE_DEFAULT}pt;}}"
        )
        # Only increase font size for the tag input pane
        tag_input_font = QFont()
        tag_input_font.setPointSize(FONT_SIZE_TAG_INPUT)
        self.iptc_text_edit.setFont(tag_input_font)
        self.iptc_text_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none; color: {COLOR_TAG_INPUT_TEXT}; font-weight: bold; font-size: {FONT_SIZE_TAG_INPUT}pt; padding-left: 18px; padding-right: 18px; padding-top: 10px; padding-bottom: 10px; }}"
        )
        # Style QListWidget (tags_list_widget) for rounded corners
        self.tags_list_widget.setStyleSheet(
            self.tags_list_widget.styleSheet()
            + f"QListWidget {{ border-radius: {self.corner_radius - 4}px; border: 1px solid {COLOR_TAG_LIST_BORDER}; }} "
            f"QListWidget::item {{ border-radius: {self.corner_radius - 8}px; }} "
        )
        # Style QComboBox (iptc_tag_dropdown) for rounded corners
        self.iptc_tag_dropdown.setStyleSheet(
            f"""
            QComboBox {{
                color: {COLOR_COMBOBOX_TEXT};
                border-radius: {self.corner_radius - 4}px;
                border: 2px solid {COLOR_COMBOBOX_BORDER};
                padding: 6px;
                background: {COLOR_COMBOBOX_BG};
                font-size: {FONT_SIZE_COMBOBOX}pt;
            }}
            QComboBox QAbstractItemView {{
                color: {COLOR_COMBOBOX_TEXT};
                border-radius: {self.corner_radius - 4}px;
                background: {COLOR_COMBOBOX_BG};
                font-size: {FONT_SIZE_COMBOBOX}pt;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 32px;
                border-top-right-radius: {self.corner_radius - 4}px;
                border-bottom-right-radius: {self.corner_radius - 4}px;
                border: none;
                background: transparent;
            }}
            """
        )

        button_style = (
            f"QPushButton {{ background-color: {COLOR_PAGINATION_BTN_BG}; color: {COLOR_PAGINATION_BTN_TEXT} !important; font-weight: bold; border-radius: {self.corner_radius - 10}px; border: 2px solid {COLOR_PAGINATION_BTN_BORDER}; padding: 6px 18px; font-size: {FONT_SIZE_BUTTON}pt; }} "
            f"QPushButton:hover {{ background-color: {COLOR_PAGINATION_BTN_BG_HOVER}; color: {COLOR_PAGINATION_BTN_TEXT} !important; border: 2px solid {COLOR_PAGINATION_BTN_BORDER}; }} "
            f"QPushButton:pressed {{ background-color: {COLOR_PAGINATION_BTN_BG_PRESSED}; color: {COLOR_PAGINATION_BTN_TEXT} !important; border: 2px solid {COLOR_PAGINATION_BTN_BORDER}; }}"
        )
        self.btn_select_folder.setStyleSheet(button_style)
        self.btn_scan_directory.setStyleSheet(button_style)
        self.btn_prev.setStyleSheet(button_style)
        self.btn_next.setStyleSheet(button_style)
        self.btn_rotate_left.setStyleSheet(button_style)
        self.btn_rotate_right.setStyleSheet(button_style)

        # Gold scrollbar for tag list and thumbnail list
        scrollbar_style = (
            f"QScrollBar:vertical {{"
            f"    background: {COLOR_SCROLLBAR_BG};"
            f"    width: {COLOR_SCROLLBAR_WIDTH_WIDE};"
            f"    margin: 0px 5px 0px 0px;"
            f"    border-radius: 8px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"    background: {COLOR_SCROLLBAR_HANDLE};"
            f"    min-height: 24px;"
            f"    border-radius: 8px;"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"    background: none;"
            f"    height: 0px;"
            f"}}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{"
            f"    background: none;"
            f"}}"
        )
        self.tags_list_widget.setStyleSheet(
            self.tags_list_widget.styleSheet() + scrollbar_style
        )
        self.list_view.setStyleSheet(self.list_view.styleSheet() + scrollbar_style)

    def rotate_left(self):
        if self.current_image_path:
            self._preview_rotation_angle = (self._preview_rotation_angle - 90) % 360
            self._apply_rotation()

    def rotate_right(self):
        if self.current_image_path:
            self._preview_rotation_angle = (self._preview_rotation_angle + 90) % 360
            self._apply_rotation()

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
            tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
            if not tags:
                if tag_type:
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
        self.page_label.setStyleSheet(f"color: {COLOR_PAPER}")
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
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
        query_start = time.perf_counter()
        if not tags:
            if tag_type:
                page_items = self.db.get_untagged_images_of_type_in_folder_paginated(
                    self.folder_path, self.current_page, self.page_size, tag_type
                )
            else:
                page_items = self.db.get_untagged_images_in_folder_paginated(
                    self.folder_path, self.current_page, self.page_size
                )
        else:
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
        model = QStandardItemModel()
        supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
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
        self.update_pagination()
        build_elapsed = time.perf_counter() - build_start
        total_elapsed = time.perf_counter() - page_start
        self._log_search_event(
            f"Model built with {model.rowCount()} rows in {build_elapsed:.3f}s; total show_current_page={total_elapsed:.3f}s"
        )
        if thumbnail_tasks:
            self.start_thumbnail_worker(thumbnail_tasks)

    def start_thumbnail_worker(self, tasks):
        self.cancel_thumbnail_worker()
        if not tasks:
            return
        worker = ThumbnailBatchWorker(tasks)
        worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        worker.finished.connect(self.on_thumbnail_worker_finished)
        self.thumbnail_worker = worker
        self._log_search_event(f"Thumbnail worker started for {len(tasks)} items")
        worker.start()

    def on_thumbnail_ready(self, row_index, image_path, thumb_path):
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
        if self.thumbnail_worker:
            self.thumbnail_worker.requestInterruption()
            if wait and self.thumbnail_worker.isRunning():
                self.thumbnail_worker.wait()
            self.thumbnail_worker.deleteLater()
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

    def on_thumbnail_worker_finished(self):
        self._log_search_event("Thumbnail worker finished")
        if self.thumbnail_worker:
            worker = self.thumbnail_worker
            self.thumbnail_worker = None
            try:
                worker.deleteLater()
            except RuntimeError:
                pass

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
        tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
        self.cancel_metadata_worker()
        key = (image_path, tag_type)
        self._metadata_pending_key = key
        self._metadata_timers[key] = time.perf_counter()
        self._log_metadata_event(
            f"Starting metadata worker for {image_path}; tag={tag_type}"
        )
        worker = MetadataWorker(image_path, tag_type)
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
        current_tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
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
        self.iptc_text_edit.setPlaceholderText("")
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
        current_tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
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
        self.iptc_text_edit.setPlaceholderText("Unable to load IPTC tags.")
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

    def _log_preview_event(self, message, level="info"):
        prefix = "[Preview]"
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

    def _log_metadata_event(self, message, level="info"):
        prefix = "[Metadata]"
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

    def _log_selection_event(self, message, level="info"):
        prefix = "[Selection]"
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

    def _log_search_event(self, message, level="info"):
        prefix = "[Search]"
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

    def _log_save_event(self, message, level="info"):
        prefix = "[Save]"
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
        FILESIZE_THRESHOLD = 25 * 1024 * 1024  # 25MB
        file_size = os.path.getsize(path)
        ext = os.path.splitext(path)[1].lower()
        if file_size > FILESIZE_THRESHOLD or ext in [".tif", ".tiff"]:
            from PySide6.QtGui import QImage
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
        if not getattr(self, "_preview_image_cache", None):
            return
        pixmap = self._preview_image_cache
        if getattr(self, "_preview_rotation_angle", 0):
            from PySide6.QtGui import QTransform

            transform = QTransform().rotate(self._preview_rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self._render_pixmap_to_label(pixmap)

    def _render_pixmap_to_label(self, pixmap):
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
        from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen

        painter = QPainter(final_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = self.corner_radius
        path = QPainterPath()
        path.addRoundedRect(1, 1, label_width - 2, label_height - 2, radius, radius)
        painter.fillPath(path, QColor(COLOR_IMAGE_PREVIEW_BG))
        pen = QPen(QColor(COLOR_IMAGE_PREVIEW_BORDER))
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
        # Always get plain text for saving
        raw_input = self.iptc_text_edit.toPlainText().strip()
        tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
        multi_valued = (
            self.selected_iptc_tag.get("multi_valued", False)
            if self.selected_iptc_tag
            else False
        )
        keywords = [kw.strip() for kw in raw_input.splitlines() if kw.strip()]
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
        current_input = self.iptc_text_edit.toPlainText().strip()
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
        if not self.handle_save_events():
            log_step("Selection blocked by unsaved changes", level="warning", path_hint="N/A")
            return  # Don't switch images
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
            label_width = self.image_label.width()
            label_height = self.image_label.height()
            final_pixmap = QPixmap(label_width, label_height)
            final_pixmap.fill(Qt.transparent)
            from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen

            painter = QPainter(final_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            radius = self.corner_radius
            path = QPainterPath()
            path.addRoundedRect(1, 1, label_width - 2, label_height - 2, radius, radius)
            painter.fillPath(path, QColor(COLOR_IMAGE_PREVIEW_BG))
            pen = QPen(QColor(COLOR_IMAGE_PREVIEW_BORDER))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            painter.end()
            self.image_label.setPixmap(final_pixmap)

    def closeEvent(self, event):
        self.cancel_preview_worker(wait=True)
        self.cancel_metadata_worker(wait=True)
        self.cancel_thumbnail_worker(wait=True)
        self.cancel_active_scan()
        super().closeEvent(event)

    def load_previous_tags(self):
        # Load unique tags for the selected tag type from the SQLite database and populate the list widget.
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
        load_start = time.perf_counter()
        self.all_tags = self.db.get_tags(tag_type)
        elapsed = time.perf_counter() - load_start
        self._log_selection_event(
            f"{self.current_image_path or 'N/A'} - Loaded {len(self.all_tags)} tags in {elapsed:.3f}s",
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
            f"color: {COLOR_ARMY_GREEN}; background: {COLOR_TAG_LIST_BG}; border-radius: 8px; border: 1px solid {COLOR_TAG_LIST_ITEM_BORDER};"
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        tag_label = QLabel(tag)
        tag_label.setStyleSheet(
            f"font-weight: bold; font-size: {FONT_SIZE_TAG_LABEL}pt; color: {COLOR_TAG_LABEL_TEXT}; padding: 2px 8px;"
        )
        tag_label.setWordWrap(True)
        tag_label.setMinimumWidth(100)
        tag_label.setMaximumWidth(240)
        tag_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(tag_label)

        btn_add = QPushButton("Add")
        btn_add.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_TAG_ADD_BTN_BG};
                color: {COLOR_TAG_ADD_BTN_TEXT};
                font-weight: bold;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: {FONT_SIZE_TAG_LIST_ITEM}pt;
            }}
            QPushButton:hover {{
                background-color: {COLOR_TAG_ADD_BTN_BG_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {COLOR_TAG_ADD_BTN_BG_PRESSED};
            }}
            """
        )
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
        # Insert tag at the end of the input (plain text, then update HTML)
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
        search_text = self.tags_search_bar.toPlainText().strip().lower()
        if not search_text:
            filtered = self.all_tags
        else:
            filtered = [tag for tag in self.all_tags if search_text in tag.lower()]
        self.update_tags_list_widget(filtered)

    def tag_clicked(self, item):
        # Do nothing when a tag is clicked (only the Add button should add the tag)
        pass

    def is_valid_tag(self, tag):
        # Only allow alphanumeric and dashes
        return bool(re.fullmatch(r"^[A-Za-z0-9\-\(\):\'\?\|\ ]*$", tag))

    def show_loading_dialog(self, message="Scanning directories..."):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar

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
        self.loading_dialog.setStyleSheet(
            f"QDialog {{ background: {COLOR_DIALOG_BG}; color: {COLOR_DIALOG_TEXT}; }} QLabel {{ color: {COLOR_DIALOG_TEXT}; }}"
        )
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
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
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

    def on_iptc_tag_changed(self, index):
        # Prompt to save unsaved changes before switching tag type
        if not self.handle_save_events():
            # Revert dropdown to previous index if cancelled
            self.iptc_tag_dropdown.blockSignals(True)
            for i in range(self.iptc_tag_dropdown.count()):
                if self.iptc_tag_dropdown.itemData(i)["tag"] == (
                    self.selected_iptc_tag["tag"]
                    if self.selected_iptc_tag
                    else "Keywords"
                ):
                    self.iptc_tag_dropdown.setCurrentIndex(i)
                    break
            self.iptc_tag_dropdown.blockSignals(False)
            return
        self.selected_iptc_tag = self.iptc_tag_dropdown.itemData(index)
        self.load_previous_tags()
        self.update_search()
        self.update_tags_search()
        # Always update the preview pane for the current image and tag type
        if self.current_image_path:
            self._prepare_metadata_ui_loading()
            self.start_metadata_loading(self.current_image_path)
        else:
            self.set_tag_input_html([])
            self.last_loaded_keywords = ""
            self.iptc_text_edit.setPlaceholderText("")
            self.iptc_text_edit.setEnabled(True)

    def set_tag_input_html(self, tags):
        if not tags:
            self.iptc_text_edit.clear()
            tag_input_font = QFont()
            tag_input_font.setPointSize(FONT_SIZE_TAG_INPUT)
            self.iptc_text_edit.setFont(tag_input_font)
            self.iptc_text_edit.setStyleSheet(
                f"QTextEdit {{ background: transparent; border: none; color: {COLOR_TAG_INPUT_TEXT}; font-family: 'Arial', 'Helvetica', sans-serif; font-weight: bold; font-size: {FONT_SIZE_TAG_INPUT}pt; padding-left: 18px; padding-right: 18px; padding-top: 10px; padding-bottom: 10px; }}"
            )
            return
        # Set plain text, one tag per line
        text = "\n".join(tags)
        self.iptc_text_edit.blockSignals(True)
        self.iptc_text_edit.setPlainText(text)
        self.iptc_text_edit.blockSignals(False)
        tag_input_font = QFont()
        tag_input_font.setPointSize(FONT_SIZE_TAG_INPUT)
        self.iptc_text_edit.setFont(tag_input_font)
        self.iptc_text_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none; color: {COLOR_TAG_INPUT_TEXT}; font-weight: bold; font-size: {FONT_SIZE_TAG_INPUT}pt; padding-left: 18px; padding-right: 18px; padding-top: 10px; padding-bottom: 10px; }}"
        )
        # Move cursor to end
        cursor = self.iptc_text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.iptc_text_edit.setTextCursor(cursor)

    def on_tag_input_text_changed(self):
        # Get plain text, split into lines, and re-apply HTML styling
        text = self.iptc_text_edit.toPlainText()
        tags = text.split("\n")
        self.set_tag_input_html(tags)
        self.cleaned_keywords = [t for t in tags if t.strip()]

    def handle_save_events(self):
        """
        Unified save handler for switching images/tag types. Only saves if there are unsaved changes and user chooses Yes.
        Returns True if save succeeded or not needed, False if cancelled or failed.
        """
        current_input = self.iptc_text_edit.toPlainText().strip()
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
                return self.save_tags_and_notify(force=True, refresh_ui=False)
            elif result == "no":
                return True
        # No unsaved changes, just allow switch
        return True

    def save_tags_and_notify(self, force=False, refresh_ui=True):
        """
        Save tags, update tag list/database, and show success/failure dialog.
        If force=True, always attempt save (used for save button).
        Returns True if save succeeded or not needed, False if failed.
        """
        if not self.current_image_path:
            return True
        total_start = time.perf_counter()
        raw_input = self.iptc_text_edit.toPlainText().strip()
        tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
        multi_valued = (
            self.selected_iptc_tag.get("multi_valued", False)
            if self.selected_iptc_tag
            else False
        )
        keywords = [kw.strip() for kw in raw_input.splitlines() if kw.strip()]
        invalid_tags = [kw for kw in keywords if not self.is_valid_tag(kw)]
        self._log_save_event(
            f"Start save for {self.current_image_path} tag={tag_type} keywords={len(keywords)} force={force} refresh_ui={refresh_ui}"
        )
        if not raw_input and not force:
            # No changes to save
            self._log_save_event("No changes detected; skipping save")
            return True
        try:
            meta = Exiv2Bind(self.current_image_path)
            meta.from_dict({"iptc": {tag_type: []}})
            self._log_save_event(
                f"Cleared IPTC {tag_type} in {time.perf_counter() - total_start:.3f}s"
            )
        except Exception as e:
            self._log_save_event(
                f"Failed clearing IPTC {tag_type}: {e}", level="warning"
            )
            self.show_custom_popup(
                "exiv2 Error", f"Failed to delete IPTC tag {tag_type}:\n{e}"
            )
            return False
        if not raw_input:
            self.db.set_image_tags(self.current_image_path, [], tag_type)
            self._log_save_event(
                f"DB cleared tags for {self.current_image_path} in {time.perf_counter() - total_start:.3f}s"
            )
            if refresh_ui:
                refresh_start = time.perf_counter()
                load_start = time.perf_counter()
                self.load_previous_tags()
                load_elapsed = time.perf_counter() - load_start
                search_start = time.perf_counter()
                self.update_tags_search()
                search_elapsed = time.perf_counter() - search_start
                message_start = time.perf_counter()
                self.show_auto_close_message(
                    "Tags Saved",
                    "Tags have been saved successfully.",
                    timeout=1200,
                )
                message_elapsed = time.perf_counter() - message_start
                self._log_save_event(
                    "UI refresh complete for empty tag save in "
                    f"{time.perf_counter() - refresh_start:.3f}s "
                    f"(load={load_elapsed:.3f}s search={search_elapsed:.3f}s "
                    f"message={message_elapsed:.3f}s)"
                )
            self.last_loaded_keywords = ""
            self._log_save_event(
                f"Completed empty tag save in {time.perf_counter() - total_start:.3f}s"
            )
            return True
        if invalid_tags:
            self._log_save_event(
                f"Invalid tags blocked save: {invalid_tags}", level="warning"
            )
            self.show_custom_popup(
                "Invalid Tag(s)",
                f"Invalid tag(s) found: {', '.join(invalid_tags)}. Tags must be alphanumeric or dashes only.",
            )
            return False
        try:
            write_start = time.perf_counter()
            if multi_valued:
                meta.from_dict({"iptc": {tag_type: keywords}})
                metadata_elapsed = time.perf_counter() - write_start
                self.db.set_image_tags(self.current_image_path, keywords, tag_type)
            else:
                single_value = keywords[-1] if keywords else ""
                meta.from_dict({"iptc": {tag_type: [single_value]}})
                metadata_elapsed = time.perf_counter() - write_start
                self.db.set_image_tags(
                    self.current_image_path,
                    [single_value] if single_value else [],
                    tag_type,
                )
            db_elapsed = time.perf_counter() - write_start - metadata_elapsed
            self._log_save_event(
                f"Metadata write took {metadata_elapsed:.3f}s; DB update took {db_elapsed:.3f}s"
            )
            # Add new tags to tag DB and update tag list
            tag_insert_start = time.perf_counter()
            for tag in keywords:
                self.db.add_tag(tag, tag_type)
            tag_insert_elapsed = time.perf_counter() - tag_insert_start
            if keywords:
                self._log_save_event(
                    f"Ensured {len(keywords)} tag entries in {tag_insert_elapsed:.3f}s"
                )
            if refresh_ui:
                refresh_start = time.perf_counter()
                load_start = time.perf_counter()
                self.load_previous_tags()
                load_elapsed = time.perf_counter() - load_start
                search_start = time.perf_counter()
                self.update_tags_search()
                search_elapsed = time.perf_counter() - search_start
                message_start = time.perf_counter()
                self.show_auto_close_message(
                    "Tags Saved",
                    "Tags have been saved successfully.",
                    timeout=1200,
                )
                message_elapsed = time.perf_counter() - message_start
                self._log_save_event(
                    f"UI refresh complete in {time.perf_counter() - refresh_start:.3f}s "
                    f"(load={load_elapsed:.3f}s search={search_elapsed:.3f}s "
                    f"message={message_elapsed:.3f}s)"
                )
            self.last_loaded_keywords = raw_input
            self._log_save_event(
                f"Save complete in {time.perf_counter() - total_start:.3f}s"
            )
            return True
        except Exception as e:
            self._log_save_event(f"Failed to write IPTC {tag_type}: {e}", level="warning")
            self.show_custom_popup(
                "exiv2 Error", f"Failed to write IPTC tag {tag_type}:\n{e}"
            )
            return False


def main():
    app = QApplication(sys.argv)
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()