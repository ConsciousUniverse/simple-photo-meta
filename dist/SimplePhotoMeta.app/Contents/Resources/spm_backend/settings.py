"""
Django settings for Simple Photo Meta backend.
This is a local-only application - no remote server needed.
"""

import os
from pathlib import Path
from appdirs import user_data_dir

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Application data directory (same location as before)
APP_NAME = "SimplePhotoMeta"
APP_AUTHOR = "Zaziork"
DATA_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
# For local-only app, we generate a random key on first run and store it
SECRET_KEY_FILE = DATA_DIR / ".secret_key"
if SECRET_KEY_FILE.exists():
    SECRET_KEY = SECRET_KEY_FILE.read_text().strip()
else:
    from django.core.management.utils import get_random_secret_key
    SECRET_KEY = get_random_secret_key()
    SECRET_KEY_FILE.write_text(SECRET_KEY)

# SECURITY WARNING: This is a LOCAL-ONLY application
# Only allow localhost connections
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

# CORS settings - allow local frontend
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]
CORS_ALLOW_ALL_ORIGINS = False

ROOT_URLCONF = 'spm_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'spm_backend.wsgi.application'

# Database - SQLite stored in user data directory
# Use a new database file to avoid conflicts with the old Qt app
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'spm_web.db',
    }
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Check if running from PyInstaller bundle
import sys
if getattr(sys, 'frozen', False):
    # Running as bundled app
    BUNDLE_DIR = Path(sys._MEIPASS)
    STATICFILES_DIRS = [
        BUNDLE_DIR / 'static',
    ]
    TEMPLATES[0]['DIRS'] = [BUNDLE_DIR / 'templates']
else:
    # Running in development
    STATICFILES_DIRS = [
        BASE_DIR.parent / 'frontend' / 'static',
    ]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'UNAUTHENTICATED_USER': None,
}

# Thumbnail and preview cache settings
PREVIEW_CACHE_DIR_NAME = ".previews"
THUMBNAIL_DIR_NAME = ".thumbnails"
DEFAULT_PREVIEW_MAX_EDGE = 2048
THUMBNAIL_SIZE = (250, 250)

# Pagination
DEFAULT_PAGE_SIZE = 25
