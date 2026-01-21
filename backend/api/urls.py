"""API URL configuration."""

from django.urls import path
from . import views

urlpatterns = [
    # Directory operations
    path('directories/open', views.OpenDirectoryView.as_view(), name='open-directory'),
    path('directories/scan', views.ScanDirectoryView.as_view(), name='scan-directory'),
    path('directories/scan/status', views.ScanStatusView.as_view(), name='scan-status'),
    path('directories/browse', views.BrowseDirectoryView.as_view(), name='browse-directory'),
    
    # Image operations
    path('images', views.ImageListView.as_view(), name='image-list'),
    path('images/thumbnail', views.ThumbnailView.as_view(), name='thumbnail'),
    path('images/preview', views.PreviewView.as_view(), name='preview'),
    path('images/open-in-viewer', views.OpenInSystemViewerView.as_view(), name='open-in-viewer'),
    
    # Metadata operations
    path('metadata', views.MetadataView.as_view(), name='metadata'),
    path('metadata/definitions', views.MetadataDefinitionsView.as_view(), name='metadata-definitions'),
    
    # Tag operations
    path('tags', views.TagListView.as_view(), name='tag-list'),
    path('tags/search', views.TagSearchView.as_view(), name='tag-search'),
    
    # Preferences
    path('preferences', views.PreferencesView.as_view(), name='preferences'),
    path('preferences/<str:key>', views.PreferenceDetailView.as_view(), name='preference-detail'),
]
