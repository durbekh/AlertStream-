import hashlib
import hmac
import json
import logging
import time
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DeliveryService:
    """Central service for managing notification delivery across channels."""

    @staticmethod
    def deliver(notification, channel):
        """Deliver a notification through the specified channel.

        Handles provider selection, rate limiting, logging, and retry scheduling.
        """
        from apps.channels.models import Channel
        from apps.rate_limiting.services import RateLimitService

        from .models import DeliveryLog, DeliveryStatus

        org = notification.organization

        # Find the active channel configuration
        channel_config = Channel.objects.filter(
            organization=org,
            channel_type=channel,
            is_active=True,
        ).first()

        if not channel_config:
            DeliveryService._log(
                org, notification, channel, "error", "no_config",
                f"No active {channel} channel configured",
            )
            return {"status": "failed", "error": "No channel configuration found"}

        # Check daily capacity
        if not channel_config.has_daily_capacity:
            DeliveryService._log(
                org, notification, channel, "warning", "daily_limit_reached",
                f"Daily limit of {channel_config.daily_limit} reached",
            )
            return {"status": "rate_limited", "error": "Daily message limit reached"}

        # Check rate limit
        rate_limiter = RateLimitService()
        if not rate_limiter.check_rate_limit(org, channel):
            DeliveryService._log(
                org, notification, channel, "warning", "rate_limited",
                "Rate limit exceeded",
            )
            return {"status": "rate_limited", "error": "Rate limit exceeded"}

        # Create or update delivery status
        delivery_status, _ = DeliveryStatus.objects.update_or_create(
            notification=notification,
            channel=channel,
            defaults={
                "status": DeliveryStatus.Status.SENDING,
                "provider": channel_config.name,
                "last_attempt_at": timezone.now(),
            },
        )
        delivery_status.attempts += 1
        delivery_status.save(update_fields=["attempts"])

        # Execute delivery
        start_time = time.time()
        try:
            from apps.channels.providers import get_provider

            provider = get_provider(channel, org)
            result = provider.send(
                recipient=notification.recipient,
                recipient_data=notification.recipient_data,
                subject=notification.subject,
                body=notification.body,
                body_html=notification.body_html,
                metadata=notification.metadata,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            delivery_status.mark_delivered()
            delivery_status.provider_message_id = result.get("message_id", "")
            delivery_status.cost = result.get("cost", 0)
            delivery_status.save(update_fields=["provider_message_id", "cost"])

            channel_config.increment_message_count()

            DeliveryService._log(
                org, notification, channel, "info", "delivered",
                f"Delivered via {channel_config.name}",
                provider=channel_config.name,
                status_code=result.get("status_code", 200),
                duration_ms=duration_ms,
                provider_message_id=result.get("message_id", ""),
            )

            return {"status": "delivered", "message_id": result.get("message_id", "")}

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            delivery_status.status = DeliveryStatus.Status.FAILED
            delivery_status.error_message = str(e)
            delivery_status.save(update_fields=["status", "error_message", "updated_at"])

            DeliveryService._log(
                org, notification, channel, "error", "failed",
                f"Delivery failed: {str(e)}",
                provider=channel_config.name,
                duration_ms=duration_ms,
                error_code=type(e).__name__,
            )

            # Schedule retry
            from .tasks import schedule_retry_for_notification
            schedule_retry_for_notification.delay(
                str(notification.id), channel, str(e)
            )

            return {"status": "failed", "error": str(e)}

    @staticmethod
    def handle_webhook_event(provider, event_type, payload):
        """Process incoming webhook events from providers (opens, clicks, bounces)."""
        from .models import DeliveryLog, DeliveryStatus

        provider_message_id = payload.get("message_id", "")

        if not provider_message_id:
            logger.warning(f"Webhook event from {provider} missing message_id")
            return

        try:
            status_obj = DeliveryStatus.objects.get(
                provider_message_id=provider_message_id
            )
        except DeliveryStatus.DoesNotExist:
            logger.warning(
                f"No delivery status found for provider_message_id: {provider_message_id}"
            )
            return

        event_map = {
            "delivered": status_obj.mark_delivered,
            "opened": status_obj.mark_opened,
            "clicked": lambda: status_obj.mark_clicked(payload.get("url", "")),
            "bounced": lambda: status_obj.mark_bounced(payload.get("error", "")),
        }

        handler = event_map.get(event_type)
        if handler:
            handler()
            logger.info(
                f"Processed {event_type} event for message {provider_message_id}"
            )
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")

    @staticmethod
    def send_webhook(url, payload, method="POST", headers=None, auth_type="none",
                     auth_credentials=None, signing_secret="", timeout=30, verify_ssl=True):
        """Send a webhook request with configurable auth and signing."""
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        body = json.dumps(payload)

        # Apply authentication
        auth = None
        if auth_type == "basic":
            auth = (
                auth_credentials.get("username", ""),
                auth_credentials.get("password", ""),
            )
        elif auth_type == "bearer":
            request_headers["Authorization"] = f"Bearer {auth_credentials.get('token', '')}"
        elif auth_type == "hmac" and signing_secret:
            signature = hmac.new(
                signing_secret.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"
        elif auth_type == "custom_header":
            header_name = auth_credentials.get("header_name", "X-Auth-Token")
            header_value = auth_credentials.get("header_value", "")
            request_headers[header_name] = header_value

        response = requests.request(
            method=method,
            url=url,
            data=body,
            headers=request_headers,
            auth=auth,
            timeout=timeout,
            verify=verify_ssl,
        )
        response.raise_for_status()

        return {
            "status_code": response.status_code,
            "body": response.text[:2000],
            "headers": dict(response.headers),
        }

    @staticmethod
    def _log(organization, notification, channel, level, event, message, **kwargs):
        """Create a delivery log entry."""
        from .models import DeliveryLog

        DeliveryLog.objects.create(
            organization=organization,
            notification=notification,
            channel=channel,
            level=level,
            event=event,
            message=message,
            provider=kwargs.get("provider", ""),
            status_code=kwargs.get("status_code"),
            duration_ms=kwargs.get("duration_ms"),
            provider_message_id=kwargs.get("provider_message_id", ""),
            error_code=kwargs.get("error_code", ""),
            recipient=notification.recipient if notification else "",
        )
