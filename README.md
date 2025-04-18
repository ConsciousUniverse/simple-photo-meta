# Simple Photo Meta (Alpha)

A simple desktop photograph IPTC Keyword meta tag editor application, for MacOS and Linux. Written in Python (3.13), using the QT GUI framework, and wrapping functionality provided by the fantastic [EXIV2 metatag management CLI utility](https://github.com/exiv2/exiv2).

Produced with the considerable assistance of Github Copilot (GPT-4.1).

Developing for MacOS and Linux; untested on Windows.

## Unsafe!

This is an Alpha version of this software, and as such is made available for testing only. It is unsafe to use on valuable data - please do not test on the only copy of your most cherished photos as they may get destroyed!

## Features & Usage

- Open directories (and subdirectories, recursively) and display contained image files as a paginated thumbail list.
- Scan directories and add all discovered IPTC Keyword metatags to a list (for future re-use).
- Search (realtime) all images by IPTC Keyword metatag.
- Search (realtime) the discovered Keyword metatag list.
- Add new IPTC Keyword metatags to images (image opened in a preview pane).
- Edit existing IPTC Keyword metatags.
- Delete existing IPTC Keyword metatags.

## Installation & Quick Start

1. **Install system dependencies** (required for image metadata editing):

   On macOS (with Homebrew):
   ```sh
   brew install exiv2
   pip3 install PySide6
   ```

   On Ubuntu:
   ```sh
   sudo apt update
   sudo apt install exiv2 python3-pip python3-pyside6
   ```

2. **Install Python dependencies**:
   ```sh
   pip install -r requirements.txt
   ```

3. **Install the app** (from the project root):
   ```sh
   pip install .
   ```

4. **Run the app**:
   ```sh
   simple-photo-meta
   ```

## Screenshots

Coming soon ...

## License

Simple Photo Meta is licensed under the GPLv3. See the [LICENSE](LICENSE) file for more details.

## Current Version

v0.1.1-beta

## Author

Dan Bright - [GitHub](https://github.com/consciousuniverse), github@bright.contact, with considerable assistance from Github Copilot (GPT-4.1).