#!/usr/bin/env python3
import sys, os, sqlite3, subprocess, re
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
    QSizePolicy,
)
from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QStandardItemModel,
    QStandardItem,
    QFont,
    QTextCursor,
)
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer, QThread, Signal
import hashlib
from PIL import Image
from simple_photo_meta import iptc_tags
from simple_photo_meta.exiv2bind import Exiv2Bind

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

# === FONT SIZE VARIABLES (ALL FONT SIZES DEFINED HERE) ===
FONT_SIZE_DEFAULT = 13
FONT_SIZE_TAG_INPUT = 16
FONT_SIZE_TAG_LIST = 12
FONT_SIZE_INFO_BANNER = 13
FONT_SIZE_TAG_LABEL = 12
FONT_SIZE_TAG_LIST_ITEM = 12
FONT_SIZE_COMBOBOX = 13
FONT_SIZE_BUTTON = 13
FONT_SIZE_POPUP = 13


class TagDatabase:
    """
    Note: Tags DB created at platform default:
    Platform | Database location
    macOS | ~/Library/Application Support/SPM/tags.db
    Linux | ~/.local/share/SPM/tags.db
    Windows | %LOCALAPPDATA%\SPM\tags.db
    """

    def __init__(self):
        appname = "SimplePhotoMeta"
        appauthor = "Zaziork"
        db_dir = user_data_dir(appname, appauthor)
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "spm_tags.db")
        self.conn = sqlite3.connect(self.db_path)
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
        self.conn.commit()
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


class ScanWorker(QThread):
    scan_finished = Signal()

    def __init__(self, folder_path, db_path, is_valid_tag, selected_iptc_tag):
        super().__init__()
        self.folder_path = folder_path
        self.db_path = db_path
        self.selected_iptc_tag = selected_iptc_tag
        self.is_valid_tag = is_valid_tag

    def run(self):
        try:
            # Create a new TagDatabase instance in this thread
            db = TagDatabase()
            supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
            for root, dirs, files in os.walk(self.folder_path):
                # Skip .thumbnails directories
                if ".thumbnails" in dirs:
                    dirs.remove(".thumbnails")
                for fname in files:
                    if fname.lower().endswith(supported):
                        fpath = os.path.join(root, fname)
                        try:
                            meta = Exiv2Bind(fpath)
                            result = meta.to_dict()
                            iptc_data = result.get("iptc", {})
                            for field in iptc_tags.iptc_writabable_fields_list:
                                tags = []
                                for result_field, result_tag in iptc_data.items():
                                    if result_field == field:
                                        if isinstance(result_tag, list):
                                            tags.extend(result_tag)
                                        else:
                                            tags.append(result_tag)
                                db.set_image_tags(fpath, tags, field)
                        except Exception as e:
                            print(f"Error: {e}")
        finally:
            self.scan_finished.emit()


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
        self.resize(1920, 1080)  # Set initial window size to 1920px wide
        self.folder_path = ""
        self.image_list = []
        self.current_image_path = None
        self.current_page = 0
        self.page_size = 10
        self.total_pages = 1
        self.selected_iptc_tag = None  # <-- Store selected tag dict
        # Create or open the SQLite database
        self.db = TagDatabase()
        self.setStyleSheet(f"background-color: {COLOR_BG_DARK_OLIVE};")
        button_css = (
            f"QPushButton {{ background-color: {COLOR_GOLD}; color: {COLOR_ARMY_GREEN}; font-weight: bold; border-radius: 6px; }} "
            f"QPushButton:pressed {{ background-color: {COLOR_GOLD_HOVER}; }}"
        )
        self.setStyleSheet(self.styleSheet() + "\n" + button_css)

        # Set a single variable for consistent corner radius across all UI elements
        self.corner_radius = 16

        self.create_widgets()
        self.load_previous_tags()

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
        self.setCentralWidget(central_widget)

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
        # Add pressed signal to always trigger preview, even if already selected
        self.list_view.pressed.connect(self.image_selected)
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
        left_panel_widget.setLayout(left_panel)
        # Remove fixed/minimum width so user can resize
        left_panel_widget.setMinimumWidth(100)
        left_panel_widget.setMaximumWidth(16777215)
        main_splitter.addWidget(left_panel_widget)

        # CENTER PANEL: image display and IPTC metadata editor in a vertical splitter
        center_splitter = QSplitter(Qt.Vertical)

        # Canvas for image display (expandable)
        self.image_label = QLabel("Image preview will appear here ...")
        self.image_label.setFont(self.font())
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            f"background-color: {COLOR_IMAGE_PREVIEW_BG}; color:  {COLOR_IMAGE_PREVIEW_TEXT}; border-radius: {self.corner_radius}px; border: 1px solid {COLOR_IMAGE_PREVIEW_BORDER};"
        )
        self.image_label.setMinimumHeight(400)
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
        self.btn_save_tags.setFixedSize(26, 26)
        # Create a monotone (black) floppy disk icon for contrast
        icon_size = 18
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.transparent)
        from PySide6.QtGui import QPainter, QColor, QPen
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        dark = QColor(COLOR_BG_DARK_OLIVE)  # dark olive/black for contrast
        # Draw floppy body
        painter.setPen(Qt.NoPen)
        painter.setBrush(dark)
        painter.drawRect(2, 2, icon_size-4, icon_size-4)
        # Draw floppy notch
        painter.setBrush(QColor(COLOR_GRAY))  # light gray notch
        painter.drawRect(icon_size-7, 2, 5, 7)
        # Draw floppy label
        painter.setBrush(QColor(COLOR_WHITE))
        painter.drawRect(4, 4, icon_size-8, 5)
        # Draw floppy line (write-protect slot)
        pen = QPen(QColor(COLOR_GRAY))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(6, icon_size-5, icon_size-6, icon_size-5)
        painter.end()
        icon = QIcon(pixmap)
        self.btn_save_tags.setIcon(icon)
        self.btn_save_tags.setIconSize(pixmap.size())
        self.btn_save_tags.setStyleSheet(f"QPushButton {{ background-color: {COLOR_DIALOG_BTN_BG}; border-radius: 8px; border: 2px solid {COLOR_DIALOG_BTN_BORDER}; }} QPushButton:hover {{ background-color: {COLOR_DIALOG_BTN_BG_HOVER}; border: 2px solid {COLOR_DIALOG_BTN_BORDER}; }} QPushButton:pressed {{ background-color: {COLOR_DIALOG_BTN_BG_PRESSED}; border: 2px solid {COLOR_DIALOG_BTN_BORDER}; }}")
        self.btn_save_tags.clicked.connect(lambda: self.save_tags_and_notify(force=True))
        rotate_controls.addWidget(self.btn_save_tags)
        rotate_controls.addWidget(self.btn_rotate_right)
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(
            0, 8, 0, 0
        )  # Reduced top margin for better alignment
        image_layout.addWidget(self.image_label)
        image_layout.addLayout(rotate_controls)
        center_splitter.addWidget(image_widget)

        # --- Tag Input Pane with persistent rounded corners and matching width ---
        iptc_input_container = QWidget()
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
            f"QTextEdit {{ background: transparent; border: none; color: {COLOR_TAG_INPUT_TEXT}; font-weight: bold; font-size: {FONT_SIZE_TAG_INPUT}pt; padding-left: 18px; padding-right: 18px; padding-top: 10px; padding-bottom: 10px; }}"
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
        self.tags_list_widget.setToolTip("Click on a tag to insert it into the input")
        # Use itemClicked instead of clicked for more reliable tag selection
        self.tags_list_widget.itemClicked.connect(self.tag_clicked)
        self.tags_list_widget.setStyleSheet(
            f"""
            QListWidget {{
                font-weight: bold;
                padding: 16px 0px 16px 28px; /* Remove right padding */
            }}
            QListWidget::item {{
                background: {COLOR_TAG_LIST_BG};
                color: {COLOR_TAG_LIST_TEXT};
                font-size: {FONT_SIZE_TAG_LIST}pt;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 14px;
                min-height: 6em;
                max-height: 7em;
                white-space: pre-wrap;
                border: 1px solid {COLOR_TAG_LIST_ITEM_BORDER};
            }}
            QListWidget::item:selected {{
                background: {COLOR_TAG_LIST_SELECTED_BG};
                color: {COLOR_TAG_LIST_SELECTED_TEXT};
            }}
            """
            + scrollbar_style
        )
        self.tags_list_widget.setWordWrap(True)
        self.tags_list_widget.setSpacing(8)
        self.tags_list_widget.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.tags_list_widget.setViewportMargins(
            0, 0, 0, 0  # Remove right viewport margin
        )
        self.tags_list_widget.setStyleSheet(
            self.tags_list_widget.styleSheet()
            + f"QListWidget {{ border-radius: {self.corner_radius - 4}px; border: 1px solid {COLOR_TAG_LIST_BORDER}; }} "
            f"QListWidget::item {{ border-radius: {self.corner_radius - 8}px; }} "
        )
        right_panel.addWidget(self.tags_list_widget)

        # IPTC Application2 Tag Dropdown
        self.iptc_tag_dropdown = QComboBox()
        self.iptc_tag_dropdown.setFont(self.font())
        self.iptc_tag_dropdown.setToolTip("Select an IPTC tag")
        # Set gold text color for dropdown
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
        right_panel_widget.setLayout(right_panel)
        main_splitter.addWidget(right_panel_widget)

        # Create the main vertical layout for the window
        main_vlayout = QVBoxLayout()
        # Add a small bottom margin to the main layout for footer padding
        main_vlayout.setContentsMargins(0, 0, 0, 12)  # left, top, right, bottom

        # ======================================================== #
        # INFORMATIONAL BANNER
        # Remove or comment out this section to remove!
        self.info_banner = QLabel("IMPORTANT: This is alpha software. Ensure images are backed up to prevent data loss or damage in the event of software bugs.")
        self.info_banner.setStyleSheet(
            f"background: {COLOR_INFO_BANNER_BG}; color: {COLOR_INFO_BANNER_TEXT}; font-weight: bold; font-size: {FONT_SIZE_INFO_BANNER}pt; padding: 8px 0px; border-radius: 8px; border: 2px solid {COLOR_INFO_BANNER_BORDER};"
        )
        self.info_banner.setAlignment(Qt.AlignCenter)
        self.info_banner.setWordWrap(True)
        # Add a small left/right AND top margin using a container widget and layout, but let the banner fill the width
        banner_container = QWidget()
        banner_layout = QHBoxLayout()
        banner_layout.setContentsMargins(8, 12, 8, 0)  # left, top, right, bottom
        banner_layout.addWidget(self.info_banner)
        banner_container.setLayout(banner_layout)
        main_vlayout.addWidget(banner_container)
        # ======================================================== #

        # Add the splitter to a horizontal layout
        # place splitter directly and stretch
        main_vlayout.setStretch(0, 0)
        main_vlayout.addWidget(main_splitter)
        main_vlayout.setStretch(1, 1)
        central_widget.setLayout(main_vlayout)

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
            self.display_image(self.current_image_path)

    def rotate_right(self):
        if self.current_image_path:
            self._preview_rotation_angle = (self._preview_rotation_angle + 90) % 360
            self.display_image(self.current_image_path)

    def update_pagination(self):
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
        self.page_label.setText(f"Page {self.current_page + 1} / {self.total_pages}")
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
        # Use the database to get the images for the current page
        if not self.folder_path:
            self.image_list = []
            model = QStandardItemModel()
            self.list_view.setModel(model)
            self.update_pagination()
            return
        text = self.search_bar.toPlainText().strip()
        tags = [t.strip() for t in re.split(r",|\s", text) if t.strip()]
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
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
        self.image_list = page_items  # Store full paths, not just basenames
        model = QStandardItemModel()
        supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
        for fpath in page_items:
            if not fpath.lower().endswith(supported):
                continue
            thumb_path = self.ensure_thumbnail(fpath)
            if thumb_path and os.path.exists(thumb_path):
                pixmap = QPixmap(thumb_path)
            else:
                pixmap = QPixmap(fpath)
            if pixmap.isNull():
                icon = QIcon()
            else:
                icon = QIcon(
                    pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            item = QStandardItem()
            item.setIcon(icon)
            item.setEditable(False)
            # Show only the basename in the tooltip, but store full path in data
            item.setText("")
            item.setSizeHint(QPixmap(175, 175).size())
            item.setData(fpath, Qt.UserRole + 1)  # Store full path
            model.appendRow(item)
        self.list_view.setModel(model)
        self.update_pagination()

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

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.current_page = 0
            # Only scan if not previously scanned
            if not self.db.was_directory_scanned(folder):
                self.show_loading_dialog("Scanning for images and tags...")
                self.worker = ScanWorker(
                    folder, self.db.db_path, self.is_valid_tag, self.selected_iptc_tag
                )
                self.worker.scan_finished.connect(self.on_scan_finished)
                self.worker.start()
            else:
                self.update_pagination()
                self.show_current_page()

    def on_scan_finished(self):
        if self.folder_path:
            self.db.mark_directory_scanned(self.folder_path)
        self.hide_loading_dialog()
        self.remove_unused_tags_from_db()
        self.load_previous_tags()
        self.update_search()
        self.update_tags_search()  # Refresh tag search after scan

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
        if not self.handle_save_events():
            return  # Don't switch images
        selected_index = index.row()
        if selected_index < 0 or selected_index >= len(self.image_list):
            return
        # Always get the image path after handle_unsaved_changes
        image_path = self.image_list[selected_index]
        self.current_image_path = image_path
        self._preview_rotation_angle = 0
        self.display_image(self.current_image_path)
        self.iptc_text_edit.clear()  # Explicitly clear input field before setting new tags
        self.extract_keywords()
        # Always update the input field, even if there are no tags
        if hasattr(self, "cleaned_keywords") and self.cleaned_keywords:
            self.set_tag_input_html(self.cleaned_keywords)
        else:
            self.set_tag_input_html([])
        self.last_loaded_keywords = (
            "\n".join(self.cleaned_keywords)
            if hasattr(self, "cleaned_keywords")
            else ""
        )
        self.load_previous_tags()
        self.update_tags_search()

    def display_image(self, path):
        try:
            FILESIZE_THRESHOLD = 25 * 1024 * 1024  # 25MB
            file_size = os.path.getsize(path)
            ext = os.path.splitext(path)[1].lower()
            if file_size > FILESIZE_THRESHOLD or ext in [".tif", ".tiff"]:
                from PIL import Image
                from PySide6.QtGui import QImage
                import io

                pil_img = Image.open(path)
                if hasattr(pil_img, "n_frames") and pil_img.n_frames > 1:
                    pil_img.seek(0)
                max_dim = 2000
                if pil_img.width > max_dim or pil_img.height > max_dim:
                    pil_img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                if (
                    hasattr(self, "_preview_rotation_angle")
                    and self._preview_rotation_angle
                ):
                    pil_img = pil_img.rotate(-self._preview_rotation_angle, expand=True)
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                qimg = QImage.fromData(buf.getvalue())
                pixmap = QPixmap.fromImage(qimg)
            else:
                pixmap = QPixmap(path)
                if (
                    hasattr(self, "_preview_rotation_angle")
                    and self._preview_rotation_angle
                ):
                    from PySide6.QtGui import QTransform

                    transform = QTransform().rotate(self._preview_rotation_angle)
                    pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
            label_width = self.image_label.width()
            label_height = self.image_label.height()
            if label_width < 10 or label_height < 10:
                label_width = 600
                label_height = 400
            margin = 16  # Set your desired margin here
            # Calculate max size for the image
            max_img_width = max(1, label_width - 2 * margin)
            max_img_height = max(1, label_height - 2 * margin)
            scaled_pixmap = pixmap.scaled(
                max_img_width,
                max_img_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            # Create a transparent pixmap for rounded corners
            final_pixmap = QPixmap(label_width, label_height)
            final_pixmap.fill(Qt.transparent)
            from PySide6.QtGui import QPainter, QColor, QPainterPath

            painter = QPainter(final_pixmap)
            radius = self.corner_radius  # Use the shared corner radius
            path = QPainterPath()
            path.addRoundedRect(0, 0, label_width, label_height, radius, radius)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipPath(path)
            # Fill background with skyblue inside rounded rect
            painter.fillPath(path, QColor(COLOR_IMAGE_PREVIEW_BG))
            # Center the image
            x = (label_width - scaled_pixmap.width()) // 2
            y = (label_height - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            self.image_label.setPixmap(final_pixmap)
        except Exception as e:
            self.show_custom_popup(
                "Error", f"Could not open image: {e}\nType: {type(e)}"
            )

    def load_previous_tags(self):
        # Load unique tags for the selected tag type from the SQLite database and populate the list widget.
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
        self.all_tags = self.db.get_tags(tag_type)
        self.update_tags_list_widget(self.all_tags)

    def update_tags_list_widget(self, tags):
        # Clear the list and add custom widgets for each tag
        self.tags_list_widget.clear()
        self.tags_list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self.tags_list_widget.setEnabled(True)
        for tag in sorted(tags, key=lambda t: t.lower()):
            item = QListWidgetItem()
            widget = QWidget()
            widget.setStyleSheet(f"background: {COLOR_TAG_LIST_BG}; border-radius: 8px;")
            layout = QHBoxLayout()
            layout.setContentsMargins(4, 2, 4, 2)
            # Tag label
            tag_label = QLabel(tag)
            tag_label.setStyleSheet(f"font-weight: bold; font-size: {FONT_SIZE_TAG_LABEL}pt; color: {COLOR_TAG_LABEL_TEXT}; padding: 2px 8px;")
            tag_label.setWordWrap(True)
            tag_label.setMinimumWidth(250)
            tag_label.setMaximumWidth(300)  # Limit width to allow wrapping
            layout.addWidget(tag_label)
            layout.addStretch(1)  # Push buttons to the right
            # Add button
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
            btn_add.setFixedHeight(28)
            btn_add.clicked.connect(lambda checked, t=tag: self.add_tag_to_input(t))
            layout.addWidget(btn_add)
            widget.setLayout(layout)
            self.tags_list_widget.addItem(item)
            self.tags_list_widget.setItemWidget(item, widget)

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

    def extract_keywords(self):
        # Extract tags for the selected tag type from exiv2 output.
        tag_type = (
            self.selected_iptc_tag["tag"] if self.selected_iptc_tag else "Keywords"
        )
        try:
            meta = Exiv2Bind(self.current_image_path)
            result = meta.to_dict()
            tags = []
            iptc_data = result.get("iptc", {})
            for result_field, result_tag in iptc_data.items():
                if result_field == tag_type:
                    if isinstance(result_tag, list):
                        tags.extend(result_tag)
                    elif isinstance(result_tag, str):
                        tags.append(result_tag)
            # Remove empty strings and strip whitespace
            tags = [t.strip() for t in tags if t and t.strip()]
        except Exception as e:
            print("Error reading IPTC data:", e)
            self.cleaned_keywords = []
            return
        self.cleaned_keywords = tags

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
        self.show_loading_dialog()
        # Remove missing images from DB before rescanning
        self.db.remove_missing_images(self.folder_path)
        # Pass db_path instead of db instance, and use the correct attribute
        self.worker = ScanWorker(
            self.folder_path, self.db.db_path, self.is_valid_tag, self.selected_iptc_tag
        )
        self.worker.scan_finished.connect(self.on_scan_finished)
        self.worker.start()

    def update_search(self):
        # Just reset to first page and update pagination/display
        self.current_page = 0
        self.update_pagination()
        self.show_current_page()

    def get_thumbnail_path(self, image_path):
        """Return the path to the cached thumbnail for a given image."""
        folder = os.path.dirname(image_path)
        thumb_dir = os.path.join(folder, ".thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        # Use a hash of the absolute path for uniqueness
        hash_str = hashlib.sha256(os.path.abspath(image_path).encode()).hexdigest()
        ext = ".jpg"
        return os.path.join(thumb_dir, f"{hash_str}{ext}")

    def ensure_thumbnail(self, image_path, size=(250, 250)):
        """Create a thumbnail for the image if it doesn't exist. Return the thumbnail path."""
        thumb_path = self.get_thumbnail_path(image_path)
        if not os.path.exists(thumb_path):
            try:
                with Image.open(image_path) as img:
                    img.thumbnail(size, Image.LANCZOS)
                    img = img.convert("RGB")
                    img.save(thumb_path, "JPEG", quality=85)
            except Exception as e:
                print(f"Failed to create thumbnail for {image_path}: {e}")
                return None
        return thumb_path

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
            self.extract_keywords()
            if hasattr(self, "cleaned_keywords") and self.cleaned_keywords:
                self.set_tag_input_html(self.cleaned_keywords)
            else:
                self.set_tag_input_html([])
            self.last_loaded_keywords = (
                "\n".join(self.cleaned_keywords)
                if hasattr(self, "cleaned_keywords")
                else ""
            )
        else:
            self.set_tag_input_html([])
            self.last_loaded_keywords = ""

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
                return self.save_tags_and_notify(force=True)
            elif result == "no":
                return True
        # No unsaved changes, just allow switch
        return True

    def save_tags_and_notify(self, force=False):
        """
        Save tags, update tag list/database, and show success/failure dialog.
        If force=True, always attempt save (used for save button).
        Returns True if save succeeded or not needed, False if failed.
        """
        if not self.current_image_path:
            return True
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
        if not raw_input and not force:
            # No changes to save
            return True
        try:
            meta = Exiv2Bind(self.current_image_path)
            meta.from_dict({"iptc": {tag_type: []}})
        except Exception as e:
            self.show_custom_popup(
                "exiv2 Error", f"Failed to delete IPTC tag {tag_type}:\n{e}"
            )
            return False
        if not raw_input:
            self.db.set_image_tags(self.current_image_path, [], tag_type)
            self.load_previous_tags()
            self.update_tags_search()
            self.last_loaded_keywords = ""
            self.show_auto_close_message("Tags Saved", "Tags have been saved successfully.", timeout=1200)
            return True
        if invalid_tags:
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
                single_value = keywords[-1] if keywords else ""
                meta.from_dict({"iptc": {tag_type: [single_value]}})
                self.db.set_image_tags(
                    self.current_image_path,
                    [single_value] if single_value else [],
                    tag_type,
                )
            # Add new tags to tag DB and update tag list
            for tag in keywords:
                self.db.add_tag(tag, tag_type)
            self.load_previous_tags()
            self.update_tags_search()
            self.last_loaded_keywords = raw_input
            self.show_auto_close_message("Tags Saved", "Tags have been saved successfully.", timeout=1200)
            return True
        except Exception as e:
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