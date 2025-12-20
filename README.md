# Simple Photo Meta (Alpha)

This is a desktop photograph metadata management software, for MacOS and Linux. It allows the editing of both IPTC and EXIF tags, with a clean interface. This is not a photo processing software - it deals only with metadata. It is intended to do one job, and do it well.

The software is written in Python (3.13), and uses the Qt GUI framework. It is powered by the excellent [Exiv2 metadata library](https://github.com/exiv2/exiv2).

This software was written for MacOS (Apple Silicon) and Linux. It is untested on Windows.

## ⚠️ Currently Potentially Unsafe - Use with Caution

This is an Alpha version of this software, and as such is made available for testing purposes only. It is unsafe to use on valuable images - please do not test on the only copy of your most cherished photos as they may be destroyed!

## Download Binaries (Mac and Linux)

Binaries of the latest version may be downloaded from the [releases page here on GitHub](https://github.com/ConsciousUniverse/simple-photo-meta/releases). The MacOS (Apple Silicon) version is available as a .dmg, while the Linux version is available as an AppImage.

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
- **Batch Operations**: Add the same tag to multiple images efficiently (coming soon)
- **Unsaved Changes Detection**: Automatic prompts to save changes when switching images or tag types
- **Input Validation**: Ensures tags meet format requirements

### Performance & UX

- **Background Threading**: Non-blocking metadata operations
- **Optimized Caching**: Thumbnail and preview caching for instant navigation
- **Responsive UI**: Smooth interface even with large image collections
- **Error Handling**: Graceful handling of corrupted files and unsupported formats
- **SQLite Database**: Fast local metadata indexing for quick searches

## Installation

### Pre-built Binaries

Download alpha releases from the Releases page:

- **macOS (Apple Silicon)**: [DMG installer](https://github.com/ConsciousUniverse/simple-photo-meta/releases)
- **Linux**: [AppImage (universal)](https://github.com/ConsciousUniverse/simple-photo-meta/releases)

### From Source

**Requirements:**

- Python 3.13+
- Exiv2 library (for metadata operations)
- Qt6 (via PySide6)

**macOS:**

```bash
# Install dependencies
brew install exiv2 brotli python@3.13

# Clone and setup
git clone https://github.com/consciousuniverse/simple-photo-meta.git
cd simple-photo-meta
pip install -r requirements.txt

# Run
python simple_photo_meta/main.py
```

**Linux:**

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get install libexiv2-dev libbrotli-dev python3.13

# Clone and setup
git clone https://github.com/consciousuniverse/simple-photo-meta.git
cd simple-photo-meta
pip install -r requirements.txt

# Run
python simple_photo_meta/main.py
```

### Optional: HEIC/HEIF Support

To enable HEIC/HEIF image format support:

```bash
pip install pillow-heif
```

## Usage

1. **Open Directory**: Click "Open Directory" to select a folder containing images
2. **Browse Images**: Navigate through paginated thumbnails (25 per page)
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

## Technical Architecture

### Core Technologies

- **Python 3.13**: Modern Python with type hints
- **PySide6/Qt6**: Cross-platform GUI framework
- **Exiv2**: Industry-standard metadata library (via pybind11 bindings)
- **SQLite**: Local metadata index for fast searches
- **Pillow**: Image processing and thumbnail generation
- **pillow-heif**: Optional HEIC/HEIF format support

### Build System

- **Nuitka**: Compiles Python to native machine code for distribution
- **Static Linking**: Bundles Exiv2 statically on macOS for portable binaries
- **Dynamic Linking**: Uses system libraries on Linux for better compatibility

## License

Simple Photo Meta is licensed under the GPLv3. See the [LICENSE](LICENSE) file for more details.

### Third-Party Licenses

This project includes or links to several open-source components. See [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) for complete details:

- **Exiv2**: GPL-2.0+ / GPL-3.0 / LGPL-3.0
- **PySide6/Qt6**: LGPL-3.0
- **inih**: BSD-3-Clause
- **pybind11**: BSD-3-Clause
- **Pillow**: HPND

## Current Version

v0.1.130-alpha+59fecae

## Contributing

This is an alpha project under active development. Bug reports and pull requests are welcome on GitHub.

## Author

Dan Bright - [GitHub](https://github.com/consciousuniverse), <github@danbright.uk>
