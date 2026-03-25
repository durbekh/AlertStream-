import logging
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def process_retry_queue(self):
    """Process pending retry attempts that are due for execution."""
    from apps.notifications.services import NotificationService

    from .models import DeliveryLog, DeliveryStatus, RetryLog

    now = timezone.now()
    pending_retries = RetryLog.objects.filter(
        status=RetryLog.RetryStatus.PENDING,
        scheduled_at__lte=now,
    ).select_related("notification", "notification__organization").order_by("scheduled_at")[:50]

    processed = 0

    for retry in pending_retries:
        retry.status = RetryLog.RetryStatus.IN_PROGRESS
        retry.started_at = now
        retry.save(update_fields=["status", "started_at"])

        notification = retry.notification

        start_time = time.time()
        try:
            result = NotificationService._deliver_to_channel(notification, retry.channel)
            duration_ms = int((time.time() - start_time) * 1000)

            if result == "delivered":
                retry.status = RetryLog.RetryStatus.SUCCESS
                retry.completed_at = timezone.now()
                retry.duration_ms = duration_ms

                DeliveryStatus.objects.update_or_create(
                    notification=notification,
                    channel=retry.channel,
                    defaults={
                        "status": DeliveryStatus.Status.DELIVERED,
                        "delivered_at": timezone.now(),
                        "attempts": retry.attempt_number,
                        "last_attempt_at": timezone.now(),
                    },
                )
            else:
                retry.status = RetryLog.RetryStatus.FAILED
                retry.completed_at = timezone.now()
                retry.duration_ms = duration_ms
                retry.error_message = f"Delivery returned: {result}"

                if retry.is_retriable:
                    _schedule_next_retry(retry)
                else:
                    retry.status = RetryLog.RetryStatus.EXHAUSTED

            retry.save()
            processed += 1

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            retry.status = RetryLog.RetryStatus.FAILED
            retry.completed_at = timezone.now()
            retry.duration_ms = duration_ms
            retry.error_message = str(e)
            retry.error_code = type(e).__name__
            retry.save()

            if retry.is_retriable:
                _schedule_next_retry(retry)

            logger.error(
                f"Retry #{retry.attempt_number} failed for notification "
                f"{retry.notification_id} via {retry.channel}: {e}"
            )

    if processed:
        logger.info(f"Processed {processed} retry attempts")

    return processed


def _schedule_next_retry(failed_retry):
    """Schedule the next retry attempt with exponential backoff."""
    from .models import RetryLog

    next_attempt = failed_retry.attempt_number + 1
    base = getattr(settings, "RETRY_BACKOFF_BASE", 60)
    multiplier = getattr(settings, "RETRY_BACKOFF_MULTIPLIER", 2)
    backoff = base * (multiplier ** (next_attempt - 1))
    max_backoff = 3600  # Cap at 1 hour
    backoff = min(backoff, max_backoff)

    scheduled_at = timezone.now() + timezone.timedelta(seconds=backoff)

    RetryLog.objects.create(
        notification=failed_retry.notification,
        channel=failed_retry.channel,
        attempt_number=next_attempt,
        max_attempts=failed_retry.max_attempts,
        status=RetryLog.RetryStatus.PENDING,
        backoff_seconds=backoff,
        scheduled_at=scheduled_at,
    )

    logger.info(
        f"Scheduled retry #{next_attempt} for notification "
        f"{failed_retry.notification_id} via {failed_retry.channel} "
        f"at {scheduled_at} (backoff: {backoff}s)"
    )


@shared_task
def schedule_retry_for_notification(notification_id, channel, error_message=""):
    """Create the first retry attempt for a failed notification delivery."""
    from apps.notifications.models import Notification

    from .models import RetryLog

    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found for retry scheduling")
        return

    max_attempts = getattr(settings, "MAX_RETRY_ATTEMPTS", 5)
    base_backoff = getattr(settings, "RETRY_BACKOFF_BASE", 60)
    scheduled_at = timezone.now() + timezone.timedelta(seconds=base_backoff)

    RetryLog.objects.create(
        notification=notification,
        channel=channel,
        attempt_number=1,
        max_attempts=max_attempts,
        status=RetryLog.RetryStatus.PENDING,
        error_message=error_message,
        backoff_seconds=base_backoff,
        scheduled_at=scheduled_at,
    )

    logger.info(
        f"Scheduled first retry for notification {notification_id} "
        f"via {channel} at {scheduled_at}"
    )


@shared_task
def cleanup_old_delivery_logs(days=30):
    """Remove delivery logs older than the specified number of days."""
    from .models import DeliveryLog

    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted_count, _ = DeliveryLog.objects.filter(timestamp__lt=cutoff).delete()
    logger.info(f"Cleaned up {deleted_count} delivery logs older than {days} days")
    return deleted_count
