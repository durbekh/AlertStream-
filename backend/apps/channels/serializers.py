from rest_framework import serializers

from .models import (
    Channel,
    EmailChannel,
    PushChannel,
    SlackChannel,
    SMSChannel,
    WebhookChannel,
)


class EmailChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailChannel
        fields = [
            "provider",
            "from_email",
            "from_name",
            "reply_to",
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_password",
            "smtp_use_tls",
            "api_key",
            "api_endpoint",
            "domain",
            "track_opens",
            "track_clicks",
        ]
        extra_kwargs = {
            "smtp_password": {"write_only": True},
            "api_key": {"write_only": True},
        }


class SMSChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMSChannel
        fields = [
            "provider",
            "from_number",
            "account_sid",
            "auth_token",
            "messaging_service_sid",
            "max_segments",
        ]
        extra_kwargs = {
            "auth_token": {"write_only": True},
        }


class PushChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushChannel
        fields = [
            "provider",
            "fcm_server_key",
            "fcm_project_id",
            "fcm_service_account_json",
            "apns_key_id",
            "apns_team_id",
            "apns_bundle_id",
            "apns_private_key",
            "apns_use_sandbox",
            "onesignal_app_id",
            "onesignal_api_key",
        ]
        extra_kwargs = {
            "fcm_server_key": {"write_only": True},
            "apns_private_key": {"write_only": True},
            "onesignal_api_key": {"write_only": True},
        }


class WebhookChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookChannel
        fields = [
            "url",
            "method",
            "headers",
            "auth_type",
            "auth_credentials",
            "payload_template",
            "timeout_seconds",
            "verify_ssl",
            "signing_secret",
        ]
        extra_kwargs = {
            "auth_credentials": {"write_only": True},
            "signing_secret": {"write_only": True},
        }


class SlackChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlackChannel
        fields = [
            "bot_token",
            "signing_secret",
            "default_channel_id",
            "default_channel_name",
            "workspace_name",
            "workspace_id",
            "icon_emoji",
            "bot_username",
            "use_blocks",
        ]
        extra_kwargs = {
            "bot_token": {"write_only": True},
            "signing_secret": {"write_only": True},
        }


class ChannelListSerializer(serializers.ModelSerializer):
    channel_type_display = serializers.CharField(
        source="get_channel_type_display", read_only=True
    )
    has_capacity = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "channel_type",
            "channel_type_display",
            "is_active",
            "is_default",
            "priority",
            "rate_limit_per_minute",
            "daily_limit",
            "messages_sent_today",
            "has_capacity",
            "last_tested_at",
            "last_test_status",
            "created_at",
        ]
        read_only_fields = ["id", "messages_sent_today", "last_tested_at", "last_test_status", "created_at"]

    def get_has_capacity(self, obj):
        return obj.has_daily_capacity


class ChannelDetailSerializer(serializers.ModelSerializer):
    channel_type_display = serializers.CharField(
        source="get_channel_type_display", read_only=True
    )
    config = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "channel_type",
            "channel_type_display",
            "is_active",
            "is_default",
            "priority",
            "rate_limit_per_minute",
            "daily_limit",
            "messages_sent_today",
            "last_tested_at",
            "last_test_status",
            "metadata",
            "config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "messages_sent_today",
            "last_tested_at",
            "last_test_status",
            "created_at",
            "updated_at",
        ]

    def get_config(self, obj):
        config_map = {
            "email": ("email_config", EmailChannelSerializer),
            "sms": ("sms_config", SMSChannelSerializer),
            "push": ("push_config", PushChannelSerializer),
            "webhook": ("webhook_config", WebhookChannelSerializer),
            "slack": ("slack_config", SlackChannelSerializer),
        }
        related_name, serializer_cls = config_map.get(obj.channel_type, (None, None))
        if related_name and serializer_cls:
            config_obj = getattr(obj, related_name, None)
            if config_obj:
                return serializer_cls(config_obj).data
        return None


class ChannelCreateSerializer(serializers.ModelSerializer):
    email_config = EmailChannelSerializer(required=False)
    sms_config = SMSChannelSerializer(required=False)
    push_config = PushChannelSerializer(required=False)
    webhook_config = WebhookChannelSerializer(required=False)
    slack_config = SlackChannelSerializer(required=False)

    class Meta:
        model = Channel
        fields = [
            "name",
            "channel_type",
            "is_active",
            "is_default",
            "priority",
            "rate_limit_per_minute",
            "daily_limit",
            "metadata",
            "email_config",
            "sms_config",
            "push_config",
            "webhook_config",
            "slack_config",
        ]

    def validate(self, attrs):
        channel_type = attrs.get("channel_type")
        config_key = f"{channel_type}_config"
        if channel_type in ("email", "sms", "push", "webhook", "slack"):
            if config_key not in self.initial_data:
                raise serializers.ValidationError(
                    {config_key: f"Configuration is required for {channel_type} channels."}
                )
        return attrs

    def create(self, validated_data):
        config_fields = {
            "email": ("email_config", EmailChannel),
            "sms": ("sms_config", SMSChannel),
            "push": ("push_config", PushChannel),
            "webhook": ("webhook_config", WebhookChannel),
            "slack": ("slack_config", SlackChannel),
        }
        channel_type = validated_data["channel_type"]
        config_key, model_cls = config_fields.get(channel_type, (None, None))
        config_data = validated_data.pop(config_key, None) if config_key else None

        # Remove any other config keys that are not relevant
        for key in list(config_fields.keys()):
            k = f"{key}_config"
            validated_data.pop(k, None)

        channel = Channel.objects.create(
            organization=self.context["request"].user.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )

        if config_data and model_cls:
            model_cls.objects.create(channel=channel, **config_data)

        return channel

    def update(self, instance, validated_data):
        config_fields = {
            "email": ("email_config", EmailChannel),
            "sms": ("sms_config", SMSChannel),
            "push": ("push_config", PushChannel),
            "webhook": ("webhook_config", WebhookChannel),
            "slack": ("slack_config", SlackChannel),
        }
        channel_type = instance.channel_type
        config_key, model_cls = config_fields.get(channel_type, (None, None))
        config_data = validated_data.pop(config_key, None) if config_key else None

        for key in list(config_fields.keys()):
            k = f"{key}_config"
            validated_data.pop(k, None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if config_data and model_cls:
            config_obj = getattr(instance, config_key, None)
            if config_obj:
                for attr, value in config_data.items():
                    setattr(config_obj, attr, value)
                config_obj.save()
            else:
                model_cls.objects.create(channel=instance, **config_data)

        return instance


class ChannelTestSerializer(serializers.Serializer):
    """Serializer for testing a channel configuration."""

    test_recipient = serializers.CharField(
        max_length=500,
        help_text="Recipient to send the test notification to (email, phone, etc.)",
    )
    test_message = serializers.CharField(
        max_length=1000,
        default="This is a test notification from AlertStream.",
    )
