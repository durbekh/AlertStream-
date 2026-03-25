import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Channel(models.Model):
    """Base channel configuration for an organization."""

    class ChannelType(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push Notification"
        WEBHOOK = "webhook", "Webhook"
        SLACK = "slack", "Slack"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="channels",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    channel_type = models.CharField(
        max_length=20,
        choices=ChannelType.choices,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this channel is used by default for new notifications",
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text="Higher priority channels are tried first in failover scenarios",
    )
    rate_limit_per_minute = models.PositiveIntegerField(
        default=60,
        help_text="Maximum messages per minute through this channel",
    )
    daily_limit = models.PositiveIntegerField(
        default=10000,
        help_text="Maximum messages per day through this channel",
    )
    messages_sent_today = models.PositiveIntegerField(default=0)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_channels",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "channels_channel"
        ordering = ["-is_default", "priority", "name"]
        unique_together = [("organization", "name")]
        indexes = [
            models.Index(fields=["organization", "channel_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()}) - {self.organization.name}"

    @property
    def has_daily_capacity(self):
        return self.messages_sent_today < self.daily_limit

    def reset_daily_count(self):
        self.messages_sent_today = 0
        self.save(update_fields=["messages_sent_today"])

    def increment_message_count(self):
        Channel.objects.filter(pk=self.pk).update(
            messages_sent_today=models.F("messages_sent_today") + 1
        )

    def record_test(self, success):
        self.last_tested_at = timezone.now()
        self.last_test_status = "success" if success else "failed"
        self.save(update_fields=["last_tested_at", "last_test_status"])


class EmailChannel(models.Model):
    """Email-specific channel configuration."""

    class Provider(models.TextChoices):
        SMTP = "smtp", "SMTP"
        SENDGRID = "sendgrid", "SendGrid"
        SES = "ses", "Amazon SES"
        MAILGUN = "mailgun", "Mailgun"
        POSTMARK = "postmark", "Postmark"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.OneToOneField(
        Channel,
        on_delete=models.CASCADE,
        related_name="email_config",
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.SMTP,
    )
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True)
    reply_to = models.EmailField(blank=True)

    # SMTP settings
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=500, blank=True)
    smtp_use_tls = models.BooleanField(default=True)

    # API provider settings
    api_key = models.CharField(max_length=500, blank=True)
    api_endpoint = models.URLField(blank=True)
    domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Sender domain for services like Mailgun",
    )

    # Tracking
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)

    class Meta:
        db_table = "channels_email_channel"
        verbose_name = "Email Channel Config"
        verbose_name_plural = "Email Channel Configs"

    def __str__(self):
        return f"Email: {self.from_email} via {self.get_provider_display()}"


class SMSChannel(models.Model):
    """SMS-specific channel configuration."""

    class Provider(models.TextChoices):
        TWILIO = "twilio", "Twilio"
        NEXMO = "nexmo", "Nexmo / Vonage"
        PLIVO = "plivo", "Plivo"
        MESSAGEBIRD = "messagebird", "MessageBird"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.OneToOneField(
        Channel,
        on_delete=models.CASCADE,
        related_name="sms_config",
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.TWILIO,
    )
    from_number = models.CharField(max_length=20)
    account_sid = models.CharField(max_length=255)
    auth_token = models.CharField(max_length=500)
    messaging_service_sid = models.CharField(
        max_length=255,
        blank=True,
        help_text="Twilio Messaging Service SID for intelligent routing",
    )
    max_segments = models.PositiveIntegerField(
        default=3,
        help_text="Maximum SMS segments per message",
    )

    class Meta:
        db_table = "channels_sms_channel"
        verbose_name = "SMS Channel Config"
        verbose_name_plural = "SMS Channel Configs"

    def __str__(self):
        return f"SMS: {self.from_number} via {self.get_provider_display()}"


class PushChannel(models.Model):
    """Push notification channel configuration."""

    class Provider(models.TextChoices):
        FCM = "fcm", "Firebase Cloud Messaging"
        APNS = "apns", "Apple Push Notification Service"
        ONESIGNAL = "onesignal", "OneSignal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.OneToOneField(
        Channel,
        on_delete=models.CASCADE,
        related_name="push_config",
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.FCM,
    )
    # FCM
    fcm_server_key = models.CharField(max_length=500, blank=True)
    fcm_project_id = models.CharField(max_length=255, blank=True)
    fcm_service_account_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Firebase service account credentials JSON",
    )
    # APNS
    apns_key_id = models.CharField(max_length=20, blank=True)
    apns_team_id = models.CharField(max_length=20, blank=True)
    apns_bundle_id = models.CharField(max_length=255, blank=True)
    apns_private_key = models.TextField(blank=True)
    apns_use_sandbox = models.BooleanField(default=False)
    # OneSignal
    onesignal_app_id = models.CharField(max_length=255, blank=True)
    onesignal_api_key = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "channels_push_channel"
        verbose_name = "Push Channel Config"
        verbose_name_plural = "Push Channel Configs"

    def __str__(self):
        return f"Push: {self.get_provider_display()}"


class WebhookChannel(models.Model):
    """Webhook channel configuration."""

    class AuthType(models.TextChoices):
        NONE = "none", "None"
        BASIC = "basic", "Basic Auth"
        BEARER = "bearer", "Bearer Token"
        HMAC = "hmac", "HMAC Signature"
        CUSTOM_HEADER = "custom_header", "Custom Header"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.OneToOneField(
        Channel,
        on_delete=models.CASCADE,
        related_name="webhook_config",
    )
    url = models.URLField(max_length=2000)
    method = models.CharField(
        max_length=10,
        choices=[("POST", "POST"), ("PUT", "PUT"), ("PATCH", "PATCH")],
        default="POST",
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom headers to include with each request",
    )
    auth_type = models.CharField(
        max_length=20,
        choices=AuthType.choices,
        default=AuthType.NONE,
    )
    auth_credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text="Auth credentials: {username, password} for basic, {token} for bearer, {secret} for hmac",
    )
    payload_template = models.TextField(
        blank=True,
        help_text="Jinja2 template for the request body. Variables: {{subject}}, {{body}}, {{recipient}}, {{metadata}}",
    )
    timeout_seconds = models.PositiveIntegerField(default=30)
    verify_ssl = models.BooleanField(default=True)
    signing_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret key for HMAC signing of webhook payloads",
    )

    class Meta:
        db_table = "channels_webhook_channel"
        verbose_name = "Webhook Channel Config"
        verbose_name_plural = "Webhook Channel Configs"

    def __str__(self):
        return f"Webhook: {self.url}"


class SlackChannel(models.Model):
    """Slack channel configuration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.OneToOneField(
        Channel,
        on_delete=models.CASCADE,
        related_name="slack_config",
    )
    bot_token = models.CharField(max_length=500)
    signing_secret = models.CharField(max_length=255, blank=True)
    default_channel_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Default Slack channel ID for notifications",
    )
    default_channel_name = models.CharField(max_length=255, blank=True)
    workspace_name = models.CharField(max_length=255, blank=True)
    workspace_id = models.CharField(max_length=50, blank=True)
    icon_emoji = models.CharField(
        max_length=50,
        blank=True,
        default=":bell:",
    )
    bot_username = models.CharField(
        max_length=255,
        blank=True,
        default="AlertStream",
    )
    use_blocks = models.BooleanField(
        default=True,
        help_text="Use Slack Block Kit for rich message formatting",
    )

    class Meta:
        db_table = "channels_slack_channel"
        verbose_name = "Slack Channel Config"
        verbose_name_plural = "Slack Channel Configs"

    def __str__(self):
        return f"Slack: {self.workspace_name or self.bot_username}"
