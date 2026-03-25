from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import APIKey, Organization, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "organization",
        "role",
        "is_active",
        "is_staff",
        "created_at",
    )
    list_filter = ("is_active", "is_staff", "role", "organization")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "phone_number", "avatar")}),
        (
            "Organization",
            {"fields": ("organization", "role")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Activity", {"fields": ("is_email_verified", "last_activity", "last_login")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "first_name", "last_name"),
            },
        ),
    )
    readonly_fields = ("last_activity", "last_login", "created_at")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "plan",
        "notifications_sent_this_month",
        "max_notifications_per_month",
        "is_active",
        "created_at",
    )
    list_filter = ("plan", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "prefix",
        "organization",
        "is_active",
        "last_used_at",
        "request_count",
        "created_at",
    )
    list_filter = ("is_active", "organization")
    search_fields = ("name", "prefix")
    readonly_fields = (
        "prefix",
        "hashed_key",
        "last_used_at",
        "last_used_ip",
        "request_count",
        "created_at",
    )
