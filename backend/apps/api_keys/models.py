import uuid

from django.db import models
from django.utils import timezone


class APIKey(models.Model):
    """Extended API key model with usage tracking and scoped access control.

    Note: The primary APIKey model is in apps.accounts.models.
    This model provides additional rate limiting and usage tracking.
    """

    class Tier(models.TextChoices):
        FREE = "free", "Free"
        BASIC = "basic", "Basic"
        PRO = "pro", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_api_key = models.OneToOneField(
        "accounts.APIKey",
        on_delete=models.CASCADE,
        related_name="extended_config",
    )
    tier = models.CharField(
        max_length=20,
        choices=Tier.choices,
        default=Tier.FREE,
    )
    allowed_channels = models.JSONField(
        default=list,
        blank=True,
        help_text='Channels this key can use: ["email", "sms", "push"]',
    )
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="IP whitelist. Empty means all IPs allowed.",
    )
    allowed_origins = models.JSONField(
        default=list,
        blank=True,
        help_text="CORS origins. Empty means all origins allowed.",
    )
    webhook_url = models.URLField(
        blank=True,
        help_text="Webhook URL for delivery status callbacks",
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret for signing webhook payloads",
    )
    daily_request_count = models.PositiveIntegerField(default=0)
    daily_request_limit = models.PositiveIntegerField(
        default=10000,
        help_text="Maximum API requests per day",
    )
    monthly_request_count = models.PositiveIntegerField(default=0)
    monthly_notification_limit = models.PositiveIntegerField(
        default=100000,
        help_text="Maximum notifications per month",
    )
    monthly_notification_count = models.PositiveIntegerField(default=0)
    last_reset_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_keys_extended"
        verbose_name = "API Key Config"
        verbose_name_plural = "API Key Configs"

    def __str__(self):
        return f"Config for {self.account_api_key.name} ({self.tier})"

    @property
    def has_daily_capacity(self):
        return self.daily_request_count < self.daily_request_limit

    @property
    def has_monthly_capacity(self):
        return self.monthly_notification_count < self.monthly_notification_limit

    def increment_daily_count(self):
        APIKey.objects.filter(pk=self.pk).update(
            daily_request_count=models.F("daily_request_count") + 1
        )

    def increment_monthly_notification_count(self):
        APIKey.objects.filter(pk=self.pk).update(
            monthly_notification_count=models.F("monthly_notification_count") + 1
        )

    def reset_daily_counts(self):
        self.daily_request_count = 0
        self.save(update_fields=["daily_request_count", "updated_at"])

    def reset_monthly_counts(self):
        self.monthly_request_count = 0
        self.monthly_notification_count = 0
        self.last_reset_at = timezone.now()
        self.save(update_fields=[
            "monthly_request_count", "monthly_notification_count",
            "last_reset_at", "updated_at",
        ])

    def is_ip_allowed(self, ip_address):
        if not self.allowed_ips:
            return True
        return ip_address in self.allowed_ips

    def is_channel_allowed(self, channel):
        if not self.allowed_channels:
            return True
        return channel in self.allowed_channels


class RateLimit(models.Model):
    """Configurable rate limits per organization or API key."""

    class LimitScope(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        API_KEY = "api_key", "API Key"
        CHANNEL = "channel", "Channel"
        GLOBAL = "global", "Global"

    class WindowType(models.TextChoices):
        SECOND = "second", "Per Second"
        MINUTE = "minute", "Per Minute"
        HOUR = "hour", "Per Hour"
        DAY = "day", "Per Day"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="rate_limits",
        null=True,
        blank=True,
    )
    api_key = models.ForeignKey(
        "accounts.APIKey",
        on_delete=models.CASCADE,
        related_name="rate_limits",
        null=True,
        blank=True,
    )
    scope = models.CharField(
        max_length=20,
        choices=LimitScope.choices,
        default=LimitScope.ORGANIZATION,
    )
    resource = models.CharField(
        max_length=100,
        help_text="Resource being limited (e.g., 'notifications', 'email', 'api_calls')",
    )
    window_type = models.CharField(
        max_length=10,
        choices=WindowType.choices,
        default=WindowType.HOUR,
    )
    max_requests = models.PositiveIntegerField(
        help_text="Maximum number of requests within the time window",
    )
    current_count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField(auto_now_add=True)
    burst_limit = models.PositiveIntegerField(
        default=0,
        help_text="Allow short burst above max_requests (0 = no burst)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_keys_rate_limit"
        ordering = ["scope", "resource"]
        indexes = [
            models.Index(fields=["organization", "resource", "is_active"]),
            models.Index(fields=["api_key", "resource", "is_active"]),
        ]

    def __str__(self):
        return (
            f"RateLimit: {self.resource} - {self.max_requests}/{self.window_type} "
            f"({self.scope})"
        )

    @property
    def window_seconds(self):
        mapping = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        return mapping.get(self.window_type, 3600)

    def is_within_window(self):
        elapsed = (timezone.now() - self.window_start).total_seconds()
        return elapsed < self.window_seconds

    def check_limit(self):
        """Check if the current request is within the rate limit."""
        if not self.is_active:
            return True

        if not self.is_within_window():
            self.current_count = 0
            self.window_start = timezone.now()
            self.save(update_fields=["current_count", "window_start"])

        effective_limit = self.max_requests + self.burst_limit
        return self.current_count < effective_limit

    def increment(self):
        RateLimit.objects.filter(pk=self.pk).update(
            current_count=models.F("current_count") + 1
        )
