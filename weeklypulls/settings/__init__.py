import os

if os.getenv('WP_PROD', False):
    from .production import *
else:
    from .development import *