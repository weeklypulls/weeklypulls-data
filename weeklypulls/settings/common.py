import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).parent.parent.absolute()
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'weeklypulls.apps.base',
    'weeklypulls.apps.pulls.apps.PullsConfig',
    'weeklypulls.apps.pull_lists.apps.ListsConfig',
    'weeklypulls.apps.comicvine.apps.ComicvineConfig',
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    )
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # enable this for site-wide caching
    # 'django.middleware.cache.UpdateCacheMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # enable this for site-wide caching
    # 'django.middleware.cache.FetchFromCacheMiddleware',
]

ROOT_URLCONF = 'weeklypulls.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'weeklypulls.wsgi.application'

db_from_env = dj_database_url.config()
db_from_env['TEST'] = {'NAME': 'wptest'}
DATABASES = {
    'default': db_from_env,
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.UserAttributeSimilarity'
            'Validator'),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.MinimumLengthValidator'),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.CommonPasswordValidator'),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'),
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

PROJECT_ROOT = BASE_DIR.parent

STATIC_ROOT =  PROJECT_ROOT / 'staticfiles'
STATIC_URL = '/static/'
SITE_ID = 1

# Simplified static file serving.
# https://warehouse.python.org/project/whitenoise/
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# caching
import django_cache_url
CACHES = {'default': django_cache_url.config(default='locmem://')}
CACHE_MIDDLEWARE_ALIAS = "weeklypulls"
CACHE_MIDDLEWARE_SECONDS = 300  # seconds
CACHE_MIDDLEWARE_KEY_PREFIX = "wps_"

# email config
DEFAULT_FROM_EMAIL = 'WeeklyPulls <staff@weeklypulls.com>'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.sendgrid.net')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = bool(os.environ.get('EMAIL_USE_TLS', True))

# location of weeklypulls-marvel (deprecated)
MAPI_URL = os.getenv('MAPI_URL', 'https://weeklypulls-marvel.herokuapp.com')

# ComicVine API configuration
COMICVINE_API_KEY = os.getenv('COMICVINE_API_KEY', '')
COMICVINE_API_BASE_URL = 'https://comicvine.gamespot.com/api'
COMICVINE_RATE_LIMIT_PER_HOUR = 200  # ComicVine's strict limit
COMICVINE_CACHE_EXPIRE_HOURS = 24  # How long to cache data