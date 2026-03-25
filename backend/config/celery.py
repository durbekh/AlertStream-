import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("alertstream")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(
    [
        "tasks",
        "apps.notifications",
        "apps.analytics",
    ]
)

app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "notifications": {"exchange": "notifications", "routing_key": "notifications"},
    "analytics": {"exchange": "analytics", "routing_key": "analytics"},
    "retries": {"exchange": "retries", "routing_key": "retries"},
}

app.conf.task_routes = {
    "tasks.notification_tasks.*": {"queue": "notifications"},
    "tasks.analytics_tasks.*": {"queue": "analytics"},
    "tasks.retry_tasks.*": {"queue": "retries"},
}

app.conf.beat_schedule = {
    "aggregate-delivery-stats-hourly": {
        "task": "tasks.analytics_tasks.aggregate_delivery_stats",
        "schedule": crontab(minute=0),
        "options": {"queue": "analytics"},
    },
    "cleanup-old-delivery-attempts": {
        "task": "tasks.analytics_tasks.cleanup_old_records",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "analytics"},
    },
    "process-retry-queue": {
        "task": "tasks.retry_tasks.process_retry_queue",
        "schedule": 30.0,
        "options": {"queue": "retries"},
    },
    "reset-rate-limit-counters": {
        "task": "tasks.analytics_tasks.reset_rate_limit_counters",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "default"},
    },
}

app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.timezone = "UTC"
app.conf.enable_utc = True
app.conf.task_track_started = True
app.conf.task_time_limit = 300
app.conf.task_soft_time_limit = 240
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_max_tasks_per_child = 1000
