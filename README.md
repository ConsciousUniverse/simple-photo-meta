# Simple Photo Meta (Alpha)

A local desktop application for viewing and editing IPTC and EXIF metadata in image files. The app provides a browser-based UI while running entirely on your local machine—no remote server required.

This software is written in Python 3.13 with a FastAPI backend and plain HTML/CSS/JavaScript frontend. It is powered by the excellent [Exiv2 metadata library](https://github.com/exiv2/exiv2) via custom C++ bindings.

This software was written for macOS (Apple Silicon) and Linux. It is untested on Windows.

## ⚠️ Currently Potentially Unsafe - Use with Caution

This is an Alpha version of this software, and as such is made available for testing purposes only. It is unsafe to use on valuable images - please do not test on the only copy of your most cherished photos as they may be destroyed!

## Download Binaries (Mac and Linux)

Binaries of the latest version may be downloaded from the [releases page here on GitHub](https://github.com/ConsciousUniverse/simple-photo-meta/releases). The macOS (Apple Silicon) version is available as a .dmg, while the Linux version is available as an AppImage.

Note, the .dmg for Mac is not signed, as this is an alpha testing version. Therefore, the OS will report the binary is "broken", due to it being blocked by Gatekeeper. You will need to run a command to get it through Gatekeeper; see installation instructions below.

## What's New in Version 2.0

Version 2.0 is a complete rewrite of the application architecture:

- **Web-based UI**: Now uses a browser-based interface powered by FastAPI, replacing the previous Qt/PySide6 GUI
- **Plain JavaScript**: No JavaScript frameworks - minimal maintenance burden and no npm dependencies
- **Lightweight backend**: FastAPI instead of heavier frameworks, with raw SQLite queries for simplicity
- **Native window**: Uses pywebview to provide a native application window (WebKit on macOS, GTK/WebKit on Linux)
- **System theme support**: UI now respects your OS light/dark theme settings
- **Same powerful metadata engine**: Still uses the proven Exiv2 C++ bindings for reliable metadata handling

## Produced Using AI

This version was produced with the considerable assistance of artificial intelligence. The code works, and works well, but is not a thing of beauty. It is likely bloated and not as efficient as it could be. For that reason, it should not be used to train future AI models.

## Features

### Metadata Support

- **IPTC Tags**: Full support for standard IPTC fields including Keywords, Caption, Copyright, Creator, City, Country, and more
- **EXIF Tags**: Edit EXIF fields including Artist, Copyright, ImageDescription, UserComment, Camera Make/Model, DateTime fields, exposure settings (ISO, aperture, shutter speed), GPS coordinates, lens information, and more
- **Format Switching**: Seamlessly switch between IPTC and EXIF tag types with dedicated dropdown selectors
- **Multi-valued Tags**: Support for tags that can contain multiple values (e.g., Keywords, Supplemental Categories)
- **Single-valued Tags**: Appropriate handling of single-value fields (e.g., Caption, Copyright, DateTime)

### Image Management

- **Directory Browsing**: Open directories and recursively scan subdirectories for images
- **Pagination**: Navigate through large image collections with paginated thumbnail view (25 images per page)
- **Image Formats**: Support for JPEG, PNG, TIFF, HEIC/HEIF (requires pillow-heif)
- **Thumbnail Caching**: Fast thumbnail generation with intelligent caching for improved performance
- **Preview Caching**: High-resolution preview caching for large images and HEIC/HEIF files
- **Smart Preview Sizing**: Automatic preview size optimization based on file size and format

### Search & Discovery

- **Real-time Search**: Instant search across all images by metadata tag value
- **Tag Discovery**: Automatically discover and catalog all existing metadata tags in your collection
- **Tag Library Search**: Filter the discovered tag library with real-time search
- **Metadata Type Filtering**: Search within specific IPTC or EXIF fields

### Editing Features

- **Visual Tag Editor**: Clean, card-based interface for managing tags
- **Autocomplete**: Smart tag suggestions from your discovered tag library while typing
- **One-click Delete**: Remove tags with a single click
- **Auto-save**: Tags save immediately on add/remove - no explicit save button needed
- **Unsaved Changes Detection**: Automatic prompts when switching images or tag types
- **Input Validation**: Ensures tags meet format requirements

### Performance & UX

- **Background Threading**: Non-blocking metadata operations
- **Optimized Caching**: Thumbnail and preview caching for instant navigation
- **Responsive UI**: Smooth interface even with large image collections
- **Error Handling**: Graceful handling of corrupted files and unsupported formats
- **SQLite Database**: Fast local metadata indexing for quick searches

## Technology Stack

| Component        | Technology                                       |
| ---------------- | ------------------------------------------------ |
| Backend          | Python 3.13, FastAPI, uvicorn                    |
| Frontend         | Plain HTML, CSS, JavaScript (no frameworks)      |
| Database         | SQLite (raw queries, no ORM)                     |
| Metadata Engine  | C++ Exiv2 library via pybind11 bindings          |
| Image Processing | Pillow, pillow-heif                              |
| Desktop Wrapper  | pywebview (WebKit on macOS, GTK/WebKit on Linux) |

## Installation

### Pre-built Binaries

Download alpha releases from the [Releases page](https://github.com/ConsciousUniverse/simple-photo-meta/releases):

- **macOS (Apple Silicon)**: [DMG installer](https://github.com/ConsciousUniverse/simple-photo-meta/releases). Once downloaded, install in the usual way. Since the alpha release is not signed, you will need to run this command before running it for the first time, to unblock the binary on Gatekeeper: `xattr -dr com.apple.quarantine /Applications/SimplePhotoMeta.app`
- **Linux**: [AppImage (universal)](https://github.com/ConsciousUniverse/simple-photo-meta/releases)

### From Source

**Requirements:**

- Python 3.13+
- Exiv2 library (for metadata operations)
- pybind11 (for C++ bindings)

**macOS:**

```bash
# Install dependencies
brew install exiv2 brotli pybind11 python@3.13

# Clone and setup
git clone https://github.com/consciousuniverse/simple-photo-meta.git
cd simple-photo-meta

# Run (creates venv automatically)
./scripts/run.sh
```

**Linux (Ubuntu/Debian):**

```bash
# Install dependencies
sudo apt install libexiv2-dev libbrotli-dev python3-pybind11 python3.13

# Clone and setup
git clone https://github.com/consciousuniverse/simple-photo-meta.git
cd simple-photo-meta

# Run (creates venv automatically)
./scripts/run.sh
```

The `run.sh` script will:

1. Create a Python virtual environment (`.venv`)
2. Install all required packages
3. Build the C++ Exiv2 bindings if needed
4. Start the uvicorn server on `http://127.0.0.1:8080`
5. Open your browser to the app

### Optional: HEIC/HEIF Support

HEIC/HEIF image format support is included automatically when you run the app.

## Usage

1. **Open Directory**: Click "Open Folder" to select a folder containing images
2. **Browse Images**: Navigate through paginated thumbnails
3. **Select Metadata Type**: Choose between IPTC or EXIF from the dropdown
4. **Select Field**: Choose which metadata field to edit (e.g., Keywords, Caption, Artist, Copyright)
5. **Edit Tags**:
   - Type in the input field and press Enter to add
   - Click the ✕ button to delete tags
   - Use autocomplete suggestions from your tag library
6. **Search**: Use the search bar to find images by tag value
7. **Scan Directory**: Build a tag library from all images in the directory for quick reuse

## Screenshots

![alt text](assets/image.png)

## Building from Source

### Build Scripts

| Script                         | Description                                                  |
| ------------------------------ | ------------------------------------------------------------ |
| `scripts/run.sh`             | Start dev server - creates venv, installs deps, runs uvicorn |
| `scripts/build_bindings.sh`  | Build C++ Exiv2 bindings                                     |
| `scripts/build_desktop.sh`   | Build standalone app with PyInstaller                        |
| `scripts/build_all.sh`       | Full build - bindings → desktop → installer                |
| `scripts/create_dmg.sh`      | Create macOS DMG installer                                   |
| `scripts/create_appimage.sh` | Create Linux AppImage                                        |

### Build Prerequisites

**macOS:**

```bash
brew install exiv2 brotli pybind11 create-dmg
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt install libexiv2-dev libbrotli-dev python3-pybind11 \
    python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

### Output Locations

| Platform | Output                                                                                |
| -------- | ------------------------------------------------------------------------------------- |
| macOS    | `dist/SimplePhotoMeta.app` → `packages/macos/SimplePhotoMeta-2.0.0.dmg`          |
| Linux    | `dist/SimplePhotoMeta/` → `packages/Linux/SimplePhotoMeta-2.0.0-x86_64.AppImage` |

## Data Storage

- **Database**: `~/Library/Application Support/SimplePhotoMeta/spm_web.db` (macOS) or `~/.local/share/SimplePhotoMeta/` (Linux)
- **Thumbnails**: Stored in `.thumbnails` folder within each photo directory you open
- **Metadata**: Written directly to image files via Exiv2

## License

Simple Photo Meta is licensed under the GPLv3. See the [LICENSE](LICENSE) file for more details.

### Third-Party Licenses

This project includes or links to several open-source components. See [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) for complete details:

- **Exiv2**: GPL-2.0+ / GPL-3.0 / LGPL-3.0
- **FastAPI**: MIT
- **pywebview**: BSD-3-Clause
- **inih**: BSD-3-Clause
- **pybind11**: BSD-3-Clause
- **Pillow**: HPND

## Current Version

v3.0.5-alpha+6f82be1

## Contributing

This is an alpha project under active development. Bug reports and pull requests are welcome on GitHub.

## Author

Dan Bright - [GitHub](https://github.com/consciousuniverse), <github@danbright.uk>
