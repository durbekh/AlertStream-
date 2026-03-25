from rest_framework import serializers

from .models import Preference, Subscriber, SubscriberGroup, Unsubscribe


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preference
        fields = [
            "id",
            "channel",
            "category",
            "is_enabled",
            "frequency",
            "quiet_hours_start",
            "quiet_hours_end",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class SubscriberListSerializer(serializers.ModelSerializer):
    group_names = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = [
            "id",
            "external_id",
            "email",
            "phone",
            "name",
            "is_active",
            "tags",
            "group_names",
            "total_notifications",
            "last_notified_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "unsubscribe_token",
            "total_notifications",
            "last_notified_at",
            "created_at",
        ]

    def get_group_names(self, obj):
        return list(obj.groups.values_list("name", flat=True))


class SubscriberDetailSerializer(serializers.ModelSerializer):
    preferences = PreferenceSerializer(many=True, read_only=True)
    groups = serializers.SerializerMethodField()

    class Meta:
        model = Subscriber
        fields = [
            "id",
            "external_id",
            "email",
            "phone",
            "name",
            "first_name",
            "last_name",
            "device_token",
            "slack_user_id",
            "locale",
            "timezone",
            "avatar_url",
            "custom_data",
            "tags",
            "is_active",
            "unsubscribe_token",
            "preferences",
            "groups",
            "total_notifications",
            "last_notified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "unsubscribe_token",
            "total_notifications",
            "last_notified_at",
            "created_at",
            "updated_at",
        ]

    def get_groups(self, obj):
        return [
            {"id": str(g.id), "name": g.name, "color": g.color}
            for g in obj.groups.all()
        ]


class SubscriberCreateSerializer(serializers.ModelSerializer):
    preferences = PreferenceSerializer(many=True, required=False)
    group_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Subscriber
        fields = [
            "external_id",
            "email",
            "phone",
            "name",
            "first_name",
            "last_name",
            "device_token",
            "slack_user_id",
            "locale",
            "timezone",
            "avatar_url",
            "custom_data",
            "tags",
            "preferences",
            "group_ids",
        ]

    def validate_email(self, value):
        if value:
            org = self.context["request"].user.organization
            existing = Subscriber.objects.filter(organization=org, email=value)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    "A subscriber with this email already exists."
                )
        return value

    def create(self, validated_data):
        preferences_data = validated_data.pop("preferences", [])
        group_ids = validated_data.pop("group_ids", [])

        subscriber = Subscriber.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )

        for pref_data in preferences_data:
            Preference.objects.create(subscriber=subscriber, **pref_data)

        if group_ids:
            groups = SubscriberGroup.objects.filter(
                id__in=group_ids,
                organization=subscriber.organization,
            )
            subscriber.groups.set(groups)

        return subscriber

    def update(self, instance, validated_data):
        preferences_data = validated_data.pop("preferences", None)
        group_ids = validated_data.pop("group_ids", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if preferences_data is not None:
            instance.preferences.all().delete()
            for pref_data in preferences_data:
                Preference.objects.create(subscriber=instance, **pref_data)

        if group_ids is not None:
            groups = SubscriberGroup.objects.filter(
                id__in=group_ids,
                organization=instance.organization,
            )
            instance.groups.set(groups)

        return instance


class SubscriberGroupListSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.ReadOnlyField()
    group_type_display = serializers.CharField(
        source="get_group_type_display", read_only=True
    )

    class Meta:
        model = SubscriberGroup
        fields = [
            "id",
            "name",
            "description",
            "group_type",
            "group_type_display",
            "color",
            "is_active",
            "subscriber_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SubscriberGroupDetailSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.ReadOnlyField()
    subscribers = SubscriberListSerializer(many=True, read_only=True)

    class Meta:
        model = SubscriberGroup
        fields = [
            "id",
            "name",
            "description",
            "group_type",
            "rules",
            "color",
            "is_active",
            "subscriber_count",
            "subscribers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriberGroupCreateSerializer(serializers.ModelSerializer):
    subscriber_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = SubscriberGroup
        fields = [
            "name",
            "description",
            "group_type",
            "rules",
            "color",
            "is_active",
            "subscriber_ids",
        ]

    def create(self, validated_data):
        subscriber_ids = validated_data.pop("subscriber_ids", [])
        group = SubscriberGroup.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )
        if subscriber_ids:
            subscribers = Subscriber.objects.filter(
                id__in=subscriber_ids,
                organization=group.organization,
            )
            group.subscribers.set(subscribers)
        return group


class UnsubscribeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unsubscribe
        fields = [
            "id",
            "subscriber",
            "channel",
            "category",
            "reason",
            "feedback",
            "notification_id",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class UnsubscribePublicSerializer(serializers.Serializer):
    """Public serializer for unsubscribe endpoint (no auth required)."""

    token = serializers.CharField(max_length=64)
    channel = serializers.CharField(max_length=20, required=False, default="")
    category = serializers.CharField(max_length=50, required=False, default="")
    reason = serializers.ChoiceField(
        choices=Unsubscribe.Reason.choices,
        default=Unsubscribe.Reason.USER_REQUEST,
    )
    feedback = serializers.CharField(max_length=1000, required=False, default="")
