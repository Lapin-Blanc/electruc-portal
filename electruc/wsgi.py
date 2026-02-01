"""WSGI config for electruc project."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "electruc.settings")

application = get_wsgi_application()
