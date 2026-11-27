import os

from .common import *

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
