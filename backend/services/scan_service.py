"""
Directory scanning service.
No Django dependencies.
"""

import os
import sys
import threading
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import SUPPORTED_EXTENSIONS, PREVIEW_CACHE_DIR_NAME, THUMBNAIL_DIR_NAME
import database
from services.metadata_service import get_metadata
from simple_photo_meta import iptc_tags, exif_tags


# Global scan state
_scan_state = {
    "running": False,
    "folder": None,
    "processed": 0,
    "total": 0,
    "cancelled": False,
}
_scan_lock = threading.Lock()


def get_images_in_folder(folder_path: str) -> list[str]:
    """Get list of all image files in folder (recursive)."""
    images = []
    for root, dirs, files in os.walk(folder_path):
        # Skip cache directories
        if THUMBNAIL_DIR_NAME in dirs:
            dirs.remove(THUMBNAIL_DIR_NAME)
        if PREVIEW_CACHE_DIR_NAME in dirs:
            dirs.remove(PREVIEW_CACHE_DIR_NAME)
        
        for fname in files:
            if fname.lower().endswith(SUPPORTED_EXTENSIONS):
                images.append(os.path.join(root, fname))
    
    return sorted(images)


def get_scan_status() -> dict:
    """Get current scan status."""
    with _scan_lock:
        return {
            "running": _scan_state["running"],
            "folder": _scan_state["folder"],
            "processed": _scan_state["processed"],
            "total": _scan_state["total"],
        }


def cancel_scan():
    """Cancel any running scan."""
    with _scan_lock:
        _scan_state["cancelled"] = True


def start_scan(folder_path: str, force: bool = False) -> bool:
    """
    Start scanning a directory in the background.
    
    Args:
        folder_path: Directory to scan
        force: If True, rescan all images. If False, only scan new images.
    
    Returns True if scan started, False if already running.
    """
    with _scan_lock:
        if _scan_state["running"]:
            return False
        
        _scan_state["running"] = True
        _scan_state["folder"] = folder_path
        _scan_state["processed"] = 0
        _scan_state["total"] = 0
        _scan_state["cancelled"] = False
    
    # Start background thread
    thread = threading.Thread(target=_run_scan, args=(folder_path, force))
    thread.daemon = True
    thread.start()
    
    return True


def _run_scan(folder_path: str, force: bool = False):
    """Background scan worker."""
    try:
        # Get list of all images in folder
        all_images = get_images_in_folder(folder_path)
        all_images_set = set(all_images)
        
        # Purge database records for files that no longer exist
        purged = database.purge_missing_images(os.path.abspath(folder_path), all_images_set)
        if purged > 0:
            print(f"Purged {purged} missing image(s) from database")
        
        if force:
            # Full rescan - process all images
            images_to_scan = all_images
        else:
            # Incremental scan - only process new images
            indexed_images = database.get_indexed_images(os.path.abspath(folder_path))
            images_to_scan = [img for img in all_images if img not in indexed_images]
        
        with _scan_lock:
            _scan_state["total"] = len(images_to_scan)
        
        if len(images_to_scan) == 0:
            # Nothing to scan
            with _scan_lock:
                _scan_state["running"] = False
                _scan_state["folder"] = None
            return
        
        for image_path in images_to_scan:
            with _scan_lock:
                if _scan_state["cancelled"]:
                    break
            
            try:
                _index_image(image_path)
            except Exception as e:
                print(f"Error indexing {image_path}: {e}")
            
            with _scan_lock:
                _scan_state["processed"] += 1
        
        # Mark directory as scanned
        database.mark_directory_scanned(os.path.abspath(folder_path))
    
    finally:
        with _scan_lock:
            _scan_state["running"] = False
            _scan_state["folder"] = None


def _index_image(image_path: str):
    """Index a single image's metadata."""
    # Get or create image record
    image_id = database.get_or_create_image(image_path)
    
    # Clear existing tag associations
    database.clear_image_tags(image_id)
    
    # Read metadata
    metadata = get_metadata(image_path)
    
    # Index IPTC fields
    iptc_data = metadata.get("iptc", {})
    for field in iptc_tags.iptc_writabable_fields_list:
        value = iptc_data.get(field)
        _index_tag_values(image_id, field, value)
    
    # Index EXIF fields
    exif_data = metadata.get("exif", {})
    for field in exif_tags.exif_writable_fields_list:
        value = exif_data.get(field)
        _index_tag_values(image_id, field, value)


def _index_tag_values(image_id: int, tag_type: str, value):
    """Index tag values for an image."""
    if isinstance(value, list):
        tags = [t for t in value if t and str(t).strip()]
    elif isinstance(value, str) and value.strip():
        tags = [value.strip()]
    else:
        return
    
    for tag_text in tags:
        tag_id = database.get_or_create_tag(str(tag_text).strip(), tag_type)
        database.add_image_tag(image_id, tag_id)
