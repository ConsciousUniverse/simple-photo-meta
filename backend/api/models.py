"""Django models for Simple Photo Meta."""

from django.db import models


class Tag(models.Model):
    """A metadata tag value."""
    tag = models.CharField(max_length=500)
    tag_type = models.CharField(max_length=100)
    
    class Meta:
        unique_together = ('tag', 'tag_type')
        ordering = ['tag']
    
    def __str__(self):
        return f"{self.tag} ({self.tag_type})"


class Image(models.Model):
    """An indexed image file."""
    path = models.CharField(max_length=2000, unique=True)
    tags = models.ManyToManyField(Tag, through='ImageTag', related_name='images')
    
    class Meta:
        ordering = ['path']
    
    def __str__(self):
        return self.path


class ImageTag(models.Model):
    """Association between images and tags."""
    image = models.ForeignKey(Image, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('image', 'tag')


class ScannedDirectory(models.Model):
    """Tracks which directories have been scanned."""
    path = models.CharField(max_length=2000, unique=True)
    last_scan = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.path


class Preference(models.Model):
    """User preferences storage."""
    key = models.CharField(max_length=100, primary_key=True)
    value = models.TextField()
    
    def __str__(self):
        return f"{self.key}={self.value}"
