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
        if (tag_type):
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


class IPTCEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTC Editor")
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
        self.setStyleSheet("background-color: #222222;")
        # Set gold background and army green font for all QPushButton widgets
        button_css = "QPushButton { background-color: gold; color: #4B5320; font-weight: bold; border-radius: 6px; } QPushButton:pressed { background-color: #e6c200; }"
        self.setStyleSheet(self.styleSheet() + "\n" + button_css)

        self.create_widgets()
        self.load_previous_tags()

    def style_dialog(self, dialog, min_width=380, min_height=120, padding=18):
        """
        Apply minimum size and padding to dialogs for better readability, without forcing text color.
        """
        dialog.setMinimumWidth(min_width)
        dialog.setMinimumHeight(min_height)
        # Only apply padding to QLabel, do not set color
        dialog.setStyleSheet(f"QLabel {{ padding: {padding}px; }}")

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

    def create_widgets(self):
        # Define scrollbar_style at the very top so it is available everywhere in this method
        scrollbar_style = (
            "QScrollBar:vertical {"
            "    background: transparent;"
            "    width: 16px;"
            "    margin: 0px 0px 0px 0px;"
            "    border-radius: 8px;"
            "}"
            "QScrollBar::handle:vertical {"
            "    background: gold;"
            "    min-height: 24px;"
            "    border-radius: 8px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "    background: none;"
            "    height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "    background: none;"
            "}"
        )
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Set global font size
        font = QFont()
        font.setPointSize(12)
        self.setFont(font)
        central_widget.setFont(font)

        # LEFT PANEL: folder and image list
        left_panel = QVBoxLayout()
        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.setFont(font)
        self.btn_select_folder.clicked.connect(self.select_folder)
        self.btn_scan_directory = QPushButton("Scan Directory")
        self.btn_scan_directory.setFont(font)
        self.btn_scan_directory.clicked.connect(self.scan_directory)
        self.search_bar = QTextEdit()
        self.search_bar.setFont(font)
        self.search_bar.setMaximumHeight(50)  # Increased from 30 to 50
        self.search_bar.setPlaceholderText("Search by tag(s)...")
        self.search_bar.textChanged.connect(self.on_search_text_changed)

        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self.update_search)

        left_panel.addWidget(self.btn_select_folder)
        left_panel.addWidget(self.btn_scan_directory)
        left_panel.addWidget(self.search_bar)

        # Thumbnails list
        self.list_view = QListView()
        self.list_view.setFont(font)
        self.list_view.setViewMode(QListView.IconMode)
        self.list_view.setIconSize(QPixmap(175, 175).size())
        self.list_view.setResizeMode(QListView.Adjust)
        self.list_view.setSpacing(7)  # Changed from 10 to 7
        self.list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_view.setMovement(QListView.Static)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setMinimumHeight(250)
        self.list_view.setMinimumWidth(250)
        self.list_view.clicked.connect(self.image_selected)
        # Add pressed signal to always trigger preview, even if already selected
        self.list_view.pressed.connect(self.image_selected)
        # Add context menu policy and handler for right-click
        self.list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(
            self.show_image_filename_context_menu
        )
        self.list_view.setStyleSheet("QListView { background: skyblue; }")
        left_panel.addWidget(self.list_view)

        # Pagination controls
        self.pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.setFont(font)
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("Next")
        self.btn_next.setFont(font)
        self.btn_next.clicked.connect(self.next_page)
        self.page_label = QLabel()
        self.page_label.setFont(font)
        self.pagination_layout.addWidget(self.btn_prev)
        self.pagination_layout.addWidget(self.page_label)
        self.pagination_layout.addWidget(self.btn_next)
        left_panel.addLayout(self.pagination_layout)

        # Add left panel to main layout
        left_panel_widget = QWidget()
        left_panel_widget.setLayout(left_panel)
        main_layout.addWidget(left_panel_widget, 1)

        # CENTER PANEL: image display and IPTC metadata editor in a vertical splitter
        center_splitter = QSplitter(Qt.Vertical)

        # Canvas for image display (expandable)
        self.image_label = QLabel("Image preview will appear here")
        self.image_label.setFont(font)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: skyblue;")
        self.image_label.setMinimumHeight(400)
        # Add rotation controls below image_label
        rotate_controls = QHBoxLayout()
        self.btn_rotate_left = QPushButton("⟲ Rotate Left")
        self.btn_rotate_right = QPushButton("⟳ Rotate Right")
        self.btn_rotate_left.setFont(font)
        self.btn_rotate_right.setFont(font)
        self.btn_rotate_left.clicked.connect(self.rotate_left)
        self.btn_rotate_right.clicked.connect(self.rotate_right)
        rotate_controls.addWidget(self.btn_rotate_left)
        rotate_controls.addWidget(self.btn_rotate_right)
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self.image_label)
        image_layout.addLayout(rotate_controls)
        center_splitter.addWidget(image_widget)

        # Container for IPTC text edit
        iptc_widget = QWidget()
        iptc_layout = QVBoxLayout(iptc_widget)
        iptc_layout.setContentsMargins(0, 0, 0, 0)
        self.iptc_text_edit = QTextEdit()
        self.iptc_text_edit.setFont(font)
        iptc_layout.addWidget(self.iptc_text_edit)
        center_splitter.addWidget(iptc_widget)
        center_splitter.setSizes([600, 200])
        self.iptc_text_edit.textChanged.connect(self.on_tag_input_text_changed)

        main_layout.addWidget(center_splitter, 2)

        # RIGHT PANEL: tags list (not split)
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(8, 8, 8, 8)
        right_panel.addWidget(QLabel("Tags:"))

        # Add tag search bar before anything that uses it
        self.tags_search_bar = QTextEdit()
        self.tags_search_bar.setFont(self.font())
        self.tags_search_bar.setMaximumHeight(50)  # Increased from 30 to 50
        self.tags_search_bar.setPlaceholderText("Search tags...")
        self.tags_search_bar.textChanged.connect(self.update_tags_search)
        right_panel.addWidget(self.tags_search_bar)

        # Create tags_list_widget early so it's available for other methods
        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setFont(self.font())
        self.tags_list_widget.setToolTip("Click on a tag to insert it into the input")
        # Use itemClicked instead of clicked for more reliable tag selection
        self.tags_list_widget.itemClicked.connect(self.tag_clicked)
        self.tags_list_widget.setStyleSheet(
            """
            QListWidget {
                font-weight: bold;
                padding: 16px 0px 16px 28px; /* Remove right padding */
            }
            QListWidget::item {
                background: skyblue;
                color: black;
                font-size: 12pt;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 14px;
                min-height: 36px;
                max-height: 36px;
                min-width: 40px;
                max-width: 160px;
                white-space: pre-wrap;
            }
            QListWidget::item:selected {
                background: #87ceeb;
                color: yellow;
            }
            """
            + scrollbar_style
        )
        self.tags_list_widget.setWordWrap(True)
        self.tags_list_widget.setSpacing(8)
        self.tags_list_widget.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.tags_list_widget.setViewportMargins(0, 0, 0, 0)  # Remove right viewport margin
        right_panel.addWidget(self.tags_list_widget)

        # IPTC Application2 Tag Dropdown
        self.iptc_tag_dropdown = QComboBox()
        self.iptc_tag_dropdown.setFont(self.font())
        self.iptc_tag_dropdown.setToolTip("Select an IPTC tag")
        # Set gold text color for dropdown
        self.iptc_tag_dropdown.setStyleSheet("QComboBox { color: gold; } QComboBox QAbstractItemView { color: gold; }")
        # Populate dropdown with name and set description as tooltip
        keyword_index = 0
        for i, tag in enumerate(iptc_tags.iptc_writable_tags):
            self.iptc_tag_dropdown.addItem(tag["name"], tag)
            self.iptc_tag_dropdown.setItemData(i, tag["description"], Qt.ToolTipRole)
            if tag["tag"] == "Keywords":
                keyword_index = i
        self.iptc_tag_dropdown.currentIndexChanged.connect(self.on_iptc_tag_changed)
        right_panel.addWidget(self.iptc_tag_dropdown)
        # Set initial value to 'Keywords' if present
        self.iptc_tag_dropdown.setCurrentIndex(keyword_index)
        self.selected_iptc_tag = self.iptc_tag_dropdown.itemData(keyword_index)

        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_panel)
        main_layout.addWidget(right_panel_widget, 1)

        self._preview_rotation_angle = 0
        self._preview_image_cache = None

        # Set background color for all input fields (search bars and tag input) to match tag blue
        skyblue_css = "background: skyblue; color: black; font-size: 12pt; font-weight: bold;"
        self.search_bar.setStyleSheet(f"QTextEdit {{{skyblue_css}}}")
        self.tags_search_bar.setStyleSheet(f"QTextEdit {{{skyblue_css}}}")
        # Only increase font size for the tag input pane
        tag_input_font = QFont()
        tag_input_font.setPointSize(18)
        self.iptc_text_edit.setFont(tag_input_font)
        self.iptc_text_edit.setStyleSheet("QTextEdit { background: skyblue; color: black; font-weight: bold; }")

        # Olive green: #808000
        button_style = (
            "QPushButton { background-color: gold; color: #808000 !important; font-weight: bold; border-radius: 6px; padding: 6px 18px; } "
            "QPushButton:hover { background-color: #ffe066; } "
            "QPushButton:pressed { background-color: #e6c200; }"
        )
        self.btn_select_folder.setStyleSheet(button_style)
        self.btn_scan_directory.setStyleSheet(button_style)
        self.btn_prev.setStyleSheet(button_style)
        self.btn_next.setStyleSheet(button_style)
        self.btn_rotate_left.setStyleSheet(button_style)
        self.btn_rotate_right.setStyleSheet(button_style)

        # Gold scrollbar for tag list and thumbnail list
        scrollbar_style = (
            "QScrollBar:vertical {"
            "    background: transparent;"
            "    width: 16px;"
            "    margin: 0px 0px 0px 0px;"
            "    border-radius: 8px;"
            "}"
            "QScrollBar::handle:vertical {"
            "    background: gold;"
            "    min-height: 24px;"
            "    border-radius: 8px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "    background: none;"
            "    height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "    background: none;"
            "}"
        )
        self.tags_list_widget.setStyleSheet(self.tags_list_widget.styleSheet() + scrollbar_style)
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
        # Only show the filename, do not change selection or call image_selected
        model = self.list_view.model()
        item = model.itemFromIndex(index)
        fpath = item.data(Qt.UserRole + 1)
        if fpath:
            msg = QMessageBox(self)
            msg.setWindowTitle("Filename")
            msg.setText(os.path.basename(fpath))
            self.style_dialog(msg)
            msg.exec()
        # Optionally, clear focus to avoid selection issues
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
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("exiv2 Error")
                msg.setText(f"Failed to delete IPTC tag {tag_type}:\n{e}")
                self.style_dialog(msg)
                msg.exec()
        if not raw_input:
            self.db.set_image_tags(self.current_image_path, [], tag_type)
            return True
        if invalid_tags:
            if show_dialogs:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Invalid Tag(s)")
                msg.setText(
                    f"Invalid tag(s) found: {', '.join(invalid_tags)}. Tags must be alphanumeric or dashes only."
                )
                self.style_dialog(msg)
                msg.exec()
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
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("exiv2 Error")
                msg.setText(f"Failed to write IPTC tag {tag_type}:\n{e}")
                self.style_dialog(msg)
                msg.exec()
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

    def maybe_save_unsaved_changes(self):
        current_input = self.iptc_text_edit.toPlainText().strip()
        if (
            hasattr(self, "last_loaded_keywords")
            and self.current_image_path is not None
            and current_input != self.last_loaded_keywords
        ):
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Save Changes?")
            msg.setText("You have unsaved changes to the tags. Save before switching?")
            msg.setStandardButtons(
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            msg.setDefaultButton(QMessageBox.Yes)
            self.style_dialog(msg)
            reply = msg.exec()
            if reply == QMessageBox.Cancel:
                return False  # Cancel the action
            elif reply == QMessageBox.Yes:
                save_result = self.save_tags_to_file_and_db(show_dialogs=True)
                if save_result is False:
                    return False  # Validation failed, do not proceed
                return True  # Save succeeded, proceed
            elif reply == QMessageBox.No:
                return True  # Discard changes, proceed
        return True

    def image_selected(self, index):
        # Prompt to save unsaved changes before switching images
        if not self.maybe_save_unsaved_changes():
            return  # Don't switch images
        selected_index = index.row()
        if (selected_index < 0 or selected_index >= len(self.image_list)):
            return
        # Always get the image path after maybe_save_unsaved_changes
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
            # Create a new pixmap with the label size and fill with background color
            final_pixmap = QPixmap(label_width, label_height)
            from PySide6.QtGui import QPainter, QColor
            final_pixmap.fill(QColor("skyblue"))
            painter = QPainter(final_pixmap)
            # Center the image
            x = (label_width - scaled_pixmap.width()) // 2
            y = (label_height - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            self.image_label.setPixmap(final_pixmap)
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText(f"Could not open image: {e}\nType: {type(e)}")
            self.style_dialog(msg)
            msg.exec()

    def load_previous_tags(self):
        # Load unique tags for the selected tag type from the SQLite database and populate the list widget.
        tag_type = self.selected_iptc_tag["tag"] if self.selected_iptc_tag else None
        self.all_tags = self.db.get_tags(tag_type)
        self.update_tags_list_widget(self.all_tags)

    def update_tags_list_widget(self, tags):
        # Sort tags alphabetically before displaying
        sorted_tags = sorted(tags, key=lambda t: t.lower())
        self.tags_list_widget.clear()
        self.tags_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tags_list_widget.setEnabled(True)
        for tag in sorted_tags:
            self.tags_list_widget.addItem(tag)

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
        tag = item.text()
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
        self.style_dialog(
            self.loading_dialog, min_width=340, min_height=120, padding=16
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
        confirm_box = QMessageBox(self)
        confirm_box.setIcon(QMessageBox.Question)
        confirm_box.setWindowTitle("Confirm Scan")
        confirm_box.setText(
            f"Are you sure you want to scan the directory?\n\n{self.folder_path}"
        )
        confirm_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm_box.setDefaultButton(QMessageBox.No)
        self.style_dialog(confirm_box)
        confirm = confirm_box.exec()
        if (confirm != QMessageBox.Yes):
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
        if not self.maybe_save_unsaved_changes():
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
            tag_input_font.setPointSize(18)
            self.iptc_text_edit.setFont(tag_input_font)
            self.iptc_text_edit.setStyleSheet(
                "QTextEdit { background: #0d2356; color: white; font-family: 'Arial', 'Helvetica', sans-serif; font-weight: bold; }"
            )
            return
        # Set plain text, one tag per line
        text = "\n".join(tags)
        self.iptc_text_edit.blockSignals(True)
        self.iptc_text_edit.setPlainText(text)
        self.iptc_text_edit.blockSignals(False)
        tag_input_font = QFont()
        tag_input_font.setPointSize(18)
        self.iptc_text_edit.setFont(tag_input_font)
        self.iptc_text_edit.setStyleSheet(
            "QTextEdit { background: #0d2356; color: white; font-family: 'Arial', 'Helvetica', sans-serif; font-weight: bold; }"
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


def main():
    app = QApplication(sys.argv)
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
