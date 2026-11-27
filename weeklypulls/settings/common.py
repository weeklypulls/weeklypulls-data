import os
from pathlib import Path

import dj_database_url
import django_cache_url

BASE_DIR = Path(__file__).parent.parent.absolute()
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.contrib.sites",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "django_filters",
    "weeklypulls.apps.base",
    "weeklypulls.apps.pulls.apps.PullsConfig",
    "weeklypulls.apps.pull_lists.apps.ListsConfig",
    "weeklypulls.apps.comicvine.apps.ComicvineConfig",
]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # enable this for site-wide caching
    # 'django.middleware.cache.UpdateCacheMiddleware',
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # enable this for site-wide caching
    # 'django.middleware.cache.FetchFromCacheMiddleware',
]

ROOT_URLCONF = "weeklypulls.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "weeklypulls.wsgi.application"

db_from_env = dj_database_url.config()
db_from_env["TEST"] = {"NAME": "wptest"}
DATABASES = {
    "default": db_from_env,
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarity"
            "Validator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.MinimumLengthValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "NumericPasswordValidator"),
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

PROJECT_ROOT = BASE_DIR.parent

STATIC_ROOT = PROJECT_ROOT / "staticfiles"
STATIC_URL = "/static/"
SITE_ID = 1

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# caching

CACHES = {"default": django_cache_url.config(default="locmem://")}
CACHE_MIDDLEWARE_ALIAS = "weeklypulls"
CACHE_MIDDLEWARE_SECONDS = 300  # seconds
CACHE_MIDDLEWARE_KEY_PREFIX = "wps_"

# email config
DEFAULT_FROM_EMAIL = "WeeklyPulls <staff@weeklypulls.com>"
# Email prints to the console unless EMAIL_BACKEND is set (e.g. to the SMTP backend).
_email_backend = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
_email_options = {}
if _email_backend == "django.core.mail.backends.smtp.EmailBackend":
    _email_options = {
        "host": os.environ.get("EMAIL_HOST", "smtp.sendgrid.net"),
        "port": int(os.environ.get("EMAIL_PORT", 587)),
        "username": os.environ.get("EMAIL_HOST_USER", ""),
        "password": os.environ.get("EMAIL_HOST_PASSWORD", ""),
        "use_tls": os.environ.get("EMAIL_USE_TLS", "true").lower()
        in ("1", "true", "yes"),
    }
MAILERS = {"default": {"BACKEND": _email_backend, "OPTIONS": _email_options}}

# Allauth/dj-rest-auth: turn off email verification while email is disabled
ACCOUNT_SIGNUP_FIELDS = ["email", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"


# ComicVine API configuration
COMICVINE_API_KEY = os.getenv("COMICVINE_API_KEY", "")
COMICVINE_API_BASE_URL = "https://comicvine.gamespot.com/api"
COMICVINE_RATE_LIMIT_PER_HOUR = 200  # ComicVine's strict limit
COMICVINE_CACHE_EXPIRE_HOURS = 24  # How long to cache data

# Logging: ensure all 500 errors are printed to console
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    # Catch-all for app loggers (e.g. weeklypulls.apps.*) that have no
    # explicit entry below; without this, their INFO/DEBUG records have
    # no handler anywhere in the chain and are silently dropped.
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        # Core Django logs
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        # Request/response errors (includes full tracebacks for 500s)
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        # Useful when running under gunicorn
        "gunicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
