from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Use console email backend in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Add browsable API renderer in dev
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# Disable throttling in development
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405

# More verbose logging in development
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "INFO"  # noqa: F405

# Django Debug Toolbar (optional)
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass

# CORS allow all in development
CORS_ALLOW_ALL_ORIGINS = True

# Simplified channel layers for development (in-memory)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379/0")],  # noqa: F405
        },
    },
}
