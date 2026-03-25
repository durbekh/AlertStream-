from django.contrib import admin

from .models import Preference, Subscriber, SubscriberGroup, Unsubscribe


class PreferenceInline(admin.TabularInline):
    model = Preference
    extra = 0
    fields = ("channel", "category", "is_enabled", "frequency", "quiet_hours_start", "quiet_hours_end")


class UnsubscribeInline(admin.TabularInline):
    model = Unsubscribe
    extra = 0
    readonly_fields = ("channel", "category", "reason", "feedback", "ip_address", "created_at")


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "name",
        "phone",
        "is_active",
        "organization",
        "total_notifications",
        "last_notified_at",
        "created_at",
    )
    list_filter = ("is_active", "organization", "tags")
    search_fields = ("email", "name", "first_name", "last_name", "external_id", "phone")
    readonly_fields = (
        "id",
        "unsubscribe_token",
        "total_notifications",
        "last_notified_at",
        "created_at",
        "updated_at",
    )
    inlines = [PreferenceInline, UnsubscribeInline]
    fieldsets = (
        (None, {"fields": ("id", "organization", "external_id", "is_active")}),
        ("Contact", {"fields": ("email", "phone", "name", "first_name", "last_name")}),
        ("Channels", {"fields": ("device_token", "slack_user_id")}),
        ("Profile", {"fields": ("locale", "timezone", "avatar_url", "custom_data", "tags")}),
        ("Activity", {"fields": ("unsubscribe_token", "total_notifications", "last_notified_at", "created_at", "updated_at")}),
    )


@admin.register(SubscriberGroup)
class SubscriberGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "group_type",
        "organization",
        "subscriber_count_display",
        "is_active",
        "created_at",
    )
    list_filter = ("group_type", "is_active", "organization")
    search_fields = ("name", "description")
    filter_horizontal = ("subscribers",)
    readonly_fields = ("id", "created_at", "updated_at")

    def subscriber_count_display(self, obj):
        return obj.subscriber_count
    subscriber_count_display.short_description = "Subscribers"


@admin.register(Unsubscribe)
class UnsubscribeAdmin(admin.ModelAdmin):
    list_display = (
        "subscriber",
        "channel",
        "category",
        "reason",
        "created_at",
    )
    list_filter = ("reason", "channel")
    search_fields = ("subscriber__email", "feedback")
    readonly_fields = (
        "id",
        "subscriber",
        "channel",
        "category",
        "reason",
        "feedback",
        "ip_address",
        "user_agent",
        "notification_id",
        "created_at",
    )
