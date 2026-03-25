import uuid

from django.db import models


class DeliveryAnalytics(models.Model):
    """Aggregated delivery statistics per organization, channel, and time period."""

    class Granularity(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="delivery_analytics",
        db_index=True,
    )
    channel = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Notification channel (email, sms, push, slack, webhook, or 'all')",
    )
    granularity = models.CharField(
        max_length=10,
        choices=Granularity.choices,
        default=Granularity.DAILY,
    )
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField()

    # Volume metrics
    total_sent = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    total_bounced = models.PositiveIntegerField(default=0)
    total_deferred = models.PositiveIntegerField(default=0)

    # Rate metrics (percentages stored as decimals, e.g., 0.95 = 95%)
    delivery_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    failure_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # Performance metrics
    avg_delivery_time_ms = models.IntegerField(
        default=0,
        help_text="Average time from send to delivery confirmation in milliseconds",
    )
    p95_delivery_time_ms = models.IntegerField(
        default=0,
        help_text="95th percentile delivery time in milliseconds",
    )
    p99_delivery_time_ms = models.IntegerField(
        default=0,
        help_text="99th percentile delivery time in milliseconds",
    )

    # Cost metrics
    total_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    avg_cost_per_message = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    # Retry metrics
    total_retries = models.PositiveIntegerField(default=0)
    retry_success_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_delivery"
        ordering = ["-period_start"]
        unique_together = [("organization", "channel", "granularity", "period_start")]
        indexes = [
            models.Index(fields=["organization", "granularity", "-period_start"]),
            models.Index(fields=["channel", "granularity", "-period_start"]),
        ]

    def __str__(self):
        return (
            f"{self.organization.name} - {self.channel} "
            f"({self.granularity}: {self.period_start.date()})"
        )

    @property
    def delivery_rate_percent(self):
        return round(float(self.delivery_rate) * 100, 2)

    @property
    def bounce_rate_percent(self):
        return round(float(self.bounce_rate) * 100, 2)


class EngagementMetrics(models.Model):
    """Engagement analytics tracking opens, clicks, and conversions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="engagement_metrics",
        db_index=True,
    )
    channel = models.CharField(max_length=20, db_index=True)
    granularity = models.CharField(
        max_length=10,
        choices=DeliveryAnalytics.Granularity.choices,
        default=DeliveryAnalytics.Granularity.DAILY,
    )
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField()

    # Engagement counts
    total_delivered = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    unique_opens = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    total_unsubscribed = models.PositiveIntegerField(default=0)
    total_complained = models.PositiveIntegerField(default=0)

    # Rate metrics
    open_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    click_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    click_to_open_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    unsubscribe_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    complaint_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # Link tracking
    top_clicked_links = models.JSONField(
        default=list,
        blank=True,
        help_text='Top clicked links: [{"url": "...", "clicks": 42}]',
    )

    # Device/client breakdown
    device_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"desktop": 60, "mobile": 35, "tablet": 5}',
    )
    client_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"gmail": 30, "outlook": 25, "apple_mail": 20, "other": 25}',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_engagement"
        ordering = ["-period_start"]
        unique_together = [("organization", "channel", "granularity", "period_start")]
        indexes = [
            models.Index(fields=["organization", "granularity", "-period_start"]),
        ]

    def __str__(self):
        return (
            f"{self.organization.name} - {self.channel} engagement "
            f"({self.granularity}: {self.period_start.date()})"
        )

    @property
    def open_rate_percent(self):
        return round(float(self.open_rate) * 100, 2)

    @property
    def click_rate_percent(self):
        return round(float(self.click_rate) * 100, 2)
