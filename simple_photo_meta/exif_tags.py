exif_writable_tags = [
    {
        "tag": "Artist",
        "name": "Artist",
        "description": "Name of the photographer or creator.",
        "multi_valued": False,
    },
    {
        "tag": "Copyright",
        "name": "Copyright",
        "description": "Copyright notice for the image.",
        "multi_valued": False,
    },
    {
        "tag": "ImageDescription",
        "name": "Image Description",
        "description": "A description of the image content.",
        "multi_valued": False,
    },
    {
        "tag": "UserComment",
        "name": "User Comment",
        "description": "User-defined comment or notes.",
        "multi_valued": False,
    },
    {
        "tag": "Software",
        "name": "Software",
        "description": "Software used to create or process the image.",
        "multi_valued": False,
    },
    {
        "tag": "Make",
        "name": "Camera Make",
        "description": "Manufacturer of the camera.",
        "multi_valued": False,
    },
    {
        "tag": "Model",
        "name": "Camera Model",
        "description": "Model of the camera.",
        "multi_valued": False,
    },
    {
        "tag": "DateTimeOriginal",
        "name": "Date/Time Original",
        "description": "Date and time when the photo was taken (YYYY:MM:DD HH:MM:SS).",
        "multi_valued": False,
    },
    {
        "tag": "GPSLatitude",
        "name": "GPS Latitude",
        "description": "Latitude coordinate (e.g., 37.7749 or 37deg 46' 29.64\"N).",
        "multi_valued": False,
    },
    {
        "tag": "GPSLongitude",
        "name": "GPS Longitude",
        "description": "Longitude coordinate (e.g., -122.4194 or 122deg 25' 9.84\"W).",
        "multi_valued": False,
    },
    {
        "tag": "GPSAltitude",
        "name": "GPS Altitude",
        "description": "Altitude in meters above sea level.",
        "multi_valued": False,
    },
]

exif_writable_fields_list = [t["tag"] for t in exif_writable_tags]
