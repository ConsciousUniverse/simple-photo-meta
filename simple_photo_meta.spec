# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Simple Photo Meta

Cross-platform: macOS (arm64, x86_64), Linux (x86_64, arm64)

Build commands:
    macOS:  pyinstaller simple_photo_meta.spec
    Linux:  pyinstaller simple_photo_meta.spec
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Detect platform
is_macos = sys.platform == "darwin"
is_linux = sys.platform.startswith("linux")

block_cipher = None

# Project paths
PROJECT_ROOT = Path(SPECPATH)
BACKEND_DIR = PROJECT_ROOT / "backend"

# Collect Django and DRF data files
datas = [
    # Django templates
    (str(BACKEND_DIR / "templates"), "templates"),
    # Static files
    (str(PROJECT_ROOT / "frontend" / "static"), "static"),
    # Django apps
    (str(BACKEND_DIR / "api"), "api"),
    (str(BACKEND_DIR / "spm_backend"), "spm_backend"),
]

# Collect tag definition files
datas.append((str(PROJECT_ROOT / "simple_photo_meta" / "iptc_tags.py"), "simple_photo_meta"))
datas.append((str(PROJECT_ROOT / "simple_photo_meta" / "exif_tags.py"), "simple_photo_meta"))

# Find the compiled exiv2bind module
for ext in [".so", ".pyd", ".dylib"]:
    pattern = f"exiv2bind*.cpython-*{ext}"
    for path in (PROJECT_ROOT / "simple_photo_meta").glob(pattern):
        datas.append((str(path), "simple_photo_meta"))
        break

# Hidden imports for Django
hiddenimports = [
    "django",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.core.management",
    "django.core.servers.basehttp",
    "django.core.handlers.wsgi",
    "django.template.backends.django",
    "django.template.context_processors",
    "rest_framework",
    "corsheaders",
    "corsheaders.middleware",
    "appdirs",
    "PIL",
    "PIL.Image",
    "pillow_heif",
    "api",
    "api.models",
    "api.views",
    "api.serializers",
    "api.urls",
    "api.services",
    "api.services.metadata_service",
    "api.services.image_service",
    "api.services.scan_service",
    "spm_backend",
    "spm_backend.settings",
    "spm_backend.urls",
    "spm_backend.wsgi",
    "simple_photo_meta",
    "simple_photo_meta.exiv2bind",
    "simple_photo_meta.iptc_tags",
    "simple_photo_meta.exif_tags",
]

# Collect all Django submodules
hiddenimports += collect_submodules("django")
hiddenimports += collect_submodules("rest_framework")
hiddenimports += collect_submodules("corsheaders")

# Platform-specific pywebview backend
if is_macos:
    hiddenimports += [
        "webview",
        "webview.platforms.cocoa",
        "objc",
        "AppKit",
        "Foundation",
        "WebKit",
    ]
elif is_linux:
    hiddenimports += [
        "webview",
        "webview.platforms.gtk",
        "gi",
        "gi.repository.Gtk",
        "gi.repository.Gdk",
        "gi.repository.GLib",
        "gi.repository.WebKit2",
    ]

a = Analysis(
    ["launcher.py"],
    pathex=[str(PROJECT_ROOT), str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6",
        "PyQt5",
        "PyQt6",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SimplePhotoMeta",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SimplePhotoMeta",
)

# macOS: Create .app bundle
if is_macos:
    app = BUNDLE(
        coll,
        name="SimplePhotoMeta.app",
        icon=str(PROJECT_ROOT / "icons" / "SimplePhotoMeta.icns") if (PROJECT_ROOT / "icons" / "SimplePhotoMeta.icns").exists() else None,
        bundle_identifier="com.zaziork.simplephotoMeta",
        info_plist={
            "CFBundleName": "Simple Photo Meta",
            "CFBundleDisplayName": "Simple Photo Meta",
            "CFBundleVersion": "2.0.0",
            "CFBundleShortVersionString": "2.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "NSRequiresAquaSystemAppearance": False,  # Support dark mode
        },
    )
