from rest_framework import serializers

from .models import NotificationTemplate, TemplateVariable, TemplateVersion


class TemplateVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateVariable
        fields = [
            "id",
            "name",
            "variable_type",
            "description",
            "default_value",
            "is_required",
            "sample_value",
        ]
        read_only_fields = ["id"]


class TemplateVersionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, default=None
    )

    class Meta:
        model = TemplateVersion
        fields = [
            "id",
            "version_number",
            "subject",
            "body_text",
            "body_html",
            "change_notes",
            "created_by_email",
            "is_published",
            "created_at",
        ]
        read_only_fields = ["id", "version_number", "created_at"]


class TemplateListSerializer(serializers.ModelSerializer):
    variable_count = serializers.SerializerMethodField()
    template_type_display = serializers.CharField(
        source="get_template_type_display", read_only=True
    )

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "template_type",
            "template_type_display",
            "category",
            "tags",
            "is_active",
            "is_default",
            "current_version",
            "variable_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_version", "created_at", "updated_at"]

    def get_variable_count(self, obj):
        return obj.variables.count()


class TemplateDetailSerializer(serializers.ModelSerializer):
    variables = TemplateVariableSerializer(many=True, read_only=True)
    versions = TemplateVersionSerializer(many=True, read_only=True)
    detected_variables = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, default=None
    )

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "template_type",
            "subject",
            "body_text",
            "body_html",
            "category",
            "tags",
            "is_active",
            "is_default",
            "current_version",
            "created_by_email",
            "variables",
            "versions",
            "detected_variables",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "current_version",
            "created_at",
            "updated_at",
        ]

    def get_detected_variables(self, obj):
        return obj.get_variables()


class TemplateCreateSerializer(serializers.ModelSerializer):
    variables = TemplateVariableSerializer(many=True, required=False)

    class Meta:
        model = NotificationTemplate
        fields = [
            "name",
            "slug",
            "description",
            "template_type",
            "subject",
            "body_text",
            "body_html",
            "category",
            "tags",
            "is_active",
            "is_default",
            "variables",
        ]

    def create(self, validated_data):
        variables_data = validated_data.pop("variables", [])
        template = NotificationTemplate.objects.create(
            organization=self.context["request"].user.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )
        for var_data in variables_data:
            TemplateVariable.objects.create(template=template, **var_data)

        # Create initial version
        TemplateVersion.objects.create(
            template=template,
            version_number=1,
            subject=template.subject,
            body_text=template.body_text,
            body_html=template.body_html,
            change_notes="Initial version",
            created_by=self.context["request"].user,
            is_published=True,
        )
        return template

    def update(self, instance, validated_data):
        variables_data = validated_data.pop("variables", None)
        content_changed = False

        for attr, value in validated_data.items():
            if attr in ("subject", "body_text", "body_html"):
                if getattr(instance, attr) != value:
                    content_changed = True
            setattr(instance, attr, value)

        if content_changed:
            new_version_number = instance.current_version + 1
            TemplateVersion.objects.create(
                template=instance,
                version_number=new_version_number,
                subject=instance.subject,
                body_text=instance.body_text,
                body_html=instance.body_html,
                change_notes=f"Updated to version {new_version_number}",
                created_by=self.context["request"].user,
                is_published=True,
            )
            instance.current_version = new_version_number

        instance.save()

        if variables_data is not None:
            instance.variables.all().delete()
            for var_data in variables_data:
                TemplateVariable.objects.create(template=instance, **var_data)

        return instance


class TemplatePreviewSerializer(serializers.Serializer):
    """Serializer for previewing a template with sample context."""

    context = serializers.DictField(
        required=False,
        default=dict,
        help_text="Template variable values for preview rendering",
    )
