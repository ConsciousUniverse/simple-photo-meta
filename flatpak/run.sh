#!/bin/bash
# Flatpak runtime wrapper for Simple Photo Meta
#
# Adds the application source tree and backend directory to PYTHONPATH,
# selects the GTK backend for pywebview, and launches the app.

export PYTHONPATH=/app/share/simple-photo-meta:/app/share/simple-photo-meta/backend
export PYWEBVIEW_GUI=gtk
export LD_LIBRARY_PATH=/app/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

cd /app/share/simple-photo-meta
exec python3 launcher.py "$@"
