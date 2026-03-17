import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hirelink.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
app = application
