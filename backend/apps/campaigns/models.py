import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    """Campaign for sending bulk notifications to subscriber segments."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING = "sending", "Sending"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    class CampaignType(models.TextChoices):
        ONE_TIME = "one_time", "One-Time"
        RECURRING = "recurring", "Recurring"
        TRIGGERED = "triggered", "Triggered"
        AB_TEST = "ab_test", "A/B Test"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="campaigns",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    campaign_type = models.CharField(
        max_length=20,
        choices=CampaignType.choices,
        default=CampaignType.ONE_TIME,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # Content
    template = models.ForeignKey(
        "templates_engine.NotificationTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    subject_override = models.CharField(max_length=500, blank=True)
    body_override = models.TextField(blank=True)
    channels = models.JSONField(
        default=list,
        help_text='Channels to deliver through: ["email", "sms", "push", "slack"]',
    )
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Static context data merged with subscriber-specific data",
    )

    # Targeting
    send_to_all = models.BooleanField(
        default=False,
        help_text="Send to all active subscribers regardless of segments",
    )
    estimated_recipients = models.PositiveIntegerField(default=0)

    # Tracking
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)

    # Metadata
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_campaigns",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "campaigns_campaign"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.get_status_display()}]"

    @property
    def delivery_rate(self):
        if self.total_sent == 0:
            return 0.0
        return round((self.total_delivered / self.total_sent) * 100, 2)

    @property
    def open_rate(self):
        if self.total_delivered == 0:
            return 0.0
        return round((self.total_opened / self.total_delivered) * 100, 2)

    @property
    def click_rate(self):
        if self.total_delivered == 0:
            return 0.0
        return round((self.total_clicked / self.total_delivered) * 100, 2)

    def can_start(self):
        return self.status in (self.Status.DRAFT, self.Status.SCHEDULED)

    def mark_started(self):
        self.status = self.Status.SENDING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])


class CampaignSegment(models.Model):
    """Links a campaign to subscriber segments for targeting."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="segments",
    )
    subscriber_group = models.ForeignKey(
        "subscribers.SubscriberGroup",
        on_delete=models.CASCADE,
        related_name="campaign_segments",
    )
    is_excluded = models.BooleanField(
        default=False,
        help_text="If True, this segment is excluded from the campaign",
    )

    class Meta:
        db_table = "campaigns_segment"
        unique_together = [("campaign", "subscriber_group")]

    def __str__(self):
        prefix = "Exclude" if self.is_excluded else "Include"
        return f"{prefix}: {self.subscriber_group.name} in {self.campaign.name}"


class CampaignSchedule(models.Model):
    """Scheduling configuration for campaigns."""

    class RecurrenceType(models.TextChoices):
        NONE = "none", "None (One-Time)"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Bi-Weekly"
        MONTHLY = "monthly", "Monthly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name="schedule",
    )
    scheduled_at = models.DateTimeField(
        help_text="When to start sending the campaign",
    )
    send_window_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Earliest time of day to send (respects subscriber timezone)",
    )
    send_window_end = models.TimeField(
        null=True,
        blank=True,
        help_text="Latest time of day to send (respects subscriber timezone)",
    )
    timezone = models.CharField(max_length=50, default="UTC")
    recurrence = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
        default=RecurrenceType.NONE,
    )
    recurrence_end_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to stop recurring campaigns",
    )
    max_recurrences = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of recurrences",
    )
    recurrence_count = models.PositiveIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "campaigns_schedule"

    def __str__(self):
        return f"Schedule for {self.campaign.name}: {self.scheduled_at}"

    @property
    def is_recurring(self):
        return self.recurrence != self.RecurrenceType.NONE

    def should_run(self):
        if not self.campaign.can_start():
            return False
        now = timezone.now()
        if self.next_run_at and now >= self.next_run_at:
            return True
        if not self.last_run_at and now >= self.scheduled_at:
            return True
        return False


class CampaignResult(models.Model):
    """Individual delivery result for a campaign recipient."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        BOUNCED = "bounced", "Bounced"
        FAILED = "failed", "Failed"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="results",
    )
    subscriber = models.ForeignKey(
        "subscribers.Subscriber",
        on_delete=models.CASCADE,
        related_name="campaign_results",
    )
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_result",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    channel = models.CharField(max_length=20, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "campaigns_result"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["campaign", "status"]),
            models.Index(fields=["subscriber", "-created_at"]),
        ]
        unique_together = [("campaign", "subscriber")]

    def __str__(self):
        return f"{self.campaign.name} -> {self.subscriber} [{self.status}]"
