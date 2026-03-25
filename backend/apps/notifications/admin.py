from django.contrib import admin

from .models import DeliveryAttempt, Notification, NotificationLog


class NotificationLogInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    readonly_fields = ("event_type", "channel", "message", "details", "timestamp")
    ordering = ("-timestamp",)


class DeliveryAttemptInline(admin.TabularInline):
    model = DeliveryAttempt
    extra = 0
    readonly_fields = (
        "channel",
        "provider",
        "status",
        "attempt_number",
        "provider_message_id",
        "error_message",
        "created_at",
        "delivered_at",
        "duration_ms",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "subject",
        "status",
        "priority",
        "channels_display",
        "organization",
        "created_at",
    )
    list_filter = ("status", "priority", "channels", "organization")
    search_fields = ("recipient", "subject", "external_id", "idempotency_key")
    readonly_fields = ("id", "created_at", "updated_at", "delivered_at")
    inlines = [NotificationLogInline, DeliveryAttemptInline]
    date_hierarchy = "created_at"

    def channels_display(self, obj):
        return ", ".join(obj.channels) if obj.channels else "-"

    channels_display.short_description = "Channels"


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("notification", "event_type", "channel", "message", "timestamp")
    list_filter = ("event_type", "channel")
    search_fields = ("notification__id", "message")
    readonly_fields = ("notification", "event_type", "channel", "message", "details", "timestamp")
    date_hierarchy = "timestamp"


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "notification",
        "channel",
        "provider",
        "status",
        "attempt_number",
        "duration_ms",
        "created_at",
    )
    list_filter = ("status", "channel", "provider")
    search_fields = ("notification__id", "provider_message_id")
    readonly_fields = (
        "notification",
        "channel",
        "provider",
        "status",
        "attempt_number",
        "provider_message_id",
        "response_code",
        "response_body",
        "error_message",
        "created_at",
        "sent_at",
        "delivered_at",
        "failed_at",
        "duration_ms",
    )
