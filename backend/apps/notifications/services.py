import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.channels.providers import get_provider
from apps.rate_limiting.services import RateLimitService
from apps.routing.models import RoutingRule
from apps.templates_engine.services import TemplateRenderService

from .models import DeliveryAttempt, Notification, NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:
    """Core service for creating and managing notifications."""

    @staticmethod
    @transaction.atomic
    def create_notification(
        organization,
        recipient: str,
        channels: list,
        subject: str = "",
        body: str = "",
        body_html: str = "",
        template_id: Optional[str] = None,
        context: Optional[dict] = None,
        metadata: Optional[dict] = None,
        recipient_data: Optional[dict] = None,
        priority: str = Notification.Priority.NORMAL,
        scheduled_at=None,
        expires_at=None,
        idempotency_key: str = "",
        external_id: str = "",
        group_id: str = "",
        created_by=None,
        api_key=None,
    ) -> Notification:
        """Create a notification and queue it for delivery."""

        # Check idempotency
        if idempotency_key:
            existing = Notification.objects.filter(
                organization=organization,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                logger.info(
                    f"Duplicate notification detected for idempotency_key={idempotency_key}"
                )
                return existing

        # Check organization quota
        if not organization.has_quota_remaining():
            raise ValueError("Organization has exceeded its notification quota.")

        # Apply routing rules to determine channels
        resolved_channels = NotificationService._apply_routing_rules(
            organization, channels, priority, metadata or {}
        )

        # Resolve template content
        if template_id:
            rendered = TemplateRenderService.render_template(
                template_id=template_id,
                context=context or {},
                organization=organization,
            )
            subject = rendered.get("subject", subject)
            body = rendered.get("body", body)
            body_html = rendered.get("body_html", body_html)

        notification = Notification.objects.create(
            organization=organization,
            created_by=created_by,
            api_key=api_key,
            recipient=recipient,
            recipient_data=recipient_data or {},
            template_id=template_id,
            subject=subject,
            body=body,
            body_html=body_html,
            context=context or {},
            metadata=metadata or {},
            channels=resolved_channels,
            status=Notification.Status.PENDING,
            priority=priority,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            external_id=external_id,
            group_id=group_id,
        )

        NotificationLog.objects.create(
            notification=notification,
            event_type=NotificationLog.EventType.CREATED,
            message=f"Notification created for channels: {resolved_channels}",
        )

        organization.increment_notification_count()

        return notification

    @staticmethod
    def _apply_routing_rules(organization, channels, priority, metadata):
        """Apply routing rules to modify channel selection."""
        rules = RoutingRule.objects.filter(
            organization=organization,
            is_active=True,
        ).order_by("priority")

        resolved = set(channels)

        for rule in rules:
            if rule.evaluate_conditions(priority=priority, metadata=metadata):
                if rule.action == "add":
                    resolved.update(rule.channels)
                elif rule.action == "remove":
                    resolved -= set(rule.channels)
                elif rule.action == "replace":
                    resolved = set(rule.channels)
                elif rule.action == "fallback":
                    # Only add fallback channels if primary channels are not available
                    pass

        return list(resolved)

    @staticmethod
    def process_notification(notification_id: str):
        """Process a notification by sending to all configured channels."""
        try:
            notification = Notification.objects.select_related(
                "organization"
            ).get(pk=notification_id)
        except Notification.DoesNotExist:
            logger.error(f"Notification {notification_id} not found")
            return

        if notification.status == Notification.Status.CANCELLED:
            logger.info(f"Notification {notification_id} is cancelled, skipping")
            return

        if notification.expires_at and timezone.now() > notification.expires_at:
            notification.status = Notification.Status.CANCELLED
            notification.save(update_fields=["status"])
            NotificationLog.objects.create(
                notification=notification,
                event_type=NotificationLog.EventType.CANCELLED,
                message="Notification expired before delivery",
            )
            return

        notification.status = Notification.Status.PROCESSING
        notification.save(update_fields=["status", "updated_at"])

        NotificationLog.objects.create(
            notification=notification,
            event_type=NotificationLog.EventType.PROCESSING,
            message="Processing notification for delivery",
        )

        results = {}
        for channel in notification.channels:
            result = NotificationService._deliver_to_channel(notification, channel)
            results[channel] = result

        # Determine overall status
        delivered_count = sum(1 for r in results.values() if r == "delivered")
        failed_count = sum(1 for r in results.values() if r == "failed")
        total = len(results)

        if delivered_count == total:
            notification.status = Notification.Status.DELIVERED
            notification.delivered_at = timezone.now()
        elif delivered_count > 0:
            notification.status = Notification.Status.PARTIALLY_DELIVERED
            notification.delivered_at = timezone.now()
        elif failed_count == total:
            notification.status = Notification.Status.FAILED
        else:
            notification.status = Notification.Status.PROCESSING

        notification.save(update_fields=["status", "delivered_at", "updated_at"])
        return results

    @staticmethod
    def _deliver_to_channel(notification, channel):
        """Deliver notification to a specific channel."""
        import time

        rate_limiter = RateLimitService()
        if not rate_limiter.check_rate_limit(notification.organization, channel):
            logger.warning(
                f"Rate limit exceeded for org={notification.organization_id} channel={channel}"
            )
            NotificationLog.objects.create(
                notification=notification,
                event_type=NotificationLog.EventType.FAILED,
                channel=channel,
                message="Rate limit exceeded",
            )
            return "rate_limited"

        attempt = DeliveryAttempt.objects.create(
            notification=notification,
            channel=channel,
            status=DeliveryAttempt.Status.SENDING,
        )

        start_time = time.time()

        try:
            provider = get_provider(channel, notification.organization)
            result = provider.send(
                recipient=notification.recipient,
                recipient_data=notification.recipient_data,
                subject=notification.subject,
                body=notification.body,
                body_html=notification.body_html,
                metadata=notification.metadata,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            attempt.status = DeliveryAttempt.Status.DELIVERED
            attempt.provider = result.get("provider", "")
            attempt.provider_message_id = result.get("message_id", "")
            attempt.response_code = result.get("status_code", 200)
            attempt.sent_at = timezone.now()
            attempt.delivered_at = timezone.now()
            attempt.duration_ms = duration_ms
            attempt.save()

            NotificationLog.objects.create(
                notification=notification,
                event_type=NotificationLog.EventType.DELIVERED,
                channel=channel,
                message=f"Delivered via {attempt.provider}",
                details=result,
            )

            return "delivered"

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            attempt.status = DeliveryAttempt.Status.FAILED
            attempt.error_message = str(e)
            attempt.error_code = type(e).__name__
            attempt.failed_at = timezone.now()
            attempt.duration_ms = duration_ms
            attempt.save()

            NotificationLog.objects.create(
                notification=notification,
                event_type=NotificationLog.EventType.FAILED,
                channel=channel,
                message=f"Delivery failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
            )

            logger.error(
                f"Failed to deliver notification {notification.id} via {channel}: {e}"
            )
            return "failed"

    @staticmethod
    def cancel_notification(notification_id: str, reason: str = ""):
        """Cancel a pending notification."""
        try:
            notification = Notification.objects.get(pk=notification_id)
        except Notification.DoesNotExist:
            raise ValueError("Notification not found")

        if notification.status not in (
            Notification.Status.PENDING,
            Notification.Status.QUEUED,
        ):
            raise ValueError(
                f"Cannot cancel notification in status: {notification.status}"
            )

        notification.status = Notification.Status.CANCELLED
        notification.save(update_fields=["status", "updated_at"])

        NotificationLog.objects.create(
            notification=notification,
            event_type=NotificationLog.EventType.CANCELLED,
            message=reason or "Cancelled by user",
        )

        return notification

    @staticmethod
    def get_notification_status(notification_id: str):
        """Get detailed status of a notification."""
        notification = Notification.objects.prefetch_related(
            "delivery_attempts", "logs"
        ).get(pk=notification_id)

        attempts = notification.delivery_attempts.all()
        return {
            "notification_id": str(notification.id),
            "status": notification.status,
            "channels": notification.channels,
            "delivery_attempts": [
                {
                    "channel": a.channel,
                    "status": a.status,
                    "attempt": a.attempt_number,
                    "provider": a.provider,
                    "error": a.error_message,
                    "delivered_at": a.delivered_at,
                }
                for a in attempts
            ],
            "created_at": notification.created_at,
            "delivered_at": notification.delivered_at,
        }
