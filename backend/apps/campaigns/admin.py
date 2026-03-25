from django.contrib import admin

from .models import Campaign, CampaignResult, CampaignSchedule, CampaignSegment


class CampaignSegmentInline(admin.TabularInline):
    model = CampaignSegment
    extra = 1
    raw_id_fields = ("subscriber_group",)


class CampaignScheduleInline(admin.StackedInline):
    model = CampaignSchedule
    extra = 0
    readonly_fields = ("recurrence_count", "last_run_at", "next_run_at")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "campaign_type",
        "status",
        "organization",
        "total_sent",
        "total_delivered",
        "total_failed",
        "delivery_rate_display",
        "open_rate_display",
        "started_at",
        "created_at",
    )
    list_filter = ("status", "campaign_type", "organization", "channels")
    search_fields = ("name", "description")
    readonly_fields = (
        "id",
        "total_sent",
        "total_delivered",
        "total_failed",
        "total_opened",
        "total_clicked",
        "estimated_recipients",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    inlines = [CampaignSegmentInline, CampaignScheduleInline]
    date_hierarchy = "created_at"
    fieldsets = (
        (None, {"fields": ("id", "organization", "name", "description", "campaign_type", "status")}),
        ("Content", {"fields": ("template", "subject_override", "body_override", "channels", "context_data")}),
        ("Targeting", {"fields": ("send_to_all", "estimated_recipients")}),
        ("Results", {"fields": ("total_sent", "total_delivered", "total_failed", "total_opened", "total_clicked")}),
        ("Metadata", {"fields": ("tags", "created_by", "started_at", "completed_at", "created_at", "updated_at")}),
    )

    def delivery_rate_display(self, obj):
        return f"{obj.delivery_rate}%"
    delivery_rate_display.short_description = "Delivery Rate"

    def open_rate_display(self, obj):
        return f"{obj.open_rate}%"
    open_rate_display.short_description = "Open Rate"


@admin.register(CampaignResult)
class CampaignResultAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "subscriber",
        "status",
        "channel",
        "sent_at",
        "delivered_at",
        "opened_at",
    )
    list_filter = ("status", "channel", "campaign__organization")
    search_fields = ("campaign__name", "subscriber__email")
    readonly_fields = (
        "id",
        "campaign",
        "subscriber",
        "notification",
        "sent_at",
        "delivered_at",
        "opened_at",
        "clicked_at",
        "created_at",
    )
    raw_id_fields = ("campaign", "subscriber", "notification")
