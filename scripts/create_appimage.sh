#!/bin/bash
#
# Create Linux AppImage for Simple Photo Meta
#
# Prerequisites:
#   - Run build_desktop.sh first
#   - wget or curl
#
# AppImage is a portable Linux app format that runs on most distributions
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/dist/SimplePhotoMeta"
APPIMAGE_DIR="$PROJECT_DIR/packages/Linux"
VERSION="2.0.0"
ARCH=$(uname -m)

echo "========================================"
echo "  Creating AppImage"
echo "========================================"
echo ""

# Check for build
if [ ! -d "$BUILD_DIR" ]; then
    echo "Error: Build not found at $BUILD_DIR"
    echo "Run ./scripts/build_desktop.sh first"
    exit 1
fi

# Create AppImage structure
APPDIR="$PROJECT_DIR/dist/SimplePhotoMeta.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/applications"

echo "Copying files..."

# Copy built application
cp -r "$BUILD_DIR"/* "$APPDIR/usr/bin/"

# Create desktop entry
cat > "$APPDIR/usr/share/applications/simplephotoMeta.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Simple Photo Meta
Comment=Photo metadata editor
Exec=SimplePhotoMeta
Icon=simplephotoMeta
Categories=Graphics;Photography;
Terminal=false
EOF

# Copy desktop entry to AppDir root (required by AppImage)
cp "$APPDIR/usr/share/applications/simplephotoMeta.desktop" "$APPDIR/"

# Copy icon (create a simple one if not exists)
ICON_SRC="$PROJECT_DIR/icons/SimplePhotoMetaIcon.iconset/icon_256x256.png"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/simplephotoMeta.png"
    cp "$ICON_SRC" "$APPDIR/simplephotoMeta.png"
else
    echo "Warning: Icon not found, AppImage will have no icon"
    # Create a placeholder
    touch "$APPDIR/simplephotoMeta.png"
fi

# Create AppRun script
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/SimplePhotoMeta" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Download appimagetool if not present
APPIMAGETOOL="$PROJECT_DIR/dist/appimagetool-$ARCH.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    wget -q -O "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

# Create output directory
mkdir -p "$APPIMAGE_DIR"

# Create AppImage
echo "Building AppImage..."
APPIMAGE_NAME="SimplePhotoMeta-${VERSION}-${ARCH}.AppImage"
ARCH=$ARCH "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_DIR/$APPIMAGE_NAME"

echo ""
echo "========================================"
echo "  AppImage Created Successfully!"
echo "========================================"
echo ""
echo "Output: $APPIMAGE_DIR/$APPIMAGE_NAME"
echo "Size: $(du -h "$APPIMAGE_DIR/$APPIMAGE_NAME" | cut -f1)"
echo ""
echo "To run:"
echo "  chmod +x $APPIMAGE_DIR/$APPIMAGE_NAME"
echo "  ./$APPIMAGE_DIR/$APPIMAGE_NAME"
