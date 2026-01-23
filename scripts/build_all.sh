#!/bin/bash
#
# Build All - Complete build for Simple Photo Meta
#
# This script performs a complete build:
#   1. Builds C++ Exiv2 bindings
#   2. Builds standalone desktop app with PyInstaller
#   3. Creates platform-specific installer (DMG on macOS, AppImage on Linux)
#
# Usage:
#   ./scripts/build_all.sh          # Full build
#   ./scripts/build_all.sh --clean  # Clean build (removes previous artifacts)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "  Simple Photo Meta - Full Build"
echo "========================================"
echo ""

# Handle --clean flag
if [[ "$1" == "--clean" ]]; then
    CLEAN_FLAG="--clean"
    echo "Clean build requested"
    echo ""
    
    # Clean up stale environments and build artifacts
    cd "$SCRIPT_DIR/.."
    rm -rf .venv .venv-build simple_photo_meta.egg-info build/ dist/
    echo "Cleaned: .venv, .venv-build, egg-info, build/, dist/"
    echo ""
else
    CLEAN_FLAG=""
fi

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
elif [[ "$OSTYPE" == "linux"* ]]; then
    PLATFORM="Linux"
else
    echo "Error: Unsupported platform: $OSTYPE"
    exit 1
fi

echo "Platform: $PLATFORM"
echo ""

# Step 1: Build C++ bindings
echo "Step 1/3: Building C++ bindings..."
"$SCRIPT_DIR/build_bindings.sh" $CLEAN_FLAG
echo ""

# Step 2: Build desktop app
echo "Step 2/3: Building desktop app..."
"$SCRIPT_DIR/build_desktop.sh" $CLEAN_FLAG
echo ""

# Step 3: Create installer
echo "Step 3/3: Creating installer..."
if [[ "$PLATFORM" == "macOS" ]]; then
    "$SCRIPT_DIR/create_dmg.sh"
else
    "$SCRIPT_DIR/create_appimage.sh"
fi

echo ""
echo "========================================"
echo "  Full Build Complete!"
echo "========================================"
echo ""

if [[ "$PLATFORM" == "macOS" ]]; then
    echo "Outputs:"
    echo "  App:       dist/SimplePhotoMeta.app"
    echo "  Installer: packages/macos/SimplePhotoMeta-*.dmg"
else
    echo "Outputs:"
    echo "  App:       dist/SimplePhotoMeta/"
    echo "  Installer: packages/Linux/SimplePhotoMeta-*.AppImage"
fi
