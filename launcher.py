#!/usr/bin/env python3
"""
Simple Photo Meta - Desktop Launcher

Starts the FastAPI backend with uvicorn and opens a native window using pywebview.
Works on macOS (WebKit), Linux (GTK/WebKit), and Windows (EdgeChromium).
"""

import os
import sys
import threading
import time
import socket
from pathlib import Path

# Ensure the project root is in the path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


def find_free_port(start_port=8080, max_attempts=100):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find free port in range {start_port}-{start_port + max_attempts}")


def wait_for_server(port, timeout=30):
    """Wait for server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(("127.0.0.1", port))
                return True
        except (socket.error, socket.timeout):
            time.sleep(0.1)
    return False


def run_fastapi_server(port):
    """Run FastAPI server with uvicorn in a thread."""
    import uvicorn
    from main import app
    
    # Run uvicorn with quiet logging
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    """Main entry point."""
    import webview
    
    # Find available port
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    
    print(f"Starting Simple Photo Meta on {url}...")
    
    # Start FastAPI/uvicorn in a daemon thread
    server_thread = threading.Thread(target=run_fastapi_server, args=(port,), daemon=True)
    server_thread.start()
    
    # Wait for server to be ready
    if not wait_for_server(port):
        print("Error: FastAPI server failed to start", file=sys.stderr)
        sys.exit(1)
    
    print("Server ready, opening window...")
    
    # Create native window with pywebview
    window = webview.create_window(
        title="Simple Photo Meta",
        url=url,
        width=1400,
        height=900,
        min_size=(800, 600),
        resizable=True,
        text_select=True,
    )
    
    # Start the GUI event loop (blocks until window is closed)
    webview.start()
    
    print("Window closed, shutting down...")


if __name__ == "__main__":
    main()
