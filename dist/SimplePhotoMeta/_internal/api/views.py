"""API Views for Simple Photo Meta."""

import os
import sys
import subprocess
from pathlib import Path
from django.http import FileResponse, Http404
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Tag, Image, ImageTag, Preference
from .serializers import (
    TagSerializer,
    ImageSerializer,
    PreferenceSerializer,
    DirectoryRequestSerializer,
    ImageListRequestSerializer,
    MetadataUpdateSerializer,
)
from .services import image_service, metadata_service, scan_service


class OpenInSystemViewerView(APIView):
    """Open an image in the system's default image viewer."""
    
    def post(self, request):
        image_path = request.data.get('path', '')
        
        if not image_path or not os.path.exists(image_path):
            return Response(
                {"error": "Image not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', image_path], check=True)
            elif sys.platform.startswith('linux'):
                subprocess.run(['xdg-open', image_path], check=True)
            elif sys.platform == 'win32':
                os.startfile(image_path)
            else:
                return Response(
                    {"error": "Unsupported platform"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({"success": True})
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BrowseDirectoryView(APIView):
    """Browse directories for folder selection."""
    
    def get(self, request):
        path = request.query_params.get('path', '')
        
        # Default to home directory if no path specified
        if not path:
            path = str(Path.home())
        
        # Expand ~ to home directory
        path = os.path.expanduser(path)
        
        # Validate path exists and is a directory
        if not os.path.exists(path):
            # Try parent directory
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
                if entry.is_file() and entry.name.lower().endswith(
                    ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.heif')
                ):
                    image_count += 1
        except PermissionError:
            pass
        
        return Response({
            'current': path,
            'parent': parent,
            'directories': subdirs,
            'image_count': image_count,
        })


class OpenDirectoryView(APIView):
    """Open a directory and get initial image list."""
    
    def post(self, request):
        serializer = DirectoryRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        folder_path = serializer.validated_data['path']
        
        if not os.path.isdir(folder_path):
            return Response(
                {"error": "Directory not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get images in folder
        images = scan_service.get_images_in_folder(folder_path)
        
        return Response({
            "folder": folder_path,
            "total_images": len(images),
            "images": images[:settings.DEFAULT_PAGE_SIZE],
            "page": 0,
            "page_size": settings.DEFAULT_PAGE_SIZE,
            "total_pages": (len(images) + settings.DEFAULT_PAGE_SIZE - 1) // settings.DEFAULT_PAGE_SIZE,
        })


class ScanDirectoryView(APIView):
    """Start or check directory scanning."""
    
    def post(self, request):
        serializer = DirectoryRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        folder_path = serializer.validated_data['path']
        
        if not os.path.isdir(folder_path):
            return Response(
                {"error": "Directory not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        started = scan_service.start_scan(folder_path)
        
        return Response({
            "started": started,
            "status": scan_service.get_scan_status(),
        })
    
    def delete(self, request):
        """Cancel current scan."""
        scan_service.cancel_scan()
        return Response({"cancelled": True})


class ScanStatusView(APIView):
    """Get current scan status."""
    
    def get(self, request):
        return Response(scan_service.get_scan_status())


class ImageListView(APIView):
    """Get paginated list of images."""
    
    def get(self, request):
        folder = request.query_params.get('folder')
        if not folder:
            return Response(
                {"error": "folder parameter required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        page = int(request.query_params.get('page', 0))
        page_size = int(request.query_params.get('page_size', settings.DEFAULT_PAGE_SIZE))
        search = request.query_params.get('search', '').strip()
        tag_type = request.query_params.get('tag_type', '').strip()
        
        # Get images based on search mode
        if search:
            # Search terms provided - filter by those terms (and optionally tag type)
            images = self._search_images(folder, search, tag_type, page, page_size)
            total = self._count_search_results(folder, search, tag_type)
        elif tag_type:
            # No search terms but tag_type selected - show images WITHOUT any tags of this type
            images = self._get_untagged_images(folder, tag_type, page, page_size)
            total = self._count_untagged_images(folder, tag_type)
        else:
            # No search terms and no tag_type - show all images
            all_images = scan_service.get_images_in_folder(folder)
            total = len(all_images)
            start = page * page_size
            images = all_images[start:start + page_size]
        
        return Response({
            "folder": folder,
            "images": images,
            "page": page,
            "page_size": page_size,
            "total_images": total,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        })
    
    def _search_images(self, folder: str, search: str, tag_type: str, page: int, page_size: int) -> list:
        """Search images by tag value."""
        folder_abs = os.path.abspath(folder)
        
        queryset = Image.objects.filter(path__startswith=folder_abs)
        
        # Search by tag
        tag_filter = Tag.objects.filter(tag__icontains=search)
        if tag_type:
            tag_filter = tag_filter.filter(tag_type=tag_type)
        
        queryset = queryset.filter(tags__in=tag_filter).distinct()
        
        start = page * page_size
        return list(queryset.values_list('path', flat=True)[start:start + page_size])
    
    def _count_search_results(self, folder: str, search: str, tag_type: str) -> int:
        """Count search results."""
        folder_abs = os.path.abspath(folder)
        
        queryset = Image.objects.filter(path__startswith=folder_abs)
        
        tag_filter = Tag.objects.filter(tag__icontains=search)
        if tag_type:
            tag_filter = tag_filter.filter(tag_type=tag_type)
        
        return queryset.filter(tags__in=tag_filter).distinct().count()
    
    def _get_untagged_images(self, folder: str, tag_type: str, page: int, page_size: int) -> list:
        """Get images that do NOT have any tags of the specified type."""
        folder_abs = os.path.abspath(folder)
        
        # Get all images in folder
        all_images_in_folder = set(scan_service.get_images_in_folder(folder))
        
        # Get images that HAVE tags of this type
        tagged_images = set(
            Image.objects.filter(
                path__startswith=folder_abs,
                tags__tag_type=tag_type
            ).distinct().values_list('path', flat=True)
        )
        
        # Untagged = all images minus those with tags of this type
        untagged = sorted(all_images_in_folder - tagged_images)
        
        start = page * page_size
        return untagged[start:start + page_size]
    
    def _count_untagged_images(self, folder: str, tag_type: str) -> int:
        """Count images that do NOT have any tags of the specified type."""
        folder_abs = os.path.abspath(folder)
        
        all_images_in_folder = set(scan_service.get_images_in_folder(folder))
        
        tagged_images = set(
            Image.objects.filter(
                path__startswith=folder_abs,
                tags__tag_type=tag_type
            ).distinct().values_list('path', flat=True)
        )
        
        return len(all_images_in_folder - tagged_images)


class ThumbnailView(APIView):
    """Get thumbnail for an image."""
    
    def get(self, request):
        image_path = request.query_params.get('path')
        if not image_path:
            return Response(
                {"error": "path parameter required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not os.path.isfile(image_path):
            raise Http404("Image not found")
        
        thumb_path = image_service.ensure_thumbnail_image(image_path)
        
        if not thumb_path or not os.path.isfile(thumb_path):
            raise Http404("Thumbnail generation failed")
        
        return FileResponse(open(thumb_path, 'rb'), content_type='image/jpeg')


class PreviewView(APIView):
    """Get preview for an image."""
    
    def get(self, request):
        image_path = request.query_params.get('path')
        if not image_path:
            return Response(
                {"error": "path parameter required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        edge_length = int(request.query_params.get('edge', settings.DEFAULT_PREVIEW_MAX_EDGE))
        
        if not os.path.isfile(image_path):
            raise Http404("Image not found")
        
        preview_path = image_service.ensure_preview_image(image_path, edge_length)
        
        if not preview_path or not os.path.isfile(preview_path):
            raise Http404("Preview generation failed")
        
        return FileResponse(open(preview_path, 'rb'), content_type='image/jpeg')


class MetadataView(APIView):
    """Get or update image metadata."""
    
    def get(self, request):
        image_path = request.query_params.get('path')
        if not image_path:
            return Response(
                {"error": "path parameter required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not os.path.isfile(image_path):
            raise Http404("Image not found")
        
        tag_type = request.query_params.get('tag_type')
        metadata_type = request.query_params.get('metadata_type', 'iptc')
        
        if tag_type:
            values = metadata_service.get_tag_values(image_path, tag_type, metadata_type)
            return Response({
                "path": image_path,
                "tag_type": tag_type,
                "metadata_type": metadata_type,
                "values": values,
            })
        else:
            metadata = metadata_service.get_metadata(image_path)
            return Response({
                "path": image_path,
                "metadata": metadata,
            })
    
    def put(self, request):
        serializer = MetadataUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        image_path = data['path']
        tag_type = data['tag_type']
        metadata_type = data['metadata_type']
        values = data['values']
        
        if not os.path.isfile(image_path):
            raise Http404("Image not found")
        
        success = metadata_service.set_tag_values(image_path, tag_type, values, metadata_type)
        
        if success:
            # Update database index
            self._update_index(image_path, tag_type, values)
            return Response({"success": True})
        else:
            return Response(
                {"error": "Failed to write metadata"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _update_index(self, image_path: str, tag_type: str, values: list):
        """Update the tag index for an image."""
        image_obj, _ = Image.objects.get_or_create(path=image_path)
        
        # Remove old tags of this type
        old_tags = Tag.objects.filter(tag_type=tag_type)
        ImageTag.objects.filter(image=image_obj, tag__in=old_tags).delete()
        
        # Add new tags
        for value in values:
            if value and value.strip():
                tag_obj, _ = Tag.objects.get_or_create(tag=value.strip(), tag_type=tag_type)
                ImageTag.objects.get_or_create(image=image_obj, tag=tag_obj)


class MetadataDefinitionsView(APIView):
    """Get available metadata tag definitions."""
    
    def get(self, request):
        return Response(metadata_service.get_tag_definitions())


class TagListView(APIView):
    """List all tags (for autocomplete)."""
    
    def get(self, request):
        tag_type = request.query_params.get('tag_type')
        
        queryset = Tag.objects.all()
        if tag_type:
            queryset = queryset.filter(tag_type=tag_type)
        
        tags = list(queryset.values_list('tag', flat=True).distinct().order_by('tag'))
        
        return Response({"tags": tags})


class TagSearchView(APIView):
    """Search tags."""
    
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        tag_type = request.query_params.get('tag_type')
        limit = int(request.query_params.get('limit', 20))
        
        queryset = Tag.objects.all()
        
        if query:
            queryset = queryset.filter(tag__icontains=query)
        
        if tag_type:
            queryset = queryset.filter(tag_type=tag_type)
        
        tags = list(queryset.values_list('tag', flat=True).distinct().order_by('tag')[:limit])
        
        return Response({"tags": tags})


class PreferencesView(APIView):
    """Get all preferences."""
    
    def get(self, request):
        prefs = Preference.objects.all()
        serializer = PreferenceSerializer(prefs, many=True)
        return Response({"preferences": serializer.data})


class PreferenceDetailView(APIView):
    """Get or set a single preference."""
    
    def get(self, request, key):
        try:
            pref = Preference.objects.get(key=key)
            return Response({"key": key, "value": pref.value})
        except Preference.DoesNotExist:
            return Response({"key": key, "value": None})
    
    def put(self, request, key):
        value = request.data.get('value', '')
        pref, _ = Preference.objects.update_or_create(
            key=key,
            defaults={'value': str(value)}
        )
        return Response({"key": key, "value": pref.value})
