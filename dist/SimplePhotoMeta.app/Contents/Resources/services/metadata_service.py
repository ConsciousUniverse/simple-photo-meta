"""
Metadata service - wraps Exiv2 bindings for reading/writing metadata.
No Django dependencies.
"""

import os
import sys

# Add parent directory to path to import exiv2bind
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simple_photo_meta.exiv2bind import Exiv2Bind
from simple_photo_meta import iptc_tags, exif_tags


def get_metadata(image_path: str) -> dict:
    """
    Get all metadata from an image.
    Returns dict with 'iptc' and 'exif' sections.
    """
    try:
        meta = Exiv2Bind(image_path)
        return meta.to_dict()
    except Exception as e:
        print(f"Error reading metadata from {image_path}: {e}")
        return {"iptc": {}, "exif": {}}


def get_tag_values(image_path: str, tag_type: str, metadata_type: str = "iptc") -> list:
    """
    Get values for a specific tag type from an image.
    
    Args:
        image_path: Path to the image file
        tag_type: The tag field name (e.g., "Keywords", "Artist")
        metadata_type: Either "iptc" or "exif"
    
    Returns:
        List of tag values
    """
    result = get_metadata(image_path)
    section = result.get(metadata_type, {})
    value = section.get(tag_type)
    
    if isinstance(value, list):
        return [v.strip() for v in value if v and v.strip()]
    elif isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def set_tag_values(image_path: str, tag_type: str, values: list, metadata_type: str = "iptc") -> bool:
    """
    Set values for a specific tag type on an image.
    
    Args:
        image_path: Path to the image file
        tag_type: The tag field name (e.g., "Keywords", "Artist")
        values: List of values to set
        metadata_type: Either "iptc" or "exif"
    
    Returns:
        True if successful, False otherwise
    """
    try:
        meta = Exiv2Bind(image_path)
        
        # Get current metadata
        current = meta.to_dict()
        
        # Update the specific field
        if metadata_type not in current:
            current[metadata_type] = {}
        
        # Handle multi-valued vs single-valued tags
        if metadata_type == "iptc":
            tag_def = next((t for t in iptc_tags.iptc_writable_tags if t["tag"] == tag_type), None)
        else:
            tag_def = next((t for t in exif_tags.exif_writable_tags if t["tag"] == tag_type), None)
        
        if tag_def and tag_def.get("multi_valued", False):
            current[metadata_type][tag_type] = values
        else:
            current[metadata_type][tag_type] = values[0] if values else ""
        
        # Write back
        meta.from_dict(current)
        return True
    except Exception as e:
        print(f"Error writing metadata to {image_path}: {e}")
        return False


def get_tag_definitions() -> dict:
    """
    Get all available tag definitions.
    Returns dict with 'iptc' and 'exif' tag lists.
    """
    return {
        "iptc": iptc_tags.iptc_writable_tags,
        "exif": exif_tags.exif_writable_tags,
    }
