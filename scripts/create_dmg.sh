#!/bin/bash
#
# Create macOS DMG installer for Simple Photo Meta
#
# Prerequisites:
#   brew install create-dmg
#
# Run build_desktop.sh first to create the .app bundle
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_PATH="$PROJECT_DIR/dist/SimplePhotoMeta.app"
DMG_DIR="$PROJECT_DIR/packages/macos"
VERSION="2.0.0"

echo "========================================"
echo "  Creating DMG Installer"
echo "========================================"
echo ""

# Check for app bundle
if [ ! -d "$APP_PATH" ]; then
    echo "Error: App bundle not found at $APP_PATH"
    echo "Run ./scripts/build_desktop.sh first"
    exit 1
fi

# Check for create-dmg
if ! command -v create-dmg &> /dev/null; then
    echo "Installing create-dmg..."
    brew install create-dmg
fi

# Create output directory
mkdir -p "$DMG_DIR"

# Remove old DMG if exists
DMG_NAME="SimplePhotoMeta-${VERSION}.dmg"
rm -f "$DMG_DIR/$DMG_NAME"

echo "Creating DMG..."

create-dmg \
    --volname "Simple Photo Meta" \
    --volicon "$PROJECT_DIR/icons/SimplePhotoMeta.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "SimplePhotoMeta.app" 150 190 \
    --hide-extension "SimplePhotoMeta.app" \
    --app-drop-link 450 185 \
    --no-internet-enable \
    "$DMG_DIR/$DMG_NAME" \
    "$APP_PATH" \
    2>/dev/null || true  # create-dmg returns non-zero even on success sometimes

# Verify DMG was created
if [ -f "$DMG_DIR/$DMG_NAME" ]; then
    echo ""
    echo "========================================"
    echo "  DMG Created Successfully!"
    echo "========================================"
    echo ""
    echo "Output: $DMG_DIR/$DMG_NAME"
    echo "Size: $(du -h "$DMG_DIR/$DMG_NAME" | cut -f1)"
else
    echo "Error: Failed to create DMG"
    exit 1
fi
