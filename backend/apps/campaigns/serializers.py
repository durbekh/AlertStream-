from rest_framework import serializers

from .models import Campaign, CampaignResult, CampaignSchedule, CampaignSegment


class CampaignSegmentSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(
        source="subscriber_group.name", read_only=True
    )
    subscriber_count = serializers.SerializerMethodField()

    class Meta:
        model = CampaignSegment
        fields = [
            "id",
            "subscriber_group",
            "group_name",
            "subscriber_count",
            "is_excluded",
        ]
        read_only_fields = ["id"]

    def get_subscriber_count(self, obj):
        return obj.subscriber_group.subscribers.filter(is_active=True).count()


class CampaignScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSchedule
        fields = [
            "scheduled_at",
            "send_window_start",
            "send_window_end",
            "timezone",
            "recurrence",
            "recurrence_end_at",
            "max_recurrences",
            "recurrence_count",
            "last_run_at",
            "next_run_at",
        ]
        read_only_fields = ["recurrence_count", "last_run_at", "next_run_at"]


class CampaignResultSerializer(serializers.ModelSerializer):
    subscriber_email = serializers.CharField(
        source="subscriber.email", read_only=True
    )

    class Meta:
        model = CampaignResult
        fields = [
            "id",
            "subscriber",
            "subscriber_email",
            "notification",
            "status",
            "channel",
            "error_message",
            "sent_at",
            "delivered_at",
            "opened_at",
            "clicked_at",
            "created_at",
        ]
        read_only_fields = fields


class CampaignListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    campaign_type_display = serializers.CharField(
        source="get_campaign_type_display", read_only=True
    )
    delivery_rate = serializers.ReadOnlyField()
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    segment_count = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "campaign_type",
            "campaign_type_display",
            "status",
            "status_display",
            "channels",
            "estimated_recipients",
            "total_sent",
            "total_delivered",
            "total_failed",
            "total_opened",
            "total_clicked",
            "delivery_rate",
            "open_rate",
            "click_rate",
            "segment_count",
            "tags",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_segment_count(self, obj):
        return obj.segments.count()


class CampaignDetailSerializer(serializers.ModelSerializer):
    segments = CampaignSegmentSerializer(many=True, read_only=True)
    schedule = CampaignScheduleSerializer(read_only=True)
    delivery_rate = serializers.ReadOnlyField()
    open_rate = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()
    template_name = serializers.CharField(
        source="template.name", read_only=True, default=None
    )
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, default=None
    )

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "description",
            "campaign_type",
            "status",
            "template",
            "template_name",
            "subject_override",
            "body_override",
            "channels",
            "context_data",
            "send_to_all",
            "estimated_recipients",
            "total_sent",
            "total_delivered",
            "total_failed",
            "total_opened",
            "total_clicked",
            "delivery_rate",
            "open_rate",
            "click_rate",
            "tags",
            "segments",
            "schedule",
            "created_by_email",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "total_sent",
            "total_delivered",
            "total_failed",
            "total_opened",
            "total_clicked",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class CampaignCreateSerializer(serializers.ModelSerializer):
    segments = CampaignSegmentSerializer(many=True, required=False)
    schedule = CampaignScheduleSerializer(required=False)

    class Meta:
        model = Campaign
        fields = [
            "name",
            "description",
            "campaign_type",
            "template",
            "subject_override",
            "body_override",
            "channels",
            "context_data",
            "send_to_all",
            "tags",
            "segments",
            "schedule",
        ]

    def validate_channels(self, value):
        if not value:
            raise serializers.ValidationError("At least one channel is required.")
        valid_channels = {"email", "sms", "push", "slack", "webhook"}
        invalid = set(value) - valid_channels
        if invalid:
            raise serializers.ValidationError(f"Invalid channels: {invalid}")
        return value

    def validate(self, attrs):
        if not attrs.get("template") and not attrs.get("body_override"):
            raise serializers.ValidationError(
                "Either a template or body_override is required."
            )
        return attrs

    def create(self, validated_data):
        segments_data = validated_data.pop("segments", [])
        schedule_data = validated_data.pop("schedule", None)

        campaign = Campaign.objects.create(
            organization=self.context["request"].user.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )

        for segment_data in segments_data:
            CampaignSegment.objects.create(campaign=campaign, **segment_data)

        if schedule_data:
            CampaignSchedule.objects.create(campaign=campaign, **schedule_data)
            if campaign.status == Campaign.Status.DRAFT:
                campaign.status = Campaign.Status.SCHEDULED
                campaign.save(update_fields=["status"])

        return campaign

    def update(self, instance, validated_data):
        segments_data = validated_data.pop("segments", None)
        schedule_data = validated_data.pop("schedule", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if segments_data is not None:
            instance.segments.all().delete()
            for segment_data in segments_data:
                CampaignSegment.objects.create(campaign=instance, **segment_data)

        if schedule_data is not None:
            schedule, _ = CampaignSchedule.objects.update_or_create(
                campaign=instance, defaults=schedule_data
            )

        return instance
