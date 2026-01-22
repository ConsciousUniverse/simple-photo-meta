"""
Configuration for Simple Photo Meta FastAPI backend.
"""

import os
import sys
from pathlib import Path
from appdirs import user_data_dir

# Application info
APP_NAME = "SimplePhotoMeta"
APP_AUTHOR = "Zaziork"

# Data directory
DATA_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = DATA_DIR / "spm_web.db"

# Check if running from PyInstaller bundle
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    STATIC_DIR = BUNDLE_DIR / "static"
    TEMPLATES_DIR = BUNDLE_DIR / "templates"
else:
    BASE_DIR = Path(__file__).parent
    STATIC_DIR = BASE_DIR.parent / "frontend" / "static"
    TEMPLATES_DIR = BASE_DIR / "templates"

# Image settings
THUMBNAIL_SIZE = (250, 250)
DEFAULT_PREVIEW_MAX_EDGE = 2048
PREVIEW_CACHE_DIR_NAME = ".previews"
THUMBNAIL_DIR_NAME = ".thumbnails"

# Pagination
DEFAULT_PAGE_SIZE = 25

# Supported image extensions
SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif")
