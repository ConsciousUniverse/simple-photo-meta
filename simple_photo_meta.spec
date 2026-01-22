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

# Collect data files for FastAPI backend
datas = [
    # Templates
    (str(BACKEND_DIR / "templates"), "templates"),
    # Static files
    (str(PROJECT_ROOT / "frontend" / "static"), "static"),
    # Backend modules
    (str(BACKEND_DIR / "config.py"), "."),
    (str(BACKEND_DIR / "database.py"), "."),
    (str(BACKEND_DIR / "main.py"), "."),
    (str(BACKEND_DIR / "services"), "services"),
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

# Hidden imports for FastAPI/uvicorn
hiddenimports = [
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.staticfiles",
    "fastapi.responses",
    "starlette",
    "starlette.routing",
    "starlette.middleware",
    "uvicorn",
    "uvicorn.config",
    "uvicorn.main",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    "pydantic",
    "anyio",
    "anyio._backends",
    "anyio._backends._asyncio",
    "appdirs",
    "PIL",
    "PIL.Image",
    "pillow_heif",
    "config",
    "database",
    "main",
    "services",
    "services.image_service",
    "services.metadata_service",
    "services.scan_service",
    "simple_photo_meta",
    "simple_photo_meta.exiv2bind",
    "simple_photo_meta.iptc_tags",
    "simple_photo_meta.exif_tags",
]

# Collect all FastAPI/uvicorn submodules
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("uvicorn")

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
