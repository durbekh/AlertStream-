import secrets
import uuid

from django.db import models
from django.utils import timezone


class Subscriber(models.Model):
    """An individual subscriber who can receive notifications."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="subscribers",
        db_index=True,
    )
    external_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="External identifier from the client's system",
    )
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    device_token = models.CharField(
        max_length=500,
        blank=True,
        help_text="FCM or APNS device token for push notifications",
    )
    slack_user_id = models.CharField(max_length=50, blank=True)
    locale = models.CharField(max_length=10, default="en", blank=True)
    timezone = models.CharField(max_length=50, default="UTC", blank=True)
    avatar_url = models.URLField(blank=True)
    custom_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary key-value data for template personalization",
    )
    tags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    unsubscribe_token = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        db_index=True,
    )
    last_notified_at = models.DateTimeField(null=True, blank=True)
    total_notifications = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscribers_subscriber"
        ordering = ["-created_at"]
        unique_together = [("organization", "email")]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["organization", "external_id"]),
        ]

    def __str__(self):
        return self.name or self.email or str(self.id)

    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            self.unsubscribe_token = secrets.token_urlsafe(48)
        if not self.name and (self.first_name or self.last_name):
            self.name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    def record_notification(self):
        Subscriber.objects.filter(pk=self.pk).update(
            last_notified_at=timezone.now(),
            total_notifications=models.F("total_notifications") + 1,
        )


class SubscriberGroup(models.Model):
    """A named group/segment of subscribers for targeting."""

    class GroupType(models.TextChoices):
        STATIC = "static", "Static (Manual)"
        DYNAMIC = "dynamic", "Dynamic (Rule-Based)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="subscriber_groups",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    group_type = models.CharField(
        max_length=20,
        choices=GroupType.choices,
        default=GroupType.STATIC,
    )
    subscribers = models.ManyToManyField(
        Subscriber,
        related_name="groups",
        blank=True,
    )
    rules = models.JSONField(
        default=list,
        blank=True,
        help_text='Dynamic segment rules: [{"field": "tags", "operator": "contains", "value": "vip"}]',
    )
    color = models.CharField(max_length=7, default="#3B82F6", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscribers_group"
        ordering = ["name"]
        unique_together = [("organization", "name")]

    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"

    @property
    def subscriber_count(self):
        if self.group_type == self.GroupType.DYNAMIC:
            return self.resolve_dynamic_members().count()
        return self.subscribers.filter(is_active=True).count()

    def resolve_dynamic_members(self):
        """Resolve subscribers matching dynamic rules."""
        if self.group_type != self.GroupType.DYNAMIC or not self.rules:
            return self.subscribers.filter(is_active=True)

        queryset = Subscriber.objects.filter(
            organization=self.organization, is_active=True
        )

        for rule in self.rules:
            field = rule.get("field", "")
            operator = rule.get("operator", "")
            value = rule.get("value", "")

            if field and operator and value:
                if operator == "equals":
                    queryset = queryset.filter(**{field: value})
                elif operator == "contains":
                    queryset = queryset.filter(**{f"{field}__contains": value})
                elif operator == "starts_with":
                    queryset = queryset.filter(**{f"{field}__startswith": value})
                elif operator == "in":
                    queryset = queryset.filter(**{f"{field}__in": value.split(",")})
                elif operator == "gt":
                    queryset = queryset.filter(**{f"{field}__gt": value})
                elif operator == "lt":
                    queryset = queryset.filter(**{f"{field}__lt": value})

        return queryset


class Preference(models.Model):
    """Subscriber notification preferences per channel and category."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    channel = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email"),
            ("sms", "SMS"),
            ("push", "Push"),
            ("slack", "Slack"),
            ("webhook", "Webhook"),
        ],
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Notification category (e.g., marketing, transactional, alerts)",
    )
    is_enabled = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=20,
        choices=[
            ("realtime", "Real-time"),
            ("hourly", "Hourly Digest"),
            ("daily", "Daily Digest"),
            ("weekly", "Weekly Digest"),
        ],
        default="realtime",
    )
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Start of quiet hours (no notifications)",
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="End of quiet hours",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscribers_preference"
        unique_together = [("subscriber", "channel", "category")]

    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"{self.subscriber} - {self.channel}/{self.category}: {status}"


class Unsubscribe(models.Model):
    """Records when and why a subscriber unsubscribed."""

    class Reason(models.TextChoices):
        USER_REQUEST = "user_request", "User Requested"
        SPAM_COMPLAINT = "spam_complaint", "Spam Complaint"
        BOUNCE = "bounce", "Hard Bounce"
        ADMIN = "admin", "Admin Action"
        LIST_UNSUBSCRIBE = "list_unsubscribe", "List-Unsubscribe Header"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.CASCADE,
        related_name="unsubscribes",
    )
    channel = models.CharField(
        max_length=20,
        blank=True,
        help_text="Specific channel unsubscribed from, or blank for all",
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Specific category unsubscribed from, or blank for all",
    )
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        default=Reason.USER_REQUEST,
    )
    feedback = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    notification_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="The notification that triggered the unsubscribe",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscribers_unsubscribe"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subscriber} unsubscribed ({self.get_reason_display()}) at {self.created_at}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Deactivate preferences or subscriber
        if not self.channel and not self.category:
            self.subscriber.is_active = False
            self.subscriber.save(update_fields=["is_active"])
        elif self.channel:
            Preference.objects.filter(
                subscriber=self.subscriber,
                channel=self.channel,
            ).update(is_enabled=False)
