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
    rm -rf "$PROJECT_DIR/.venv-build"
    rm -rf "$PROJECT_DIR/simple_photo_meta.egg-info"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Create/activate virtual environment
# On Linux, use --system-site-packages to access GTK/GObject bindings
if [ ! -d "$PROJECT_DIR/.venv-build" ]; then
    echo "Creating build virtual environment..."
    if [[ "$PLATFORM" == "Linux" ]]; then
        python3 -m venv --system-site-packages "$PROJECT_DIR/.venv-build"
    else
        python3 -m venv "$PROJECT_DIR/.venv-build"
    fi
fi

source "$PROJECT_DIR/.venv-build/bin/activate"

echo "Installing build dependencies..."

# Install core dependencies
pip install -q --upgrade pip wheel

# Install pywebview with platform-specific backend
if [[ "$PLATFORM" == "macOS" ]]; then
    pip install -q 'pywebview>=5.0' pyobjc-framework-WebKit
elif [[ "$PLATFORM" == "Linux" ]]; then
    # Check for required GTK/WebKit system packages (use /usr/bin/python3 to check system packages)
    if ! /usr/bin/python3 -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.1')" 2>/dev/null; then
        echo "Error: Missing required system packages for pywebview on Linux."
        echo ""
        echo "Install with:"
        echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1"
        echo ""
        echo "Or on Fedora:"
        echo "  sudo dnf install python3-gobject gtk3 webkit2gtk3"
        exit 1
    fi
    
    pip install -q 'pywebview>=5.0'
fi

# Install FastAPI and other dependencies
pip install -q fastapi uvicorn pillow pillow-heif appdirs

# Install PyInstaller
pip install -q pyinstaller

# Build C++ bindings if needed
cd "$PROJECT_DIR"
if ! python -c "from simple_photo_meta.exiv2bind import Exiv2Bind" 2>/dev/null; then
    echo "Building C++ metadata bindings..."
    pip install -q pybind11 setuptools
    python setup.py build_ext --inplace
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
