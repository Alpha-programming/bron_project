"""
Django settings for config project.
Unified Production-Ready Settings combining core setups, media paths,
and headless social authentication backends.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load Environment Variables from your root .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SECURITY CONFIGURATION ---
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-hi8c4#3e_pf7u6yhhyq*+5u%$uxnuhfi7l$03k(+g_+6y2%n)1')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

# --- AUTHENTICATION BACKENDS ---
AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # `allauth` specific authentication methods, such as login by email/socials
    'allauth.account.auth_backends.AuthenticationBackend',
    'oauth2_provider.backends.OAuth2Backend'
]

# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    # Admin Interface styling (Must be listed strictly above django.contrib.admin)
    'jazzmin',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Internal Core Modules
    'core.apps.CoreConfig',
    'corsheaders',

    # Django Ninja Extensions
    'ninja_extra',
    'ninja_jwt',

    # AllAuth Core Dependencies
    'allauth',
    'allauth.account',
    'allauth.headless',
    'oauth2_provider',
    'allauth.socialaccount',

    # Headless Social Auth Providers
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.telegram',
]

# --- MIDDLEWARE DEFINITION ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Kept high up to eliminate preflight blocks
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Headless Social Identity Providers Trackers
    'allauth.account.middleware.AccountMiddleware',
    'oauth2_provider.middleware.OAuth2TokenMiddleware'
]

ROOT_URLCONF = 'config.urls'

# --- TEMPLATE HOOKS ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # Required by allauth workflows
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- DATABASE LAYER ROUTER ---
# Prioritizes your PostgreSQL pool configuration, falling back gracefully to SQLite during local tests.
if os.getenv('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- IDENTITY MANAGEMENT SYSTEM ---
AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- INTERNATIONALIZATION & TIMEZONES ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# --- STATIC AND ASSET/MEDIA CHANNELS ---
STATIC_URL = 'static/'

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CORS & SECURITY POLICY ADJUSTMENTS ---
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

# --- JAZZMIN UI CONFIGURATION ---
JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "default_theme_mode": 'dark'
}

# --- HEADLESS & SOCIAL OAUTH PROVIDERS ---
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
HEADLESS_SERVE_SPECIFICATION = True

HEADLESS_CLIENTS = {
    "app": {
        "token_strategy": "allauth.headless.tokens.jwt.JWTTokenStrategy",
    },
    "browser": {},
}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'EMAIL_AUTHENTICATION': True,
        'FETCH_USERINFO': True,
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
            'secret': os.getenv('GOOGLE_SECRET', ''),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
            'phone'
        ],
        'AUTH_PARAMS': {
            'access_type': 'offline',
        }
    },
    'telegram': {
        'APP': {
            'client_id': os.getenv('TG_CLIENT_ID_LEGACY', ''),
            'secret': os.getenv('TG_LEGACY_TOKEN', ''),
        },
        'SCOPE': [
            'profile',
            'phone'
        ],
        'AUTH_PARAMS': {'auth_date_validity': 30},
    }
}

# --- DEVELOPMENT OUTBOUND MAIL ROUTER ---
# Prints confirmation codes directly out to the terminal console screen
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'