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

# Check for pipenv
if ! command -v pipenv &> /dev/null; then
    echo "Error: pipenv is required. Install with: pip install pipenv"
    exit 1
fi

cd "$PROJECT_DIR"

# On Linux, allow pipenv venv to see system site-packages (for GTK/GObject bindings)
if [[ "$OSTYPE" == "linux"* ]]; then
    export PIPENV_SITE_PACKAGES=1
fi

# Install dependencies
echo "Installing dependencies with pipenv..."
pipenv install

# Build C++ bindings if needed
if ! pipenv run python -c "from simple_photo_meta.exiv2bind import Exiv2Bind" 2>/dev/null; then
    echo "Building C++ metadata bindings..."
    pipenv install --dev
    pipenv run python setup.py build_ext --inplace
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
(sleep 2 && pipenv run python -c "import webbrowser; webbrowser.open('http://127.0.0.1:$PORT')") &

# Run the development server with uvicorn
cd "$BACKEND_DIR"
pipenv run python -m uvicorn main:app --host 127.0.0.1 --port "$PORT" --reload
