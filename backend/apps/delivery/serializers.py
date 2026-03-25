from rest_framework import serializers

from .models import DeliveryLog, DeliveryStatus, RetryLog


class DeliveryLogSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(
        source="get_level_display", read_only=True
    )

    class Meta:
        model = DeliveryLog
        fields = [
            "id",
            "notification",
            "channel",
            "provider",
            "level",
            "level_display",
            "event",
            "recipient",
            "message",
            "status_code",
            "duration_ms",
            "provider_message_id",
            "error_code",
            "metadata",
            "timestamp",
        ]
        read_only_fields = fields


class DeliveryLogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryLog
        fields = [
            "id",
            "organization",
            "notification",
            "channel",
            "provider",
            "level",
            "event",
            "recipient",
            "message",
            "request_payload",
            "response_payload",
            "status_code",
            "duration_ms",
            "provider_message_id",
            "error_code",
            "ip_address",
            "user_agent",
            "metadata",
            "timestamp",
        ]
        read_only_fields = fields


class DeliveryStatusSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = DeliveryStatus
        fields = [
            "id",
            "notification",
            "channel",
            "status",
            "status_display",
            "provider",
            "provider_message_id",
            "attempts",
            "last_attempt_at",
            "delivered_at",
            "opened_at",
            "clicked_at",
            "bounced_at",
            "error_message",
            "cost",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RetryLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = RetryLog
        fields = [
            "id",
            "notification",
            "channel",
            "attempt_number",
            "max_attempts",
            "status",
            "status_display",
            "error_message",
            "error_code",
            "backoff_seconds",
            "scheduled_at",
            "started_at",
            "completed_at",
            "response_code",
            "duration_ms",
            "created_at",
        ]
        read_only_fields = fields
