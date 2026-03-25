import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_notification_task(self, notification_id):
    """Process a single notification through all configured channels."""
    from .services import NotificationService

    logger.info(f"Processing notification: {notification_id}")

    try:
        results = NotificationService.process_notification(notification_id)
        if results:
            delivered = sum(1 for r in results.values() if r == "delivered")
            failed = sum(1 for r in results.values() if r == "failed")
            logger.info(
                f"Notification {notification_id} processed: "
                f"{delivered} delivered, {failed} failed out of {len(results)} channels"
            )

            # Broadcast real-time update
            _broadcast_notification_update(notification_id)
        return results

    except Exception as e:
        logger.error(f"Error processing notification {notification_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def retry_notification_task(self, notification_id, channels=None):
    """Retry delivering a notification to specified or all channels."""
    from .models import Notification
    from .services import NotificationService

    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found for retry")
        return

    channels_to_retry = channels or notification.channels

    logger.info(
        f"Retrying notification {notification_id} on channels: {channels_to_retry}"
    )

    results = {}
    for channel in channels_to_retry:
        result = NotificationService._deliver_to_channel(notification, channel)
        results[channel] = result

    delivered = sum(1 for r in results.values() if r == "delivered")
    failed = sum(1 for r in results.values() if r == "failed")

    # Update notification status based on retry results
    if delivered > 0 and notification.status != Notification.Status.DELIVERED:
        if delivered == len(results):
            notification.status = Notification.Status.DELIVERED
        else:
            notification.status = Notification.Status.PARTIALLY_DELIVERED
        notification.delivered_at = timezone.now()
        notification.save(update_fields=["status", "delivered_at", "updated_at"])

    _broadcast_notification_update(notification_id)
    return results


@shared_task
def process_scheduled_notifications():
    """Find and process notifications that are scheduled for delivery."""
    from .models import Notification

    now = timezone.now()

    scheduled = Notification.objects.filter(
        status=Notification.Status.PENDING,
        scheduled_at__lte=now,
        scheduled_at__isnull=False,
    ).values_list("id", flat=True)[:100]

    count = 0
    for notification_id in scheduled:
        Notification.objects.filter(pk=notification_id).update(
            status=Notification.Status.QUEUED
        )
        process_notification_task.delay(str(notification_id))
        count += 1

    if count:
        logger.info(f"Queued {count} scheduled notifications for processing")

    return count


@shared_task
def send_batch_notifications(notification_ids):
    """Process a batch of notifications in parallel."""
    from celery import group

    tasks = [process_notification_task.s(nid) for nid in notification_ids]
    job = group(tasks)
    result = job.apply_async()

    logger.info(f"Dispatched batch of {len(notification_ids)} notifications")
    return {"batch_size": len(notification_ids), "group_id": str(result.id)}


@shared_task
def cleanup_expired_notifications():
    """Mark expired notifications as cancelled."""
    from .models import Notification, NotificationLog

    now = timezone.now()
    expired = Notification.objects.filter(
        status__in=[Notification.Status.PENDING, Notification.Status.QUEUED],
        expires_at__lt=now,
    )

    count = 0
    for notification in expired:
        notification.status = Notification.Status.CANCELLED
        notification.save(update_fields=["status", "updated_at"])

        NotificationLog.objects.create(
            notification=notification,
            event_type=NotificationLog.EventType.CANCELLED,
            message="Notification expired before delivery",
        )
        count += 1

    if count:
        logger.info(f"Cancelled {count} expired notifications")

    return count


def _broadcast_notification_update(notification_id):
    """Send a real-time WebSocket update for a notification."""
    try:
        from .models import Notification

        notification = Notification.objects.get(pk=notification_id)
        from .consumers import send_notification_update

        send_notification_update(
            str(notification.organization_id),
            {
                "notification_id": str(notification.id),
                "status": notification.status,
                "recipient": notification.recipient,
                "channels": notification.channels,
                "delivered_at": (
                    notification.delivered_at.isoformat()
                    if notification.delivered_at
                    else None
                ),
                "updated_at": notification.updated_at.isoformat(),
            },
        )
    except Exception as e:
        logger.warning(f"Failed to broadcast notification update: {e}")
