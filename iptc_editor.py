import os
import subprocess
import sys
import shlex
import re
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
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import sqlite3

class TagDatabase:
    def __init__(self, db_path="tags.db"):
        # Connect to the database file (it will be created in the current directory)
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        c = self.conn.cursor()
        # The 'tag' field is UNIQUE so that duplicate tags are ignored
        c.execute("CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT UNIQUE)")
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
        self.cleaned_keywords = []

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side: Folder selection and list of images
        left_panel = QVBoxLayout()
        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        left_panel.addWidget(self.btn_select_folder)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        left_panel.addWidget(self.list_widget)

        main_layout.addLayout(left_panel, 1)

        # Right side: Image display, IPTC text, and buttons
        right_panel = QVBoxLayout()

        self.image_label = QLabel("Image preview will appear here")
        self.image_label.setFixedSize(500, 400)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: gray;")
        right_panel.addWidget(self.image_label)

        self.iptc_text_edit = QTextEdit()
        right_panel.addWidget(self.iptc_text_edit)

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
        """Opens a dialog to select a folder containing images."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.populate_list()

    def populate_list(self):
        """Populates the list widget with image filenames (supports .jpg, .jpeg, .png)."""
        self.list_widget.clear()
        supported = (".jpg", ".jpeg", ".png")
        self.image_list = [
            f for f in os.listdir(self.folder_path) if f.lower().endswith(supported)
        ]
        self.list_widget.addItems(self.image_list)

    def on_item_clicked(self, item):
        """Loads and displays the selected image."""
        image_name = item.text()
        self.current_image_path = os.path.join(self.folder_path, image_name)
        self.display_image(self.current_image_path)

    def display_image(self, path):
        """Displays an image on the QLabel, scaled to fit."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", f"Could not load image: {path}")
            return
        pixmap = pixmap.scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)

    def extract_keywords(self):
        # Run exiv2 to get IPTC data from the image.
        result = subprocess.run(
            ["exiv2", "-pi", self.current_image_path], capture_output=True, text=True
        )
        if result.returncode != 0:
            print("Error reading IPTC data:", result.stderr)
            self.cleaned_keywords = []
            return
        keywords = []
        for line in result.stdout.splitlines():
            # Process only lines with the Keywords tag.
            if "Iptc.Application2.Keywords" in line:
                # Split on two or more consecutive whitespace characters.
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 4:
                    # The last part holds the actual keyword value.
                    keyword_value = parts[-1].strip()
                    keywords.append(keyword_value)
                else:
                    print("DEBUG: Unexpected format:", line)
        self.cleaned_keywords = keywords

    def read_iptc(self):
        """
        Reads IPTC metadata from the current image using exiv2,
        extracts only the keyword values, and displays them in the text edit.
        """
        if not self.current_image_path:
            QMessageBox.warning(
                self, "No Image Selected", "Please select an image first."
            )
            return
        try:
            self.extract_keywords()
            # Display each keyword on its own line
            self.iptc_text_edit.setPlainText("\n".join(self.cleaned_keywords))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_iptc(self):
        """
        Saves IPTC metadata (multiple keywords) to the current image using exiv2.
        Deletes all existing keywords, then adds each one individually to avoid
        combining them into a single entry.
        """
        if not self.current_image_path:
            QMessageBox.warning(
                self, "No Image Selected", "Please select an image first."
            )
            return
        raw_input = self.iptc_text_edit.toPlainText().strip()
        if not raw_input:
            QMessageBox.information(self, "Empty Data", "No IPTC data provided.")
            return
        # Split keywords by lines or comma depending what's better; here it's lines
        keywords = [kw.strip() for kw in raw_input.splitlines() if kw.strip()]
        try:
            # delete exising
            delete_result = subprocess.run(
                f'exiv2 -M "del Iptc.Application2.Keywords" "{self.current_image_path}"',
                shell=True,
                capture_output=True,
                text=True,
            )
            if delete_result.returncode != 0:
                QMessageBox.critical(self, "exiv2 Error", run_result.stderr)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        # Build the command with one `add` per keyword
        commands = [
            f'-M "add Iptc.Application2.Keywords {shlex.quote(kw.strip())}"'
            for kw in keywords
        ]
        full_cmd = f'exiv2 {" ".join(commands)} "{self.current_image_path}"'
        try:
            run_result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
            )
            if run_result.returncode != 0:
                QMessageBox.critical(self, "exiv2 Error", run_result.stderr)
            else:
                QMessageBox.information(
                    self, "Success", "IPTC keywords saved correctly!"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPTCEditor()
    window.show()
    sys.exit(app.exec())
