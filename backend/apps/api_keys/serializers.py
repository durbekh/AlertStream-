from rest_framework import serializers

from .models import APIKey, RateLimit


class APIKeyExtendedSerializer(serializers.ModelSerializer):
    key_name = serializers.CharField(source="account_api_key.name", read_only=True)
    key_prefix = serializers.CharField(source="account_api_key.prefix", read_only=True)
    is_key_active = serializers.BooleanField(source="account_api_key.is_active", read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id",
            "account_api_key",
            "key_name",
            "key_prefix",
            "is_key_active",
            "tier",
            "allowed_channels",
            "allowed_ips",
            "allowed_origins",
            "webhook_url",
            "webhook_secret",
            "daily_request_count",
            "daily_request_limit",
            "monthly_notification_count",
            "monthly_notification_limit",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "daily_request_count",
            "monthly_notification_count",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "webhook_secret": {"write_only": True},
        }


class APIKeyConfigUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = [
            "tier",
            "allowed_channels",
            "allowed_ips",
            "allowed_origins",
            "webhook_url",
            "webhook_secret",
            "daily_request_limit",
            "monthly_notification_limit",
            "metadata",
        ]


class RateLimitSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(
        source="get_scope_display", read_only=True
    )
    window_type_display = serializers.CharField(
        source="get_window_type_display", read_only=True
    )
    usage_percent = serializers.SerializerMethodField()

    class Meta:
        model = RateLimit
        fields = [
            "id",
            "organization",
            "api_key",
            "scope",
            "scope_display",
            "resource",
            "window_type",
            "window_type_display",
            "max_requests",
            "current_count",
            "burst_limit",
            "is_active",
            "usage_percent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_count", "created_at", "updated_at"]

    def get_usage_percent(self, obj):
        if obj.max_requests == 0:
            return 0.0
        return round((obj.current_count / obj.max_requests) * 100, 2)


class RateLimitCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateLimit
        fields = [
            "scope",
            "resource",
            "window_type",
            "max_requests",
            "burst_limit",
            "is_active",
        ]

    def create(self, validated_data):
        org = self.context["request"].user.organization
        return RateLimit.objects.create(organization=org, **validated_data)
