"""
Location service - offline reverse geocoding.
Uses reverse_geocoder for local coordinate-to-place-name conversion.
"""

import re
from typing import Optional, Tuple

# Lazy-load reverse_geocoder to avoid startup delay
_rg = None


def _get_geocoder():
    """Lazy-load the reverse geocoder."""
    global _rg
    if _rg is None:
        import reverse_geocoder as rg
        _rg = rg
    return _rg


def parse_gps_coordinate(value: str, ref: Optional[str] = None) -> Optional[float]:
    """
    Parse a GPS coordinate string into decimal degrees.
    
    Handles formats like:
    - "37.7749" (decimal degrees)
    - "37 46 29.64" (degrees minutes seconds)
    - "37deg 46' 29.64\"" (DMS with symbols)
    - "37/1 46/1 2964/100" (rational format from EXIF)
    
    Args:
        value: The coordinate string
        ref: Reference direction (N, S, E, W) - if S or W, result is negative
    
    Returns:
        Decimal degrees as float, or None if parsing fails
    """
    if not value:
        return None
    
    value = str(value).strip()
    
    # Check if ref is embedded in the value (e.g., "37.7749 N")
    if not ref:
        if value.endswith(('N', 'S', 'E', 'W')):
            ref = value[-1]
            value = value[:-1].strip()
    
    try:
        # Try simple decimal format first
        result = float(value)
    except ValueError:
        # Try to parse DMS format
        result = _parse_dms(value)
    
    if result is None:
        return None
    
    # Apply reference (S and W are negative)
    if ref in ('S', 'W'):
        result = -abs(result)
    elif ref in ('N', 'E'):
        result = abs(result)
    
    return result


def _parse_dms(value: str) -> Optional[float]:
    """Parse degrees/minutes/seconds format."""
    # Remove common degree symbols and normalize
    value = value.replace('deg', ' ').replace('°', ' ')
    value = value.replace("'", ' ').replace("'", ' ')
    value = value.replace('"', ' ').replace('"', ' ')
    value = value.replace(',', ' ')
    
    # Try rational format: "37/1 46/1 2964/100"
    rational_match = re.findall(r'(\d+)/(\d+)', value)
    if len(rational_match) >= 2:
        try:
            degrees = float(rational_match[0][0]) / float(rational_match[0][1])
            minutes = float(rational_match[1][0]) / float(rational_match[1][1])
            seconds = 0.0
            if len(rational_match) >= 3:
                seconds = float(rational_match[2][0]) / float(rational_match[2][1])
            return degrees + minutes / 60 + seconds / 3600
        except (ValueError, ZeroDivisionError):
            pass
    
    # Try space-separated DMS: "37 46 29.64"
    parts = value.split()
    numbers = []
    for part in parts:
        try:
            numbers.append(float(part))
        except ValueError:
            continue
    
    if len(numbers) >= 2:
        degrees = numbers[0]
        minutes = numbers[1]
        seconds = numbers[2] if len(numbers) >= 3 else 0.0
        return degrees + minutes / 60 + seconds / 3600
    
    return None


def reverse_geocode(lat: float, lon: float) -> Optional[dict]:
    """
    Convert coordinates to a place name.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
    
    Returns:
        Dict with 'city', 'admin1' (state/county), 'cc' (country code), 'name'
        or None if geocoding fails
    """
    try:
        rg = _get_geocoder()
        # reverse_geocoder returns a list of results
        results = rg.search((lat, lon), mode=1)  # mode=1 for single result
        
        if results and len(results) > 0:
            result = results[0]
            return {
                'city': result.get('name', ''),
                'admin1': result.get('admin1', ''),  # State/Province/County
                'admin2': result.get('admin2', ''),  # County/District (more local)
                'country_code': result.get('cc', ''),
            }
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
    
    return None


def format_place_name(geocode_result: dict) -> str:
    """
    Format geocode result as "City, State/County, Country".
    
    Args:
        geocode_result: Result from reverse_geocode()
    
    Returns:
        Formatted place name string
    """
    if not geocode_result:
        return ""
    
    parts = []
    
    # City/Town/Village name
    city = geocode_result.get('city', '').strip()
    if city:
        parts.append(city)
    
    # State/Province/County (admin1 is usually the larger region)
    admin1 = geocode_result.get('admin1', '').strip()
    if admin1 and admin1 != city:
        parts.append(admin1)
    
    # Country code - could expand to full name if desired
    country = geocode_result.get('country_code', '').strip()
    if country:
        # Convert common country codes to full names
        country_names = {
            'US': 'USA',
            'GB': 'UK',
            'DE': 'Germany',
            'FR': 'France',
            'IT': 'Italy',
            'ES': 'Spain',
            'JP': 'Japan',
            'CN': 'China',
            'AU': 'Australia',
            'CA': 'Canada',
            'NL': 'Netherlands',
            'BE': 'Belgium',
            'CH': 'Switzerland',
            'AT': 'Austria',
            'SE': 'Sweden',
            'NO': 'Norway',
            'DK': 'Denmark',
            'FI': 'Finland',
            'IE': 'Ireland',
            'PT': 'Portugal',
            'GR': 'Greece',
            'PL': 'Poland',
            'CZ': 'Czech Republic',
            'HU': 'Hungary',
            'RU': 'Russia',
            'BR': 'Brazil',
            'MX': 'Mexico',
            'AR': 'Argentina',
            'IN': 'India',
            'NZ': 'New Zealand',
            'ZA': 'South Africa',
        }
        country = country_names.get(country, country)
        parts.append(country)
    
    return ', '.join(parts)


def get_place_name(lat_str: str, lon_str: str, 
                   lat_ref: Optional[str] = None, 
                   lon_ref: Optional[str] = None) -> Optional[str]:
    """
    Convert GPS coordinate strings to a formatted place name.
    
    This is the main entry point for the overlay feature.
    
    Args:
        lat_str: Latitude value as string (various formats supported)
        lon_str: Longitude value as string (various formats supported)
        lat_ref: Latitude reference (N or S)
        lon_ref: Longitude reference (E or W)
    
    Returns:
        Formatted place name like "San Francisco, California, USA" or None
    """
    lat = parse_gps_coordinate(lat_str, lat_ref)
    lon = parse_gps_coordinate(lon_str, lon_ref)
    
    if lat is None or lon is None:
        return None
    
    geocode_result = reverse_geocode(lat, lon)
    if geocode_result:
        return format_place_name(geocode_result)
    
    return None
