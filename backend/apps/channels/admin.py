from django.contrib import admin

from .models import (
    Channel,
    EmailChannel,
    PushChannel,
    SlackChannel,
    SMSChannel,
    WebhookChannel,
)


class EmailChannelInline(admin.StackedInline):
    model = EmailChannel
    extra = 0
    fieldsets = (
        ("Provider", {"fields": ("provider",)}),
        ("Sender", {"fields": ("from_email", "from_name", "reply_to")}),
        ("SMTP", {"fields": ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_use_tls"), "classes": ("collapse",)}),
        ("API", {"fields": ("api_key", "api_endpoint", "domain"), "classes": ("collapse",)}),
        ("Tracking", {"fields": ("track_opens", "track_clicks")}),
    )


class SMSChannelInline(admin.StackedInline):
    model = SMSChannel
    extra = 0


class PushChannelInline(admin.StackedInline):
    model = PushChannel
    extra = 0
    fieldsets = (
        ("Provider", {"fields": ("provider",)}),
        ("FCM", {"fields": ("fcm_server_key", "fcm_project_id", "fcm_service_account_json"), "classes": ("collapse",)}),
        ("APNS", {"fields": ("apns_key_id", "apns_team_id", "apns_bundle_id", "apns_private_key", "apns_use_sandbox"), "classes": ("collapse",)}),
        ("OneSignal", {"fields": ("onesignal_app_id", "onesignal_api_key"), "classes": ("collapse",)}),
    )


class WebhookChannelInline(admin.StackedInline):
    model = WebhookChannel
    extra = 0


class SlackChannelInline(admin.StackedInline):
    model = SlackChannel
    extra = 0


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "channel_type",
        "organization",
        "is_active",
        "is_default",
        "priority",
        "messages_sent_today",
        "daily_limit",
        "last_tested_at",
        "last_test_status",
        "created_at",
    )
    list_filter = ("channel_type", "is_active", "is_default", "organization")
    search_fields = ("name", "organization__name")
    readonly_fields = ("id", "messages_sent_today", "last_tested_at", "last_test_status", "created_at", "updated_at")
    inlines = [
        EmailChannelInline,
        SMSChannelInline,
        PushChannelInline,
        WebhookChannelInline,
        SlackChannelInline,
    ]

    def get_inlines(self, request, obj=None):
        if obj is None:
            return self.inlines
        inline_map = {
            "email": [EmailChannelInline],
            "sms": [SMSChannelInline],
            "push": [PushChannelInline],
            "webhook": [WebhookChannelInline],
            "slack": [SlackChannelInline],
        }
        return inline_map.get(obj.channel_type, [])
