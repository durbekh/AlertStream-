import secrets
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model with email as the primary identifier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField("email address", unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    organization = models.ForeignKey(
        "Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ("owner", "Owner"),
            ("admin", "Admin"),
            ("member", "Member"),
            ("viewer", "Viewer"),
        ],
        default="member",
    )
    is_email_verified = models.BooleanField(default=False)
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "accounts_user"
        ordering = ["-created_at"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def update_last_activity(self):
        self.last_activity = timezone.now()
        self.save(update_fields=["last_activity"])


class Organization(models.Model):
    """Organization model for multi-tenant support."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    logo = models.ImageField(upload_to="org_logos/", blank=True, null=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    plan = models.CharField(
        max_length=20,
        choices=[
            ("free", "Free"),
            ("starter", "Starter"),
            ("professional", "Professional"),
            ("enterprise", "Enterprise"),
        ],
        default="free",
    )
    max_notifications_per_month = models.IntegerField(default=1000)
    notifications_sent_this_month = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_organization"
        ordering = ["-created_at"]
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return self.name

    def has_quota_remaining(self):
        return self.notifications_sent_this_month < self.max_notifications_per_month

    def increment_notification_count(self):
        Organization.objects.filter(pk=self.pk).update(
            notifications_sent_this_month=models.F("notifications_sent_this_month") + 1
        )

    def reset_monthly_count(self):
        self.notifications_sent_this_month = 0
        self.save(update_fields=["notifications_sent_this_month"])


class APIKey(models.Model):
    """API Key model for programmatic access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_api_keys",
    )
    name = models.CharField(max_length=255, help_text="A descriptive name for this API key")
    prefix = models.CharField(max_length=8, unique=True, db_index=True, editable=False)
    hashed_key = models.CharField(max_length=128, editable=False)
    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of permitted scopes: notifications:send, notifications:read, templates:manage, etc.",
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    request_count = models.BigIntegerField(default=0)
    rate_limit = models.IntegerField(
        default=1000,
        help_text="Maximum requests per hour for this key",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_api_key"
        ordering = ["-created_at"]
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @staticmethod
    def generate_key():
        """Generate a new API key with prefix."""
        key = secrets.token_urlsafe(48)
        prefix = key[:8]
        return key, prefix

    @staticmethod
    def hash_key(key):
        """Hash an API key for storage."""
        import hashlib

        return hashlib.sha256(key.encode()).hexdigest()

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

    def record_usage(self, ip_address=None):
        """Record API key usage."""
        update_fields = ["last_used_at", "request_count"]
        self.last_used_at = timezone.now()
        self.request_count = models.F("request_count") + 1
        if ip_address:
            self.last_used_ip = ip_address
            update_fields.append("last_used_ip")
        self.save(update_fields=update_fields)
