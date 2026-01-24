"""
Simple Photo Meta - FastAPI Backend

A lightweight REST API for photo metadata editing.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import database
from services import image_service, metadata_service, scan_service


# ============== Pydantic Models ==============

class DirectoryRequest(BaseModel):
    path: str


class ScanRequest(BaseModel):
    path: str
    force: bool = False


class MetadataUpdateRequest(BaseModel):
    path: str
    tag_type: str
    metadata_type: str = "iptc"
    values: List[str]


class PreferenceRequest(BaseModel):
    value: str


class OpenInViewerRequest(BaseModel):
    path: str


# ============== FastAPI App ==============

app = FastAPI(
    title="Simple Photo Meta",
    description="Local photo metadata editor API",
    version="2.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    database.init_database()


# ============== HTML Template ==============

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main HTML page."""
    template_path = config.TEMPLATES_DIR / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return template_path.read_text()


# ============== Directory Operations ==============

@app.get("/api/directories/browse")
async def browse_directory(path: str = ""):
    """Browse directories for folder selection."""
    # Default to home directory if no path specified
    if not path:
        path = str(Path.home())
    
    # Expand ~ to home directory
    path = os.path.expanduser(path)
    
    # Validate path exists and is a directory
    if not os.path.exists(path):
        parent = os.path.dirname(path)
        if os.path.exists(parent):
            path = parent
        else:
            path = str(Path.home())
    
    if not os.path.isdir(path):
        path = os.path.dirname(path)
    
    # Get parent directory
    parent = os.path.dirname(path)
    if parent == path:  # At root
        parent = None
    
    # List subdirectories
    subdirs = []
    try:
        for entry in os.scandir(path):
            if entry.is_dir() and not entry.name.startswith('.'):
                subdirs.append({
                    'name': entry.name,
                    'path': entry.path,
                })
    except PermissionError:
        pass
    
    # Sort by name
    subdirs.sort(key=lambda x: x['name'].lower())
    
    # Count images in current directory (non-recursive for speed)
    image_count = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file() and entry.name.lower().endswith(config.SUPPORTED_EXTENSIONS):
                image_count += 1
    except PermissionError:
        pass
    
    return {
        'current': path,
        'parent': parent,
        'directories': subdirs,
        'image_count': image_count,
    }


@app.post("/api/directories/open")
async def open_directory(request: DirectoryRequest):
    """Open a directory and get initial image list."""
    folder_path = request.path
    
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Directory not found")
    
    # Get images in folder
    images = scan_service.get_images_in_folder(folder_path)
    
    return {
        "folder": folder_path,
        "total_images": len(images),
        "images": images[:config.DEFAULT_PAGE_SIZE],
        "page": 0,
        "page_size": config.DEFAULT_PAGE_SIZE,
        "total_pages": (len(images) + config.DEFAULT_PAGE_SIZE - 1) // config.DEFAULT_PAGE_SIZE,
    }


@app.post("/api/directories/scan")
async def start_scan(request: ScanRequest):
    """Start scanning a directory. Use force=True to rescan all images."""
    folder_path = request.path
    
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Directory not found")
    
    started = scan_service.start_scan(folder_path, force=request.force)
    
    return {
        "started": started,
        "status": scan_service.get_scan_status(),
    }


@app.delete("/api/directories/scan")
async def cancel_scan():
    """Cancel current scan."""
    scan_service.cancel_scan()
    return {"cancelled": True}


@app.get("/api/directories/scan/status")
async def get_scan_status():
    """Get current scan status."""
    return scan_service.get_scan_status()


# ============== Image Operations ==============

@app.get("/api/images")
async def list_images(
    folder: str,
    page: int = 0,
    page_size: int = Query(default=25),
    search: str = "",
    tag_type: str = ""
):
    """Get paginated list of images."""
    search = search.strip()
    tag_type = tag_type.strip()
    
    # Get images based on search mode
    if search:
        # Search terms provided - filter by those terms
        images = database.search_images(folder, search, tag_type or None, page, page_size)
        total = database.count_search_results(folder, search, tag_type or None)
    elif tag_type:
        # No search terms but tag_type selected - show images WITHOUT any tags of this type
        all_images = set(scan_service.get_images_in_folder(folder))
        tagged_images = database.get_tagged_images(folder, tag_type)
        untagged = sorted(all_images - tagged_images)
        total = len(untagged)
        start = page * page_size
        images = untagged[start:start + page_size]
    else:
        # No search terms and no tag_type - show all images
        all_images = scan_service.get_images_in_folder(folder)
        total = len(all_images)
        start = page * page_size
        images = all_images[start:start + page_size]
    
    return {
        "folder": folder,
        "images": images,
        "page": page,
        "page_size": page_size,
        "total_images": total,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
    }


@app.get("/api/images/thumbnail")
async def get_thumbnail(path: str):
    """Get thumbnail for an image."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    thumb_path = image_service.ensure_thumbnail(path)
    
    if not thumb_path or not os.path.isfile(thumb_path):
        raise HTTPException(status_code=500, detail="Thumbnail generation failed")
    
    return FileResponse(thumb_path, media_type="image/jpeg")


@app.get("/api/images/preview")
async def get_preview(path: str, edge: int = Query(default=2048)):
    """Get preview for an image."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    preview_path = image_service.ensure_preview(path, edge)
    
    if not preview_path or not os.path.isfile(preview_path):
        raise HTTPException(status_code=500, detail="Preview generation failed")
    
    return FileResponse(preview_path, media_type="image/jpeg")


@app.post("/api/images/open-in-viewer")
async def open_in_viewer(request: OpenInViewerRequest):
    """Open an image in the system's default viewer."""
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        if sys.platform == 'darwin':  # macOS
            subprocess.run(['open', request.path], check=True)
        elif sys.platform.startswith('linux'):
            subprocess.run(['xdg-open', request.path], check=True)
        elif sys.platform == 'win32':
            os.startfile(request.path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported platform")
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Metadata Operations ==============

@app.get("/api/metadata")
async def get_metadata(
    path: str,
    tag_type: Optional[str] = None,
    metadata_type: str = "iptc"
):
    """Get image metadata."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    if tag_type:
        values = metadata_service.get_tag_values(path, tag_type, metadata_type)
        return {
            "path": path,
            "tag_type": tag_type,
            "metadata_type": metadata_type,
            "values": values,
        }
    else:
        metadata = metadata_service.get_metadata(path)
        return {
            "path": path,
            "metadata": metadata,
        }


@app.put("/api/metadata")
async def update_metadata(request: MetadataUpdateRequest):
    """Update image metadata."""
    if not os.path.isfile(request.path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    success = metadata_service.set_tag_values(
        request.path,
        request.tag_type,
        request.values,
        request.metadata_type
    )
    
    if success:
        # Update database index
        database.update_image_tags(request.path, request.tag_type, request.values)
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to write metadata")


@app.get("/api/metadata/definitions")
async def get_metadata_definitions():
    """Get available metadata tag definitions."""
    return metadata_service.get_tag_definitions()


# ============== Tag Operations ==============

@app.get("/api/tags")
async def list_tags(tag_type: Optional[str] = None):
    """List all tags."""
    tags = database.get_tags_by_type(tag_type)
    return {"tags": tags}


@app.get("/api/tags/search")
async def search_tags(
    q: str = "",
    tag_type: Optional[str] = None,
    limit: int = 20
):
    """Search tags."""
    tags = database.search_tags(q, tag_type, limit)
    return {"tags": tags}


# ============== Preferences ==============

@app.get("/api/preferences")
async def get_preferences():
    """Get all preferences."""
    prefs = database.get_all_preferences()
    return {"preferences": [{"key": k, "value": v} for k, v in prefs.items()]}


@app.get("/api/preferences/{key}")
async def get_preference(key: str):
    """Get a single preference."""
    value = database.get_preference(key)
    return {"key": key, "value": value}


@app.put("/api/preferences/{key}")
async def set_preference(key: str, request: PreferenceRequest):
    """Set a preference."""
    database.set_preference(key, request.value)
    return {"key": key, "value": request.value}


# ============== Run with Uvicorn ==============

def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the FastAPI server with uvicorn."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
