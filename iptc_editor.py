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
    QListView, QAbstractItemView, QSplitter
)
from PySide6.QtGui import QPixmap, QIcon, QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer


class TagDatabase:
    def __init__(self, db_path="tags.db"):
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

    def get_tags(self):
        c = self.conn.cursor()
        c.execute("SELECT tag FROM tags ORDER BY tag ASC")
        return [row[0] for row in c.fetchall()]

    def get_images_with_tags(self, tags):
        # Incremental search: tags are treated as prefixes (LIKE 'tag%')
        c = self.conn.cursor()
        if not tags:
            c.execute("SELECT path FROM images ORDER BY path ASC")
            return [row[0] for row in c.fetchall()]
        # For each tag fragment, find images that have at least one tag starting with that fragment
        # Build dynamic SQL
        base_query = '''SELECT i.path FROM images i\n'''
        join_clauses = []
        where_clauses = []
        params = []
        for idx, tag in enumerate(tags):
            join_clauses.append(f"JOIN image_tags it{idx} ON i.id = it{idx}.image_id JOIN tags t{idx} ON t{idx}.id = it{idx}.tag_id")
            where_clauses.append(f"t{idx}.tag LIKE ?")
            params.append(f"{tag}%")
        query = base_query + ' '.join(join_clauses)
        if where_clauses:
            query += " WHERE " + ' AND '.join(where_clauses)
        query += " GROUP BY i.id ORDER BY i.path ASC"
        c.execute(query, params)
        return [row[0] for row in c.fetchall()]


class IPTCEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTC Editor")
        self.resize(1920, 1080)  # Set initial window size to 1920px wide
        self.folder_path = ""
        self.image_list = []
        self.current_image_path = None
        self.current_page = 0
        self.page_size = 3
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
        self.search_bar.setMaximumHeight(30)
        self.search_bar.setPlaceholderText("Search by tag(s)...")
        self.search_bar.textChanged.connect(self.update_search)

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
        self.list_view.customContextMenuRequested.connect(self.show_image_filename_context_menu)
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
        center_splitter.addWidget(self.image_label)

        # Container for IPTC text edit and buttons
        iptc_widget = QWidget()
        iptc_layout = QVBoxLayout(iptc_widget)
        iptc_layout.setContentsMargins(0, 0, 0, 0)
        self.iptc_text_edit = QTextEdit()
        self.iptc_text_edit.setFont(font)
        iptc_layout.addWidget(self.iptc_text_edit)
        btn_layout = QHBoxLayout()
        self.btn_read = QPushButton("Read IPTC")
        self.btn_read.setFont(font)
        self.btn_read.clicked.connect(self.read_iptc)
        btn_layout.addWidget(self.btn_read)
        self.btn_save = QPushButton("Save IPTC")
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
        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setFont(font)
        self.tags_list_widget.setToolTip("Click on a tag to insert it into the input")
        self.tags_list_widget.clicked.connect(self.tag_clicked)
        self.tags_list_widget.setStyleSheet("""
            QListWidget::item {
                background: skyblue;
                color: black;
                font-size: 16pt;
                margin-bottom: 7px;
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 32px;
                white-space: pre-wrap;
                word-break: break-word;
            }
            QListWidget::item:selected {
                background: #87ceeb;
                color: yellow;
            }
        """)
        self.tags_list_widget.setWordWrap(True)
        right_panel.addWidget(self.tags_list_widget)
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_panel)
        main_layout.addWidget(right_panel_widget, 1)

    def update_pagination(self):
        if not self.image_list:
            self.current_page = 0
            self.total_pages = 1
        else:
            self.total_pages = (len(self.image_list) - 1) // self.page_size + 1
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
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_items = self.image_list[start:end]
        model = QStandardItemModel()
        for fname in page_items:
            fpath = os.path.join(self.folder_path, fname)
            pixmap = QPixmap(fpath)
            if pixmap.isNull():
                icon = QIcon()
            else:
                icon = QIcon(pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            # Only set icon, not text (no filename shown)
            item = QStandardItem()
            item.setIcon(icon)
            item.setEditable(False)
            # Remove text and set size hint to icon size to avoid extra space
            item.setText("")
            item.setSizeHint(QPixmap(175, 175).size())
            # Store filename in item data for context menu
            item.setData(fname, Qt.UserRole + 1)
            model.appendRow(item)
        self.list_view.setModel(model)
        self.update_pagination()

    def show_image_filename_context_menu(self, pos):
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return
        # Retrieve filename from item data
        model = self.list_view.model()
        item = model.itemFromIndex(index)
        fname = item.data(Qt.UserRole + 1)
        if fname:
            # Show filename in a message box (or could use QToolTip)
            QMessageBox.information(self, "Filename", fname)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.populate_listbox()

    def populate_listbox(self):
        # Now populates the QListView with thumbnails and filenames
        supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")
        self.image_list = [
            f for f in os.listdir(self.folder_path) if f.lower().endswith(supported)
        ]
        self.current_page = 0
        self.update_pagination()
        self.show_current_page()

    def image_selected(self, index):
        # Map the clicked index to the correct image in the current page
        start = self.current_page * self.page_size
        selected_index = index.row()
        if selected_index < 0:
            return
        if start + selected_index >= len(self.image_list):
            return
        image_name = self.image_list[start + selected_index]
        self.current_image_path = os.path.join(self.folder_path, image_name)
        self.read_iptc()
        self.display_image(self.current_image_path)

    def display_image(self, path):
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                raise Exception("Cannot load image")
            pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open image: {e}")

    def load_previous_tags(self):
        # Load unique keywords from the SQLite database and populate the list widget.
        tags = self.db.get_tags()
        self.tags_list_widget.clear()
        for tag in tags:
            self.tags_list_widget.addItem(tag)

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
        return bool(re.fullmatch(r"[A-Za-z0-9\-\s]+", tag))

    def read_iptc(self):
        if not self.current_image_path:
            QMessageBox.warning(
                self, "No Image Selected", "Please select an image first."
            )
            return

        try:
            self.extract_keywords()
            self.iptc_text_edit.setPlainText("\n".join(self.cleaned_keywords))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_iptc(self):
        if not self.current_image_path:
            QMessageBox.warning(
                self, "No Image Selected", "Please select an image first."
            )
            return
        raw_input = self.iptc_text_edit.toPlainText().strip()
        if not raw_input:
            QMessageBox.information(self, "Empty Data", "No IPTC data provided.")
            return

        # Split the input into keywords by line (or comma, if you prefer)
        keywords = [kw.strip() for kw in raw_input.splitlines() if kw.strip()]
        # Validate tags
        invalid_tags = [kw for kw in keywords if not self.is_valid_tag(kw)]
        if invalid_tags:
            QMessageBox.critical(self, "Invalid Tag(s)", f"Invalid tag(s) found: {', '.join(invalid_tags)}. Tags must be alphanumeric or dashes only.")
            return

        # First, delete existing IPTC keywords
        try:
            delete_result = subprocess.run(
                f'exiv2 -M "del Iptc.Application2.Keywords" "{self.current_image_path}"',
                shell=True,
                capture_output=True, text=True,
            )
            if delete_result.returncode != 0:
                QMessageBox.critical(self, "exiv2 Error", delete_result.stderr)
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        # Build and run the command to add each keyword individually
        commands = [
            f'-M "add Iptc.Application2.Keywords {shlex.quote(kw)}"' for kw in keywords
        ]
        full_cmd = f'exiv2 {" ".join(commands)} "{self.current_image_path}"'
        try:
            run_result = subprocess.run(
                full_cmd, shell=True, capture_output=True, text=True
            )
            if run_result.returncode != 0:
                QMessageBox.critical(self, "exiv2 Error", run_result.stderr)
            else:
                self.show_auto_close_message(
                    "Success",
                    "IPTC keywords saved correctly!",
                    QMessageBox.Information,
                    timeout=1000,
                )
                # Save each keyword into our SQLite database.
                for kw in keywords:
                    self.db.add_image_tag(self.current_image_path, kw)
                self.load_previous_tags()  # Refresh the list of previous tags.
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def scan_directory(self):
        if not self.folder_path:
            QMessageBox.warning(self, "No Folder Selected", "Please select a folder first.")
            return
        supported = (".jpg", ".jpeg", ".png")
        # Recursively walk the directory
        for root, dirs, files in os.walk(self.folder_path):
            for fname in files:
                if fname.lower().endswith(supported):
                    fpath = os.path.join(root, fname)
                    # Extract tags for this image
                    result = subprocess.run([
                        "exiv2", "-pi", fpath
                    ], capture_output=True, text=True)
                    if result.returncode != 0:
                        continue
                    for line in result.stdout.splitlines():
                        if "Iptc.Application2.Keywords" in line:
                            parts = re.split(r"\s{2,}", line.strip())
                            if len(parts) >= 4:
                                keyword_value = parts[-1].strip()
                                if self.is_valid_tag(keyword_value):
                                    self.db.add_image_tag(fpath, keyword_value)
        self.show_auto_close_message("Scan Complete", "All images and tags have been added to the database.")
        self.load_previous_tags()
        self.update_search()

    def update_search(self):
        # Get tags from search bar, split by whitespace or comma
        text = self.search_bar.toPlainText().strip()
        tags = [t.strip() for t in re.split(r",|\s", text) if t.strip()]
        if not tags:
            # If no search, show all images in the folder (like populate_listbox)
            supported = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")
            self.image_list = [
                f for f in os.listdir(self.folder_path) if f.lower().endswith(supported)
            ]
        else:
            image_paths = self.db.get_images_with_tags(tags)
            # Only show images in the current folder
            filtered = [f for f in image_paths if os.path.dirname(f) == self.folder_path]
            self.image_list = [os.path.basename(f) for f in filtered]
        self.current_page = 0
        self.update_pagination()
        self.show_current_page()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())
