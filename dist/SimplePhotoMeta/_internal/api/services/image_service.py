"""
Image processing services - thumbnail and preview generation.
Migrated from simple_photo_meta/main.py
"""

import os
import sys
import time
import hashlib
from PIL import Image, ImageOps
from django.conf import settings

# Try to register HEIF support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass


def _preview_cache_path(image_path: str, edge_length: int) -> str:
    """Get the path for a cached preview image."""
    folder = os.path.dirname(image_path)
    cache_dir = os.path.join(folder, settings.PREVIEW_CACHE_DIR_NAME)
    os.makedirs(cache_dir, exist_ok=True)
    hash_input = f"{os.path.abspath(image_path)}::{edge_length}"
    hash_str = hashlib.sha256(hash_input.encode()).hexdigest()
    return os.path.join(cache_dir, f"{hash_str}.jpg")


def _preview_is_current(image_path: str, preview_path: str) -> bool:
    """Check if preview cache is up to date."""
    try:
        return os.path.getmtime(preview_path) >= os.path.getmtime(image_path)
    except OSError:
        return False


def _thumbnail_cache_path(image_path: str) -> str:
    """Get the path for a cached thumbnail."""
    folder = os.path.dirname(image_path)
    thumb_dir = os.path.join(folder, settings.THUMBNAIL_DIR_NAME)
    os.makedirs(thumb_dir, exist_ok=True)
    hash_str = hashlib.sha256(os.path.abspath(image_path).encode()).hexdigest()
    return os.path.join(thumb_dir, f"{hash_str}.jpg")


def _process_image(img: Image.Image) -> Image.Image:
    """Process image for thumbnail/preview generation."""
    # Handle multi-frame images (like animated GIFs)
    if hasattr(img, "n_frames") and img.n_frames > 1:
        img.seek(0)
    
    # Handle EXIF orientation
    img = ImageOps.exif_transpose(img)
    
    # Convert to RGB for compatibility with all modes
    if img.mode == "CMYK":
        from PIL import ImageChops
        img = ImageChops.invert(img)
        img = img.convert("RGB")
        img = ImageChops.invert(img)
    elif img.mode.startswith("I;") or img.mode == "I":
        img = img.point(lambda x: x / 256).convert("L")
        img = ImageOps.autocontrast(img)
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    
    return img


def ensure_thumbnail_image(image_path: str, size: tuple = None) -> str | None:
    """
    Ensure a thumbnail exists for the given image.
    Returns the path to the thumbnail, or None if generation failed.
    """
    if size is None:
        size = settings.THUMBNAIL_SIZE
    
    thumb_path = _thumbnail_cache_path(image_path)
    
    if os.path.exists(thumb_path):
        return thumb_path
    
    try:
        with Image.open(image_path) as img:
            img = _process_image(img)
            img.thumbnail(size, Image.LANCZOS)
            
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            img.save(thumb_path, "JPEG", quality=85)
        return thumb_path
    except Exception as exc:
        print(f"Failed to create thumbnail for {image_path}: {exc}")
        # Write a placeholder so we don't retry
        try:
            placeholder = Image.new("RGB", size, (210, 210, 210))
            placeholder.save(thumb_path, "JPEG", quality=60)
            return thumb_path
        except Exception:
            return None


def ensure_preview_image(image_path: str, edge_length: int = None) -> str | None:
    """
    Ensure a preview image exists for the given image.
    Returns the path to the preview, or None if generation failed.
    """
    if edge_length is None:
        edge_length = settings.DEFAULT_PREVIEW_MAX_EDGE
    
    preview_path = _preview_cache_path(image_path, edge_length)
    
    if os.path.exists(preview_path) and _preview_is_current(image_path, preview_path):
        return preview_path
    
    try:
        with Image.open(image_path) as img:
            img = _process_image(img)
            target_size = (edge_length, edge_length)
            img.thumbnail(target_size, Image.LANCZOS)
            
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            img.save(preview_path, "JPEG", quality=90)
        
        # Match timestamps
        try:
            mtime = os.path.getmtime(image_path)
            os.utime(preview_path, (mtime, mtime))
        except OSError:
            pass
        
        return preview_path
    except Exception as exc:
        print(f"Failed to create preview for {image_path}: {exc}")
        try:
            if os.path.exists(preview_path):
                os.remove(preview_path)
        except OSError:
            pass
        return None
