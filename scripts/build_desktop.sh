#!/bin/bash
#
# Build Simple Photo Meta Desktop App
# 
# Creates a standalone application using PyInstaller + pywebview
# Works on macOS and Linux
#
# Usage:
#   ./scripts/build_desktop.sh          # Build for current platform
#   ./scripts/build_desktop.sh --clean  # Clean build (remove previous)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/dist"

echo "========================================"
echo "  Simple Photo Meta - Desktop Build"
echo "========================================"
echo ""

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
    PYWEBVIEW_DEPS=""
elif [[ "$OSTYPE" == "linux"* ]]; then
    PLATFORM="Linux"
    PYWEBVIEW_DEPS="PyGObject"
else
    echo "Error: Unsupported platform: $OSTYPE"
    exit 1
fi

echo "Platform: $PLATFORM"
echo ""

# Clean if requested
if [[ "$1" == "--clean" ]]; then
    echo "Cleaning previous builds..."
    rm -rf "$PROJECT_DIR/dist"
    rm -rf "$PROJECT_DIR/build"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Create/activate virtual environment
if [ ! -d "$PROJECT_DIR/.venv-build" ]; then
    echo "Creating build virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv-build"
fi

source "$PROJECT_DIR/.venv-build/bin/activate"

echo "Installing build dependencies..."

# Install core dependencies
pip install -q --upgrade pip wheel

# Install pywebview with platform-specific backend
if [[ "$PLATFORM" == "macOS" ]]; then
    pip install -q 'pywebview>=5.0' pyobjc-framework-WebKit
elif [[ "$PLATFORM" == "Linux" ]]; then
    echo "Note: On Linux, you need system packages installed:"
    echo "  Ubuntu/Debian: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1"
    echo "  Fedora: sudo dnf install python3-gobject gtk3 webkit2gtk3"
    echo ""
    pip install -q 'pywebview>=5.0'
fi

# Install Django and other dependencies
pip install -q fastapi uvicorn pillow pillow-heif appdirs

# Install PyInstaller
pip install -q pyinstaller

# Build C++ bindings if needed
cd "$PROJECT_DIR"
if ! python -c "from simple_photo_meta.exiv2bind import Exiv2Bind" 2>/dev/null; then
    echo "Building C++ metadata bindings..."
    pip install -q pybind11
    pip install -e .
fi

echo ""
echo "Running PyInstaller..."
echo ""

# Run PyInstaller with the spec file
cd "$PROJECT_DIR"
pyinstaller --noconfirm simple_photo_meta.spec

echo ""
echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""

if [[ "$PLATFORM" == "macOS" ]]; then
    echo "Output: $BUILD_DIR/SimplePhotoMeta.app"
    echo ""
    echo "To create a DMG installer:"
    echo "  ./scripts/create_dmg.sh"
    echo ""
    echo "To run:"
    echo "  open $BUILD_DIR/SimplePhotoMeta.app"
else
    echo "Output: $BUILD_DIR/SimplePhotoMeta/"
    echo ""
    echo "To create an AppImage:"
    echo "  ./scripts/create_appimage.sh"
    echo ""
    echo "To run:"
    echo "  $BUILD_DIR/SimplePhotoMeta/SimplePhotoMeta"
fi
