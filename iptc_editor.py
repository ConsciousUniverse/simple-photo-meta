#!/usr/bin/env python3
import sys, os, sqlite3, subprocess, shlex, re
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
)
from PySide6.QtGui import QPixmap, QIcon, QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer, QThread, Signal
import hashlib
from PIL import Image


class TagDatabase:
    def __init__(self, db_path="tags.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        c = self.conn.cursor()
        # Tags table
        c.execute(
            "CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT UNIQUE)"
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

    def add_tag(self, tag):
        try:
            c = self.conn.cursor()
            c.execute("INSERT OR IGNORE INTO tags (tag) VALUES (?)", (tag,))
            self.conn.commit()
        except Exception as e:
            print("Error inserting tag", tag, e)

    def get_tag_id(self, tag):
        c = self.conn.cursor()
        c.execute("SELECT id FROM tags WHERE tag=?", (tag,))
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

    def add_image_tag(self, image_path, tag):
        image_id = self.add_image(image_path)
        self.add_tag(tag)
        tag_id = self.get_tag_id(tag)
        if image_id and tag_id:
            c = self.conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                (image_id, tag_id),
            )
            self.conn.commit()

    def set_image_tags(self, image_path, tags):
        """Replace all tags for an image with the provided list."""
        image_id = self.add_image(image_path)
        c = self.conn.cursor()
        # Remove all existing tag associations for this image
        c.execute("DELETE FROM image_tags WHERE image_id=?", (image_id,))
        # Add new tags
        for tag in tags:
            self.add_tag(tag)
            tag_id = self.get_tag_id(tag)
            if tag_id:
                c.execute(
                    "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                    (image_id, tag_id),
                )
        self.conn.commit()

    def get_tags(self):
        c = self.conn.cursor()
        c.execute("SELECT tag FROM tags ORDER BY tag ASC")
        return [row[0] for row in c.fetchall()]

    def get_images_with_tags(self, tags):
        # Partial search: tags are treated as substrings (LIKE '%tag%')
        c = self.conn.cursor()
        if not tags:
            c.execute("SELECT path FROM images ORDER BY path ASC")
            return [row[0] for row in c.fetchall()]
        # For each tag fragment, find images that have at least one tag containing that fragment
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
        query = base_query + " ".join(join_clauses)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " GROUP BY i.id ORDER BY i.path ASC"
        c.execute(query, params)
        return [row[0] for row in c.fetchall()]

    def get_image_count_in_folder(self, folder_path, tags=None):
        c = self.conn.cursor()
        if tags:
            # Use the same logic as get_images_with_tags, but count(*)
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
            query = base_query + " ".join(join_clauses)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            # Only images in the folder
            query += " AND " if where_clauses else " WHERE "
            query += "i.path LIKE ?"
            params.append(os.path.join(os.path.abspath(folder_path), "%"))
            c.execute(query, params)
        else:
            query = "SELECT COUNT(*) FROM images WHERE path LIKE ?"
            c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"),))
        row = c.fetchone()
        return row[0] if row else 0

    def get_images_in_folder_paginated(self, folder_path, page, page_size, tags=None):
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
            query = base_query + " ".join(join_clauses)
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            # Only images in the folder
            query += " AND " if where_clauses else " WHERE "
            query += "i.path LIKE ?"
            params.append(os.path.join(os.path.abspath(folder_path), "%"))
            query += " GROUP BY i.id ORDER BY i.path ASC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            c.execute(query, params)
        else:
            query = "SELECT path FROM images WHERE path LIKE ? ORDER BY path ASC LIMIT ? OFFSET ?"
            c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"), page_size, offset))
        return [row[0] for row in c.fetchall()]

    def get_untagged_images_in_folder_paginated(self, folder_path, page, page_size):
        c = self.conn.cursor()
        offset = page * page_size
        # Select images in folder that have no tags
        query = '''
            SELECT i.path FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            WHERE i.path LIKE ? AND it.tag_id IS NULL
            ORDER BY i.path ASC LIMIT ? OFFSET ?
        '''
        c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"), page_size, offset))
        return [row[0] for row in c.fetchall()]

    def get_untagged_image_count_in_folder(self, folder_path):
        c = self.conn.cursor()
        query = '''
            SELECT COUNT(*) FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            WHERE i.path LIKE ? AND it.tag_id IS NULL
        '''
        c.execute(query, (os.path.join(os.path.abspath(folder_path), "%"),))
        row = c.fetchone()
        return row[0] if row else 0

    def mark_directory_scanned(self, dir_path):
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO scanned_dirs (path, last_scan) VALUES (?, datetime('now'))", (os.path.abspath(dir_path),))
        self.conn.commit()

    def was_directory_scanned(self, dir_path):
        c = self.conn.cursor()
        c.execute("SELECT last_scan FROM scanned_dirs WHERE path=?", (os.path.abspath(dir_path),))
        row = c.fetchone()
        return row[0] if row else None

    def remove_missing_images(self, dir_path):
        c = self.conn.cursor()
        c.execute("SELECT path FROM images WHERE path LIKE ?", (os.path.join(os.path.abspath(dir_path), "%"),))
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

    def __init__(self, folder_path, db_path, is_valid_tag):
        super().__init__()
        self.folder_path = folder_path
        self.db_path = db_path
        self.is_valid_tag = is_valid_tag

    def run(self):
        import subprocess, os, re
        try:
            # Create a new TagDatabase instance in this thread
            db = TagDatabase(self.db_path)
            supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
            for root, dirs, files in os.walk(self.folder_path):
                for fname in files:
                    if fname.lower().endswith(supported):
                        fpath = os.path.join(root, fname)
                        result = subprocess.run(
                            ["exiv2", "-pi", fpath], capture_output=True, text=True
                        )
                        if result.returncode != 0:
                            continue
                        for line in result.stdout.splitlines():
                            if "Iptc.Application2.Keywords" in line:
                                parts = re.split(r"\s{2,}", line.strip())
                                if len(parts) >= 4:
                                    keyword_value = parts[-1].strip()
                                    if self.is_valid_tag(keyword_value):
                                        db.add_image_tag(fpath, keyword_value)
        finally:
            self.scan_finished.emit()


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
        # Create or open the SQLite database
        self.db = TagDatabase()

        self.create_widgets()
        self.load_previous_tags()

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

        # Set the timer to automatically close the message box.
        QTimer.singleShot(timeout, msg_box.close)
        msg_box.exec()

    def create_widgets(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Set global font size
        font = QFont()
        font.setPointSize(16)
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
        # Add context menu policy and handler for right-click
        self.list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(
            self.show_image_filename_context_menu
        )
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
        self.image_label.setStyleSheet("background-color: gray;")
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

        # Container for IPTC text edit and buttons
        iptc_widget = QWidget()
        iptc_layout = QVBoxLayout(iptc_widget)
        iptc_layout.setContentsMargins(0, 0, 0, 0)
        self.iptc_text_edit = QTextEdit()
        self.iptc_text_edit.setFont(font)
        iptc_layout.addWidget(self.iptc_text_edit)
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Tags")
        self.btn_save.setFont(font)
        self.btn_save.clicked.connect(self.save_iptc)
        btn_layout.addWidget(self.btn_save)
        iptc_layout.addLayout(btn_layout)
        center_splitter.addWidget(iptc_widget)
        center_splitter.setSizes([600, 200])

        main_layout.addWidget(center_splitter, 2)

        # RIGHT PANEL: tags list (not split)
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Tags:"))

        # Add tag search bar
        self.tags_search_bar = QTextEdit()
        self.tags_search_bar.setFont(self.font())
        self.tags_search_bar.setMaximumHeight(50)  # Increased from 30 to 50
        self.tags_search_bar.setPlaceholderText("Search tags...")
        self.tags_search_bar.textChanged.connect(self.update_tags_search)
        right_panel.addWidget(self.tags_search_bar)

        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setFont(self.font())
        self.tags_list_widget.setToolTip("Click on a tag to insert it into the input")
        self.tags_list_widget.clicked.connect(self.tag_clicked)
        self.tags_list_widget.setStyleSheet(
            """
            QListWidget::item {
                background: skyblue;
                color: black;
                font-size: 16pt;
                margin-bottom: 7px;
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 32px;
                white-space: pre-wrap;
                /* word-break: break-word; Removed: not supported in Qt */
            }
            QListWidget::item:selected {
                background: #87ceeb;
                color: yellow;
            }
        """
        )
        self.tags_list_widget.setWordWrap(True)
        right_panel.addWidget(self.tags_list_widget)
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_panel)
        main_layout.addWidget(right_panel_widget, 1)

        self._preview_rotation_angle = 0
        self._preview_image_cache = None

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
            if not tags:
                total_images = self.db.get_untagged_image_count_in_folder(self.folder_path)
            else:
                total_images = self.db.get_image_count_in_folder(self.folder_path, tags)
            self.total_pages = (total_images - 1) // self.page_size + 1 if total_images > 0 else 1
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
        if self.current_page < self.total_pages - 1:
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
        if not tags:
            page_items = self.db.get_untagged_images_in_folder_paginated(self.folder_path, self.current_page, self.page_size)
        else:
            page_items = self.db.get_images_in_folder_paginated(self.folder_path, self.current_page, self.page_size, tags)
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
        # Retrieve full path from item data
        model = self.list_view.model()
        item = model.itemFromIndex(index)
        fpath = item.data(Qt.UserRole + 1)
        if fpath:
            # Show only the basename in the message box
            QMessageBox.information(self, "Filename", os.path.basename(fpath))

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.current_page = 0
            # Only scan if not previously scanned
            if not self.db.was_directory_scanned(folder):
                self.show_loading_dialog("Scanning for images and tags...")
                self.worker = ScanWorker(folder, self.db.db_path, self.is_valid_tag)
                self.worker.scan_finished.connect(self.on_scan_finished)
                self.worker.start()
            else:
                self.update_pagination()
                self.show_current_page()

    def on_scan_finished(self):
        if self.folder_path:
            self.db.mark_directory_scanned(self.folder_path)
        self.hide_loading_dialog()
        self.load_previous_tags()
        self.update_search()
        self.update_tags_search()  # Refresh tag search after scan

    def save_tags_to_file_and_db(self, show_dialogs=False):
        """
        Save the current IPTC input pane tags to both the tag database and the image file (if any).
        If show_dialogs is True, show user dialogs for errors/success. If False, suppress dialogs.
        """
        if not self.current_image_path:
            return
        raw_input = self.iptc_text_edit.toPlainText().strip()
        if not raw_input:
            # If empty, clear tags in DB and file
            self.db.set_image_tags(self.current_image_path, [])
            # Remove all IPTC keywords from file
            subprocess.run(
                f'exiv2 -M "del Iptc.Application2.Keywords" "{self.current_image_path}"',
                shell=True,
                capture_output=True,
                text=True,
            )
            return
        keywords = [kw.strip() for kw in raw_input.splitlines() if kw.strip()]
        # Validate tags
        invalid_tags = [kw for kw in keywords if not self.is_valid_tag(kw)]
        if invalid_tags:
            if show_dialogs:
                QMessageBox.critical(
                    self,
                    "Invalid Tag(s)",
                    f"Invalid tag(s) found: {', '.join(invalid_tags)}. Tags must be alphanumeric or dashes only.",
                )
            return
        # Remove all IPTC keywords from file
        subprocess.run(
            f'exiv2 -M "del Iptc.Application2.Keywords" "{self.current_image_path}"',
            shell=True,
            capture_output=True,
            text=True,
        )
        # Add each keyword
        commands = [f'-M "add Iptc.Application2.Keywords {shlex.quote(kw)}"' for kw in keywords]
        full_cmd = f'exiv2 {" ".join(commands)} "{self.current_image_path}"'
        subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True
        )
        # Save to DB
        self.db.set_image_tags(self.current_image_path, keywords)

    def save_iptc(self):
        self.save_tags_to_file_and_db(show_dialogs=True)
        self.last_loaded_keywords = self.iptc_text_edit.toPlainText().strip()
        self.load_previous_tags()
        self.update_tags_search()

    def image_selected(self, index):
        # Check if there are unsaved changes before switching images
        current_input = self.iptc_text_edit.toPlainText().strip()
        if hasattr(self, 'last_loaded_keywords') and self.current_image_path is not None:
            if current_input != self.last_loaded_keywords:
                reply = QMessageBox.question(
                    self,
                    "Save Changes?",
                    "You have unsaved changes to the tags. Save before switching images?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                if reply == QMessageBox.Cancel:
                    return  # Don't switch images
                elif reply == QMessageBox.Yes:
                    self.save_tags_to_file_and_db(show_dialogs=True)
                # If No, discard changes and continue
        self.load_previous_tags()
        self.update_tags_search()
        selected_index = index.row()
        if selected_index < 0 or selected_index >= len(self.image_list):
            return
        image_path = self.image_list[selected_index]
        self.current_image_path = image_path
        self._preview_rotation_angle = 0
        self.display_image(self.current_image_path)
        self.extract_keywords()
        self.iptc_text_edit.setPlainText("\n".join(self.cleaned_keywords))
        self.last_loaded_keywords = self.iptc_text_edit.toPlainText().strip()

    def display_image(self, path):
        try:
            FILESIZE_THRESHOLD = 25 * 1024 * 1024  # 25MB
            file_size = os.path.getsize(path)
            ext = os.path.splitext(path)[1].lower()
            if file_size > FILESIZE_THRESHOLD or ext in ['.tif', '.tiff']:
                from PIL import Image
                from PySide6.QtGui import QImage
                import io
                pil_img = Image.open(path)
                # Always use first frame for multi-page TIFFs
                if hasattr(pil_img, 'n_frames') and pil_img.n_frames > 1:
                    pil_img.seek(0)
                max_dim = 2000
                if pil_img.width > max_dim or pil_img.height > max_dim:
                    pil_img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                # Apply rotation if needed
                if hasattr(self, '_preview_rotation_angle') and self._preview_rotation_angle:
                    pil_img = pil_img.rotate(-self._preview_rotation_angle, expand=True)
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                qimg = QImage.fromData(buf.getvalue())
                pixmap = QPixmap.fromImage(qimg)
            else:
                pixmap = QPixmap(path)
                if hasattr(self, '_preview_rotation_angle') and self._preview_rotation_angle:
                    from PySide6.QtGui import QTransform
                    transform = QTransform().rotate(self._preview_rotation_angle)
                    pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
            pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open image: {e}\nType: {type(e)}")

    def load_previous_tags(self):
        # Load unique keywords from the SQLite database and populate the list widget.
        self.all_tags = self.db.get_tags()
        self.update_tags_list_widget(self.all_tags)

    def update_tags_list_widget(self, tags):
        # Sort tags alphabetically before displaying
        sorted_tags = sorted(tags, key=lambda t: t.lower())
        self.tags_list_widget.clear()
        for tag in sorted_tags:
            self.tags_list_widget.addItem(tag)

    def update_tags_search(self):
        # Get search text, filter tags, and update the list widget
        search_text = self.tags_search_bar.toPlainText().strip().lower()
        if not hasattr(self, "all_tags"):
            self.all_tags = self.db.get_tags()
        if not search_text:
            filtered = self.all_tags
        else:
            filtered = [tag for tag in self.all_tags if search_text in tag.lower()]
        self.update_tags_list_widget(filtered)

    def tag_clicked(self, index):
        # Get the text of the clicked tag.
        tag = self.tags_list_widget.currentItem().text()
        # Get the current content of the text edit.
        current_text = self.iptc_text_edit.toPlainText().strip()
        # If there is existing text, append a space (or a newline, or a comma) and then the new tag.
        if current_text:
            # Here we append with a new line; you can customize to use a comma, space, etc.
            new_text = f"{current_text}\n{tag}"
        else:
            new_text = tag
        self.iptc_text_edit.setPlainText(new_text)

    def extract_keywords(self):
        # Extract keywords from exiv2 output.
        result = subprocess.run(
            ["exiv2", "-pi", self.current_image_path], capture_output=True, text=True
        )
        if result.returncode != 0:
            print("Error reading IPTC data:", result.stderr)
            self.cleaned_keywords = []
            return
        keywords = []
        # Use the split-by-multiple-spaces approach.
        for line in result.stdout.splitlines():
            if "Iptc.Application2.Keywords" in line:
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 4:
                    keyword_value = parts[-1].strip()
                    keywords.append(keyword_value)
        self.cleaned_keywords = keywords

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
        self.loading_dialog.setFixedSize(300, 120)
        self.loading_dialog.show()
        QApplication.processEvents()

    def hide_loading_dialog(self):
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None

    def scan_directory(self):
        if not self.folder_path:
            QMessageBox.warning(
                self, "No Folder Selected", "Please select a folder first."
            )
            return
        self.show_loading_dialog()
        # Remove missing images from DB before rescanning
        self.db.remove_missing_images(self.folder_path)
        # Pass db_path instead of db instance, and use the correct attribute
        self.worker = ScanWorker(self.folder_path, self.db.db_path, self.is_valid_tag)
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())
