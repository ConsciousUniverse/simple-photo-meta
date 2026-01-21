"""Serializers for API responses."""

from rest_framework import serializers
from .models import Tag, Image, Preference


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'tag', 'tag_type']


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ['id', 'path']


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preference
        fields = ['key', 'value']


class MetadataSerializer(serializers.Serializer):
    """Serializer for image metadata."""
    iptc = serializers.DictField(required=False)
    exif = serializers.DictField(required=False)


class DirectoryRequestSerializer(serializers.Serializer):
    """Serializer for directory operations."""
    path = serializers.CharField()


class ImageListRequestSerializer(serializers.Serializer):
    """Serializer for image list requests."""
    folder = serializers.CharField()
    page = serializers.IntegerField(default=0)
    page_size = serializers.IntegerField(default=25)
    search = serializers.CharField(required=False, allow_blank=True)
    tag_type = serializers.CharField(required=False, allow_blank=True)


class MetadataUpdateSerializer(serializers.Serializer):
    """Serializer for metadata updates."""
    path = serializers.CharField()
    tag_type = serializers.CharField()
    metadata_type = serializers.CharField()  # 'iptc' or 'exif'
    values = serializers.ListField(child=serializers.CharField())
