#!/bin/bash
#
# Build Exiv2 C++ Bindings for Simple Photo Meta
#
# This script builds the Python C++ extension that wraps libexiv2.
# Must be run on each target platform (macOS, Linux).
#
# Prerequisites:
#   macOS:  brew install exiv2 brotli pybind11
#   Linux:  sudo apt install libexiv2-dev libbrotli-dev python3-pybind11
#
# Usage:
#   ./scripts/build_bindings.sh
#   ./scripts/build_bindings.sh --clean   # Remove stale venvs first
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  Building Exiv2 C++ Bindings"
echo "========================================"
echo ""

cd "$PROJECT_DIR"

# Handle --clean flag
if [[ "$1" == "--clean" ]]; then
    echo "Cleaning stale virtual environments..."
    rm -rf .venv .venv-build
    echo ""
fi

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
    echo "Platform: macOS"
    
    # Check for Homebrew libraries
    if [[ -d "/opt/homebrew/lib" ]]; then
        LIB_DIR="/opt/homebrew/lib"
    else
        LIB_DIR="/usr/local/lib"
    fi
    
    # Check prerequisites
    if [[ ! -f "$LIB_DIR/libexiv2.a" ]]; then
        echo "Error: libexiv2 not found. Install with: brew install exiv2"
        exit 1
    fi
    
elif [[ "$OSTYPE" == "linux"* ]]; then
    PLATFORM="Linux"
    echo "Platform: Linux"
    
    # Check prerequisites
    if ! dpkg -l libexiv2-dev &>/dev/null; then
        echo "Error: libexiv2-dev not found. Install with: sudo apt install libexiv2-dev libbrotli-dev"
        exit 1
    fi
else
    echo "Error: Unsupported platform: $OSTYPE"
    exit 1
fi

echo ""

# Ensure inih vendored sources exist
if [[ ! -f "simple_photo_meta/inih/INIReader.cpp" ]]; then
    echo "Fetching vendored inih library..."
    mkdir -p simple_photo_meta/inih
    curl -sL https://raw.githubusercontent.com/benhoyt/inih/master/ini.h -o simple_photo_meta/inih/ini.h
    curl -sL https://raw.githubusercontent.com/benhoyt/inih/master/ini.c -o simple_photo_meta/inih/ini_parser.cpp
    curl -sL https://raw.githubusercontent.com/benhoyt/inih/master/cpp/INIReader.h -o simple_photo_meta/inih/INIReader.h
    curl -sL https://raw.githubusercontent.com/benhoyt/inih/master/cpp/INIReader.cpp -o simple_photo_meta/inih/INIReader.cpp
    
    # Patch INIReader.cpp to find ini.h in same directory
    if [[ "$PLATFORM" == "macOS" ]]; then
        sed -i '' 's|#include "../ini.h"|#include "ini.h"|' simple_photo_meta/inih/INIReader.cpp
    else
        sed -i 's|#include "../ini.h"|#include "ini.h"|' simple_photo_meta/inih/INIReader.cpp
    fi
    echo "inih library vendored."
fi

# Clean old builds
echo "Cleaning old builds..."
rm -rf build/ simple_photo_meta/*.so simple_photo_meta/*.pyd

# Check for virtual environment (verify it's actually usable - check for pip not just python)
if [[ -f "Pipfile" ]] && command -v pipenv &>/dev/null; then
    echo "Using pipenv environment..."
    pipenv run pip install pybind11 setuptools
    pipenv run python setup.py build_ext --inplace
elif [[ -x ".venv-build/bin/pip" ]]; then
    echo "Using .venv-build environment..."
    source .venv-build/bin/activate
    pip install pybind11 setuptools
    python setup.py build_ext --inplace
elif [[ -x ".venv/bin/pip" ]]; then
    echo "Using .venv environment..."
    source .venv/bin/activate
    pip install pybind11 setuptools
    python setup.py build_ext --inplace
else
    echo "No virtual environment found, creating one..."
    python3 -m venv .venv-build
    source .venv-build/bin/activate
    pip install --upgrade pip wheel pybind11 setuptools
    python setup.py build_ext --inplace
fi

echo ""
echo "========================================"
echo "  Build Complete!"
echo "========================================"

# Show output
SO_FILE=$(ls simple_photo_meta/exiv2bind*.so 2>/dev/null || true)
if [[ -n "$SO_FILE" ]]; then
    echo "Output: $SO_FILE"
    echo ""
    
    # Verify dependencies
    echo "Library dependencies:"
    if [[ "$PLATFORM" == "macOS" ]]; then
        otool -L "$SO_FILE" | head -10
    else
        ldd "$SO_FILE" | head -10
    fi
else
    echo "Error: No .so file produced!"
    exit 1
fi
