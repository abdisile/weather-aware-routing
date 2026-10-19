import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
backend = str(BACKEND_DIR)
if backend not in sys.path:
    sys.path.insert(0, backend)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
