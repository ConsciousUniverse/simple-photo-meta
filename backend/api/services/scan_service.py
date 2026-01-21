"""
Directory scanning service.
"""

import os
import threading
from typing import Optional
from django.conf import settings
from api.models import Image, Tag, ImageTag, ScannedDirectory
from api.services.metadata_service import get_metadata

# Import tag definitions
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
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


SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif")


def get_images_in_folder(folder_path: str) -> list[str]:
    """Get list of all image files in folder (recursive)."""
    images = []
    for root, dirs, files in os.walk(folder_path):
        # Skip cache directories
        if ".thumbnails" in dirs:
            dirs.remove(".thumbnails")
        if settings.PREVIEW_CACHE_DIR_NAME in dirs:
            dirs.remove(settings.PREVIEW_CACHE_DIR_NAME)
        
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


def start_scan(folder_path: str) -> bool:
    """
    Start scanning a directory in the background.
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
    thread = threading.Thread(target=_run_scan, args=(folder_path,))
    thread.daemon = True
    thread.start()
    
    return True


def _run_scan(folder_path: str):
    """Background scan worker."""
    try:
        # Get list of images
        images = get_images_in_folder(folder_path)
        
        with _scan_lock:
            _scan_state["total"] = len(images)
        
        for image_path in images:
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
        ScannedDirectory.objects.update_or_create(
            path=os.path.abspath(folder_path),
            defaults={}
        )
    
    finally:
        with _scan_lock:
            _scan_state["running"] = False
            _scan_state["folder"] = None


def _index_image(image_path: str):
    """Index a single image's metadata."""
    # Get or create image record
    image_obj, _ = Image.objects.get_or_create(path=image_path)
    
    # Clear existing tag associations
    ImageTag.objects.filter(image=image_obj).delete()
    
    # Read metadata
    metadata = get_metadata(image_path)
    
    # Index IPTC fields
    iptc_data = metadata.get("iptc", {})
    for field in iptc_tags.iptc_writabable_fields_list:
        value = iptc_data.get(field)
        _index_tag_values(image_obj, field, value)
    
    # Index EXIF fields
    exif_data = metadata.get("exif", {})
    for field in exif_tags.exif_writable_fields_list:
        value = exif_data.get(field)
        _index_tag_values(image_obj, field, value)


def _index_tag_values(image_obj: Image, tag_type: str, value):
    """Index tag values for an image."""
    if isinstance(value, list):
        tags = [t for t in value if t and str(t).strip()]
    elif isinstance(value, str) and value.strip():
        tags = [value.strip()]
    else:
        return
    
    for tag_text in tags:
        tag_obj, _ = Tag.objects.get_or_create(
            tag=str(tag_text).strip(),
            tag_type=tag_type
        )
        ImageTag.objects.get_or_create(image=image_obj, tag=tag_obj)
