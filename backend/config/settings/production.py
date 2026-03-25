from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Database connection pooling
DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405
DATABASES["default"]["OPTIONS"] = {  # noqa: F405
    "connect_timeout": 10,
    "options": "-c statement_timeout=30000",
}

# Cache timeout
CACHES["default"]["TIMEOUT"] = 300  # noqa: F405

# Session
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Static files
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# Logging in production - include file handler
LOGGING["handlers"]["file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": "/var/log/alertstream/app.log",
    "maxBytes": 50 * 1024 * 1024,
    "backupCount": 20,
    "formatter": "verbose",  # noqa: F405
}
LOGGING["root"]["handlers"] = ["console", "file"]  # noqa: F405

# Sentry integration
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )

# Email - use SMTP in production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Celery optimizations for production
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_POOL_LIMIT = 10
CELERY_REDIS_MAX_CONNECTIONS = 20
