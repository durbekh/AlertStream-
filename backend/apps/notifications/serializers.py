from rest_framework import serializers

from .models import DeliveryAttempt, Notification, NotificationLog


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "event_type",
            "channel",
            "message",
            "details",
            "timestamp",
        ]
        read_only_fields = fields


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAttempt
        fields = [
            "id",
            "channel",
            "provider",
            "status",
            "attempt_number",
            "max_attempts",
            "provider_message_id",
            "response_code",
            "error_message",
            "error_code",
            "cost",
            "currency",
            "created_at",
            "sent_at",
            "delivered_at",
            "failed_at",
            "next_retry_at",
            "duration_ms",
        ]
        read_only_fields = fields


class NotificationListSerializer(serializers.ModelSerializer):
    channel_count = serializers.SerializerMethodField()
    delivery_summary = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "subject",
            "channels",
            "status",
            "priority",
            "channel_count",
            "delivery_summary",
            "created_at",
            "delivered_at",
        ]
        read_only_fields = fields

    def get_channel_count(self, obj):
        return len(obj.channels) if obj.channels else 0

    def get_delivery_summary(self, obj):
        attempts = obj.delivery_attempts.all()
        if not attempts.exists():
            return {"total": 0, "delivered": 0, "failed": 0}
        return {
            "total": attempts.count(),
            "delivered": attempts.filter(status="delivered").count(),
            "failed": attempts.filter(status="failed").count(),
        }


class NotificationDetailSerializer(serializers.ModelSerializer):
    logs = NotificationLogSerializer(many=True, read_only=True)
    delivery_attempts = DeliveryAttemptSerializer(many=True, read_only=True)
    template_name = serializers.CharField(
        source="template.name", read_only=True, default=None
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "organization",
            "created_by",
            "recipient",
            "recipient_data",
            "template",
            "template_name",
            "subject",
            "body",
            "body_html",
            "context",
            "metadata",
            "channels",
            "status",
            "priority",
            "scheduled_at",
            "expires_at",
            "idempotency_key",
            "external_id",
            "group_id",
            "created_at",
            "updated_at",
            "delivered_at",
            "logs",
            "delivery_attempts",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_by",
            "status",
            "created_at",
            "updated_at",
            "delivered_at",
        ]


class SendNotificationSerializer(serializers.Serializer):
    """Serializer for sending notifications via the API."""

    recipient = serializers.CharField(max_length=500)
    recipient_data = serializers.DictField(required=False, default=dict)
    template_id = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=500, required=False, default="")
    body = serializers.CharField(required=False, default="")
    body_html = serializers.CharField(required=False, default="")
    context = serializers.DictField(required=False, default=dict)
    metadata = serializers.DictField(required=False, default=dict)
    channels = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["email", "sms", "push", "slack", "telegram", "whatsapp", "webhook"]
        ),
        min_length=1,
    )
    priority = serializers.ChoiceField(
        choices=Notification.Priority.choices,
        default=Notification.Priority.NORMAL,
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(
        max_length=255, required=False, default=""
    )
    external_id = serializers.CharField(
        max_length=255, required=False, default=""
    )
    group_id = serializers.CharField(
        max_length=255, required=False, default=""
    )

    def validate_channels(self, value):
        if not value:
            raise serializers.ValidationError("At least one channel is required.")
        return list(set(value))

    def validate(self, attrs):
        if not attrs.get("template_id") and not attrs.get("body"):
            raise serializers.ValidationError(
                "Either template_id or body must be provided."
            )
        return attrs


class BulkSendNotificationSerializer(serializers.Serializer):
    """Serializer for sending bulk notifications."""

    notifications = SendNotificationSerializer(many=True, min_length=1, max_length=100)


class NotificationCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a notification."""

    reason = serializers.CharField(max_length=500, required=False, default="")
