import uuid

from django.db import models
from django.utils import timezone


class DeliveryLog(models.Model):
    """Comprehensive log of delivery operations across all channels."""

    class LogLevel(models.TextChoices):
        DEBUG = "debug", "Debug"
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="delivery_logs",
        db_index=True,
    )
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.CASCADE,
        related_name="delivery_logs",
        null=True,
        blank=True,
    )
    channel = models.CharField(max_length=20, db_index=True)
    provider = models.CharField(max_length=50, blank=True)
    level = models.CharField(
        max_length=10,
        choices=LogLevel.choices,
        default=LogLevel.INFO,
    )
    event = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Event type: queued, sent, delivered, opened, clicked, bounced, failed",
    )
    recipient = models.CharField(max_length=500, blank=True)
    message = models.TextField(blank=True)
    request_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Outgoing request payload (sensitive fields redacted)",
    )
    response_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider response payload",
    )
    status_code = models.IntegerField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    error_code = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "delivery_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["organization", "-timestamp"]),
            models.Index(fields=["channel", "event", "-timestamp"]),
            models.Index(fields=["notification", "-timestamp"]),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.channel}/{self.event}: {self.message[:80]}"


class DeliveryStatus(models.Model):
    """Aggregated delivery status per notification per channel."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        BOUNCED = "bounced", "Bounced"
        COMPLAINED = "complained", "Spam Complaint"
        FAILED = "failed", "Failed"
        DEFERRED = "deferred", "Deferred"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.CASCADE,
        related_name="delivery_statuses",
    )
    channel = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "delivery_status"
        ordering = ["-updated_at"]
        unique_together = [("notification", "channel")]
        indexes = [
            models.Index(fields=["status", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.notification_id} via {self.channel}: {self.status}"

    def mark_delivered(self):
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])

    def mark_opened(self):
        if self.status not in (self.Status.CLICKED,):
            self.status = self.Status.OPENED
        self.opened_at = timezone.now()
        self.save(update_fields=["status", "opened_at", "updated_at"])

    def mark_clicked(self, url=""):
        self.status = self.Status.CLICKED
        self.clicked_at = timezone.now()
        if url:
            self.metadata["clicked_url"] = url
        self.save(update_fields=["status", "clicked_at", "metadata", "updated_at"])

    def mark_bounced(self, error=""):
        self.status = self.Status.BOUNCED
        self.bounced_at = timezone.now()
        self.error_message = error
        self.save(update_fields=["status", "bounced_at", "error_message", "updated_at"])


class RetryLog(models.Model):
    """Log of retry attempts for failed deliveries."""

    class RetryStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        EXHAUSTED = "exhausted", "Retries Exhausted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.CASCADE,
        related_name="retry_logs",
    )
    channel = models.CharField(max_length=20)
    attempt_number = models.PositiveIntegerField()
    max_attempts = models.PositiveIntegerField(default=5)
    status = models.CharField(
        max_length=15,
        choices=RetryStatus.choices,
        default=RetryStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    backoff_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Time to wait before this retry attempt",
    )
    scheduled_at = models.DateTimeField(
        help_text="When this retry is scheduled to execute",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "delivery_retry_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"]),
            models.Index(fields=["notification", "channel"]),
        ]

    def __str__(self):
        return (
            f"Retry #{self.attempt_number} for {self.notification_id} "
            f"via {self.channel} [{self.status}]"
        )

    @property
    def is_retriable(self):
        return (
            self.status == self.RetryStatus.FAILED
            and self.attempt_number < self.max_attempts
        )

    def calculate_next_backoff(self):
        """Calculate exponential backoff for the next retry."""
        from django.conf import settings

        base = getattr(settings, "RETRY_BACKOFF_BASE", 60)
        multiplier = getattr(settings, "RETRY_BACKOFF_MULTIPLIER", 2)
        return base * (multiplier ** (self.attempt_number - 1))
