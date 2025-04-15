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
    QListView, QAbstractItemView
)
from PySide6.QtGui import QPixmap, QIcon, QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer


class TagDatabase:
    def __init__(self, db_path="tags.db"):
        # Connect to the database file (it will be created in the current directory)
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        c = self.conn.cursor()
        # The 'tag' field is UNIQUE so that duplicate tags are ignored
        c.execute(
            "CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT UNIQUE)"
        )
        self.conn.commit()

    def add_tag(self, tag):
        try:
            c = self.conn.cursor()
            c.execute("INSERT OR IGNORE INTO tags (tag) VALUES (?)", (tag,))
            self.conn.commit()
        except Exception as e:
            print("Error inserting tag", tag, e)

    def get_tags(self):
        c = self.conn.cursor()
        c.execute("SELECT tag FROM tags ORDER BY tag ASC")
        return [row[0] for row in c.fetchall()]


# (Include the TagDatabase class from above here)
class TagDatabase:
    def __init__(self, db_path="tags.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        c = self.conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT UNIQUE)"
        )
        self.conn.commit()

    def add_tag(self, tag):
        try:
            c = self.conn.cursor()
            c.execute("INSERT OR IGNORE INTO tags (tag) VALUES (?)", (tag,))
            self.conn.commit()
        except Exception as e:
            print("Error inserting tag", tag, e)

    def get_tags(self):
        c = self.conn.cursor()
        c.execute("SELECT tag FROM tags ORDER BY tag ASC")
        return [row[0] for row in c.fetchall()]


class IPTCEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTC Editor")
        self.folder_path = ""
        self.image_list = []
        self.current_image_path = None
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

        # LEFT PANEL: folder and image list, plus previously used tags.
        left_panel = QVBoxLayout()
        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        left_panel.addWidget(self.btn_select_folder)

        # Replace QListWidget with QListView for thumbnails
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.IconMode)
        self.list_view.setIconSize(QPixmap(80, 80).size())
        self.list_view.setResizeMode(QListView.Adjust)
        self.list_view.setSpacing(10)
        self.list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_view.setMovement(QListView.Static)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setMinimumHeight(200)
        self.list_view.setMinimumWidth(200)
        self.list_view.clicked.connect(self.image_selected)
        left_panel.addWidget(self.list_view)

        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setMaximumHeight(150)
        self.tags_list_widget.setToolTip("Click on a tag to insert it into the input")
        self.tags_list_widget.clicked.connect(self.tag_clicked)
        left_panel.addWidget(self.tags_list_widget)

        main_layout.addLayout(left_panel, 1)

        # RIGHT PANEL: image display and IPTC metadata editor.
        right_panel = QVBoxLayout()

        # Canvas for image display
        self.image_label = QLabel("Image preview will appear here")
        self.image_label.setFixedSize(500, 400)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: gray;")
        right_panel.addWidget(self.image_label)

        # Text edit for IPTC data input
        self.iptc_text_edit = QTextEdit()
        right_panel.addWidget(self.iptc_text_edit)

        # Buttons for reading and saving IPTC data
        btn_layout = QHBoxLayout()
        self.btn_read = QPushButton("Read IPTC")
        self.btn_read.clicked.connect(self.read_iptc)
        btn_layout.addWidget(self.btn_read)

        self.btn_save = QPushButton("Save IPTC")
        self.btn_save.clicked.connect(self.save_iptc)
        btn_layout.addWidget(self.btn_save)
        right_panel.addLayout(btn_layout)

        main_layout.addLayout(right_panel, 2)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.populate_listbox()

    def populate_listbox(self):
        # Now populates the QListView with thumbnails and filenames
        supported = (".jpg", ".jpeg", ".png")
        self.image_list = [
            f for f in os.listdir(self.folder_path) if f.lower().endswith(supported)
        ]
        model = QStandardItemModel()
        for fname in self.image_list:
            fpath = os.path.join(self.folder_path, fname)
            pixmap = QPixmap(fpath)
            if pixmap.isNull():
                icon = QIcon()
            else:
                icon = QIcon(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            item = QStandardItem(icon, fname)
            item.setEditable(False)
            model.appendRow(item)
        self.list_view.setModel(model)

    def image_selected(self, index):
        selected_index = index.row()
        if selected_index < 0:
            return
        image_name = self.image_list[selected_index]
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

        # First, delete existing IPTC keywords
        try:
            delete_result = subprocess.run(
                f'exiv2 -M "del Iptc.Application2.Keywords" "{self.current_image_path}"',
                shell=True,
                capture_output=True,
                text=True,
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
                    self.db.add_tag(kw)
                self.load_previous_tags()  # Refresh the list of previous tags.
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())
