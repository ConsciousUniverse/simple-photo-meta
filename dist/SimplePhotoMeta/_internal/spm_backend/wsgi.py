"""
WSGI config for Simple Photo Meta backend.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spm_backend.settings')

application = get_wsgi_application()
