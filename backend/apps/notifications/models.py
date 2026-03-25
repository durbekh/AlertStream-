import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Core notification model tracking a single notification request."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        DELIVERED = "delivered", "Delivered"
        PARTIALLY_DELIVERED = "partially_delivered", "Partially Delivered"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    api_key = models.ForeignKey(
        "accounts.APIKey",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    # Recipient information
    recipient = models.CharField(
        max_length=500,
        help_text="Primary recipient identifier (email, phone, user_id, etc.)",
    )
    recipient_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional recipient data: {email, phone, slack_id, device_token, etc.}",
    )

    # Content
    template = models.ForeignKey(
        "templates_engine.NotificationTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Template context variables for rendering",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary metadata attached to the notification",
    )

    # Delivery
    channels = models.JSONField(
        default=list,
        help_text='List of channels: ["email", "sms", "push", "slack", "telegram", "whatsapp", "webhook"]',
    )
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    # Scheduling
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule notification for future delivery",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Do not deliver after this time",
    )

    # Tracking
    idempotency_key = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Unique key to prevent duplicate notifications",
    )
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External reference ID from the caller",
    )
    group_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Group related notifications together",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["recipient", "organization"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="unique_idempotency_key_per_org",
            ),
        ]

    def __str__(self):
        return f"Notification {self.id} to {self.recipient} [{self.status}]"


class NotificationLog(models.Model):
    """Log entry for notification lifecycle events."""

    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"
        CANCELLED = "cancelled", "Cancelled"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        BOUNCED = "bounced", "Bounced"
        COMPLAINED = "complained", "Complained"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    channel = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["notification", "-timestamp"]),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.event_type} - {self.notification_id}"


class DeliveryAttempt(models.Model):
    """Tracks individual delivery attempts per channel."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        BOUNCED = "bounced", "Bounced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="delivery_attempts",
    )
    channel = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email"),
            ("sms", "SMS"),
            ("push", "Push Notification"),
            ("slack", "Slack"),
            ("telegram", "Telegram"),
            ("whatsapp", "WhatsApp"),
            ("webhook", "Webhook"),
        ],
    )
    provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Provider used for this attempt (e.g., sendgrid, twilio)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempt_number = models.PositiveIntegerField(default=1)
    max_attempts = models.PositiveIntegerField(default=5)

    # Response tracking
    provider_message_id = models.CharField(max_length=255, blank=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)

    # Cost tracking
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    currency = models.CharField(max_length=3, default="USD")

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time taken for the delivery attempt in milliseconds",
    )

    class Meta:
        db_table = "notifications_delivery_attempt"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["notification", "channel"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self):
        return f"Attempt #{self.attempt_number} via {self.channel} [{self.status}]"

    @property
    def can_retry(self):
        return (
            self.status == self.Status.FAILED
            and self.attempt_number < self.max_attempts
        )
