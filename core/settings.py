from pathlib import Path
import os
from datetime import timedelta

from decouple import config
import dj_database_url


# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent


# Secret key should come from Render/environment variables in production
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')


# DEBUG should be False on Render, True only during local development
DEBUG = config('DEBUG', default=False, cast=bool)


# Hosts allowed to access the backend
# Example on Render: leak-monitor-backend.onrender.com
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')


# Required for secure POST requests from trusted domains
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://leak-monitor-backend.onrender.com'
).split(',')


INSTALLED_APPS = [
    # Default Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'corsheaders',
    'channels',

    # Required for JWT logout token blacklist
    'rest_framework_simplejwt.token_blacklist',

    # Project apps
    'accounts.apps.AccountsConfig',
    'sensors',
]


MIDDLEWARE = [
    # Allows Flutter/mobile/frontend apps to call this backend
    'corsheaders.middleware.CorsMiddleware',

    # Django security middleware
    'django.middleware.security.SecurityMiddleware',

    # Allows static files to work properly on Render
    'whitenoise.middleware.WhiteNoiseMiddleware',

    # Default Django middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# Main project URL configuration
ROOT_URLCONF = 'core.urls'


# Django templates configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # We are not using custom template folders now
        'DIRS': [],

        # Allows Django to find templates inside installed apps
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


# ASGI is used because this project has Channels/WebSocket support
ASGI_APPLICATION = 'core.asgi.application'


# Database setup
# On Render, DATABASE_URL will be used
# Locally, SQLite will be used so you do not need PostgreSQL installed on your laptop
DATABASE_URL = config('DATABASE_URL', default=None)

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Redis is used by Django Channels
# On Render, set REDIS_URL if WebSockets are needed
# Locally, this defaults to local Redis
REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379')


CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}


# Allow Flutter, Postman, and browser clients to call the API
# Fine for development. Later we can restrict this for production.
CORS_ALLOW_ALL_ORIGINS = True


# Static files configuration for Render
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Default primary key type for models
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework configuration
# JWT authentication means users login with access/refresh tokens
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}


# JWT token settings
# Access token keeps user logged in for 1 day
# Refresh token allows app to request a new access token for 30 days
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Firebase configuration switch
# Locally this stays False so migrations and server can run without Firebase credentials.
# On Render, set ENABLE_FIREBASE=True only when Firebase credentials are configured.
ENABLE_FIREBASE = config('ENABLE_FIREBASE', default=False, cast=bool)


# Email configuration
# Used for password reset, notifications, or future alerts
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER', default='')