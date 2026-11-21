from .common import *

DEBUG = False
ALLOWED_HOSTS = [".herokuapp.com", ".up.railway.app", "api.weeklypulls.com"]

CORS_ALLOWED_ORIGINS = [
    "https://weeklypulls.com",
    "https://weeklypulls-client.herokuapp.com",
    "https://client-production-6e474cc4.up.railway.app",
]

# Railway and Heroku terminate TLS at their edge and set X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
