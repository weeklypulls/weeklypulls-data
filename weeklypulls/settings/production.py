from .common import *
from .sentry import init_sentry

init_sentry()

DEBUG = False
ALLOWED_HOSTS = [
    ".up.railway.app",
    "api.weeklypulls.com",
    # Railway's deploy health check sends this Host header.
    "healthcheck.railway.app",
]

CORS_ALLOWED_ORIGINS = [
    "https://weeklypulls.com",
    "https://client-production-6e474cc4.up.railway.app",
]

# Railway terminates TLS at its edge and sets X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# The health check calls the container over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^health/?$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365

# Email is deliberately off (console backend) until a provider is set up via
# EMAIL_BACKEND; see common.py.
SILENCED_SYSTEM_CHECKS = ["mail.E001"]
