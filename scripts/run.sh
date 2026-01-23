#!/bin/bash

# Simple Photo Meta - Run Script
# Starts the local FastAPI server and opens the browser
# NO external dependencies beyond Python

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "=== Simple Photo Meta ==="
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# Activate virtual environment
source "$PROJECT_DIR/.venv/bin/activate"

# Install backend dependencies
echo "Installing dependencies..."
pip install -q fastapi uvicorn pillow pillow-heif appdirs

# Build C++ bindings if needed
if ! python -c "from simple_photo_meta.exiv2bind import Exiv2Bind" 2>/dev/null; then
    echo "Building C++ metadata bindings..."
    cd "$PROJECT_DIR"
    pip install -q pybind11 setuptools
    python setup.py build_ext --inplace
fi

# Start the server
PORT=${PORT:-8080}
echo ""
echo "========================================="
echo "  Simple Photo Meta"
echo "  Open: http://127.0.0.1:$PORT"
echo "  Press Ctrl+C to stop"
echo "========================================="
echo ""

# Open browser after a short delay (background)
(sleep 2 && python -c "import webbrowser; webbrowser.open('http://127.0.0.1:$PORT')") &

# Run the development server with uvicorn
cd "$BACKEND_DIR"
python -m uvicorn main:app --host 127.0.0.1 --port "$PORT" --reload
