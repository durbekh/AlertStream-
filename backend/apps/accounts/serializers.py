from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import APIKey, Organization

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "organization",
            "organization_name",
            "role",
            "is_email_verified",
            "last_activity",
            "created_at",
        ]
        read_only_fields = ["id", "is_email_verified", "last_activity", "created_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone_number",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone_number"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=10)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    quota_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "website",
            "description",
            "plan",
            "max_notifications_per_month",
            "notifications_sent_this_month",
            "member_count",
            "quota_remaining",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "notifications_sent_this_month",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_member_count(self, obj):
        return obj.members.count()

    def get_quota_remaining(self, obj):
        return max(0, obj.max_notifications_per_month - obj.notifications_sent_this_month)


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["name", "slug", "website", "description"]

    def create(self, validated_data):
        org = Organization.objects.create(**validated_data)
        user = self.context["request"].user
        user.organization = org
        user.role = "owner"
        user.save(update_fields=["organization", "role"])
        return org


class APIKeySerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True
    )

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "prefix",
            "scopes",
            "is_active",
            "expires_at",
            "last_used_at",
            "last_used_ip",
            "request_count",
            "rate_limit",
            "created_by_email",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "prefix",
            "last_used_at",
            "last_used_ip",
            "request_count",
            "created_at",
        ]


class APIKeyCreateSerializer(serializers.ModelSerializer):
    key = serializers.CharField(read_only=True)

    class Meta:
        model = APIKey
        fields = ["name", "scopes", "expires_at", "rate_limit", "key"]
        read_only_fields = ["key"]

    def create(self, validated_data):
        raw_key, prefix = APIKey.generate_key()
        hashed = APIKey.hash_key(raw_key)

        api_key = APIKey.objects.create(
            prefix=prefix,
            hashed_key=hashed,
            organization=self.context["request"].user.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )
        api_key._raw_key = raw_key
        return api_key

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(instance, "_raw_key"):
            data["key"] = instance._raw_key
        return data
