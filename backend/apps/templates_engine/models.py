import uuid

from django.conf import settings
from django.db import models


class NotificationTemplate(models.Model):
    """Reusable notification template with variable substitution."""

    class TemplateType(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push Notification"
        UNIVERSAL = "universal", "Universal (Multi-Channel)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="notification_templates",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.UNIVERSAL,
    )
    subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Subject template with {{variable}} placeholders",
    )
    body_text = models.TextField(
        blank=True,
        help_text="Plain text body template with {{variable}} placeholders",
    )
    body_html = models.TextField(
        blank=True,
        help_text="HTML body template with {{variable}} placeholders",
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("transactional", "Transactional"),
            ("marketing", "Marketing"),
            ("alert", "Alert"),
            ("digest", "Digest"),
            ("system", "System"),
        ],
        default="transactional",
    )
    tags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default template used when no template is specified",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_templates",
    )
    current_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "templates_notification_template"
        ordering = ["-updated_at"]
        unique_together = [("organization", "slug")]
        indexes = [
            models.Index(fields=["organization", "template_type", "is_active"]),
            models.Index(fields=["organization", "category"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def get_variables(self):
        """Extract all variable names from subject and body templates."""
        import re
        pattern = r"\{\{(\w+)\}\}"
        variables = set()
        for field in [self.subject, self.body_text, self.body_html]:
            if field:
                variables.update(re.findall(pattern, field))
        return sorted(variables)


class TemplateVariable(models.Model):
    """Defines expected variables for a template with metadata."""

    class VariableType(models.TextChoices):
        STRING = "string", "String"
        NUMBER = "number", "Number"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Date"
        URL = "url", "URL"
        LIST = "list", "List"
        OBJECT = "object", "Object"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name="variables",
    )
    name = models.CharField(max_length=100)
    variable_type = models.CharField(
        max_length=20,
        choices=VariableType.choices,
        default=VariableType.STRING,
    )
    description = models.CharField(max_length=500, blank=True)
    default_value = models.CharField(max_length=500, blank=True)
    is_required = models.BooleanField(default=True)
    sample_value = models.CharField(
        max_length=500,
        blank=True,
        help_text="Sample value for template preview",
    )

    class Meta:
        db_table = "templates_variable"
        ordering = ["name"]
        unique_together = [("template", "name")]

    def __str__(self):
        return f"{self.template.name}.{self.name} ({self.get_variable_type_display()})"


class TemplateVersion(models.Model):
    """Versioned snapshot of a template for rollback and audit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    subject = models.CharField(max_length=500, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    change_notes = models.TextField(
        blank=True,
        help_text="Description of changes in this version",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "templates_version"
        ordering = ["-version_number"]
        unique_together = [("template", "version_number")]

    def __str__(self):
        return f"{self.template.name} v{self.version_number}"

    def publish(self):
        """Publish this version, making it the active template content."""
        self.template.subject = self.subject
        self.template.body_text = self.body_text
        self.template.body_html = self.body_html
        self.template.current_version = self.version_number
        self.template.save(
            update_fields=["subject", "body_text", "body_html", "current_version", "updated_at"]
        )
        TemplateVersion.objects.filter(
            template=self.template, is_published=True
        ).exclude(pk=self.pk).update(is_published=False)
        self.is_published = True
        self.save(update_fields=["is_published"])
