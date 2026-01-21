"""URL configuration for Simple Photo Meta backend."""

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('api/', include('api.urls')),
    # Serve the frontend for all other routes
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
