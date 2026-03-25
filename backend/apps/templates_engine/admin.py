from django.contrib import admin

from .models import NotificationTemplate, TemplateVariable, TemplateVersion


class TemplateVariableInline(admin.TabularInline):
    model = TemplateVariable
    extra = 1
    fields = ("name", "variable_type", "description", "default_value", "is_required", "sample_value")


class TemplateVersionInline(admin.TabularInline):
    model = TemplateVersion
    extra = 0
    readonly_fields = ("version_number", "subject", "change_notes", "created_by", "is_published", "created_at")
    ordering = ("-version_number",)
    fields = ("version_number", "is_published", "change_notes", "created_by", "created_at")


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "template_type",
        "category",
        "is_active",
        "is_default",
        "current_version",
        "organization",
        "created_at",
        "updated_at",
    )
    list_filter = ("template_type", "category", "is_active", "is_default", "organization")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("id", "current_version", "created_at", "updated_at")
    inlines = [TemplateVariableInline, TemplateVersionInline]
    fieldsets = (
        (None, {"fields": ("id", "organization", "name", "slug", "description")}),
        ("Type & Category", {"fields": ("template_type", "category", "tags")}),
        ("Content", {"fields": ("subject", "body_text", "body_html")}),
        ("Settings", {"fields": ("is_active", "is_default", "current_version")}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(TemplateVersion)
class TemplateVersionAdmin(admin.ModelAdmin):
    list_display = ("template", "version_number", "is_published", "created_by", "created_at")
    list_filter = ("is_published", "template__organization")
    search_fields = ("template__name", "change_notes")
    readonly_fields = ("id", "created_at")
