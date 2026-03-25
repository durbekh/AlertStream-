import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationMember

from .models import NotificationTemplate, TemplateVersion
from .serializers import (
    TemplateCreateSerializer,
    TemplateDetailSerializer,
    TemplateListSerializer,
    TemplatePreviewSerializer,
    TemplateVersionSerializer,
)
from .services import TemplateRenderService

logger = logging.getLogger(__name__)


class TemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification templates."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "template_type": ["exact", "in"],
        "category": ["exact", "in"],
        "is_active": ["exact"],
        "tags": ["contains"],
    }
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at", "updated_at", "current_version"]

    def get_serializer_class(self):
        if self.action == "list":
            return TemplateListSerializer
        if self.action in ("create", "update", "partial_update"):
            return TemplateCreateSerializer
        if self.action == "preview":
            return TemplatePreviewSerializer
        return TemplateDetailSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return NotificationTemplate.objects.none()
        return NotificationTemplate.objects.filter(
            organization=org
        ).prefetch_related("variables", "versions")

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        """Preview a rendered template with context variables."""
        template = self.get_object()
        serializer = TemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        context = serializer.validated_data.get("context", {})

        # Auto-fill missing variables with sample values
        for variable in template.variables.all():
            if variable.name not in context:
                context[variable.name] = variable.sample_value or variable.default_value or f"[{variable.name}]"

        try:
            rendered = TemplateRenderService.render_template(
                template_id=str(template.id),
                context=context,
                organization=template.organization,
            )
            return Response(
                {
                    "subject": rendered.get("subject", ""),
                    "body_text": rendered.get("body", ""),
                    "body_html": rendered.get("body_html", ""),
                    "context_used": context,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Template preview failed for {template.id}: {e}")
            return Response(
                {"error": f"Template rendering failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        """List all versions of a template."""
        template = self.get_object()
        versions = TemplateVersion.objects.filter(template=template)
        serializer = TemplateVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path=r"versions/(?P<version_number>\d+)/publish")
    def publish_version(self, request, pk=None, version_number=None):
        """Publish a specific version of a template."""
        template = self.get_object()
        try:
            version = TemplateVersion.objects.get(
                template=template, version_number=int(version_number)
            )
        except TemplateVersion.DoesNotExist:
            return Response(
                {"error": f"Version {version_number} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        version.publish()
        return Response(
            {
                "message": f"Version {version_number} published.",
                "current_version": template.current_version,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Create a copy of an existing template."""
        original = self.get_object()
        new_name = request.data.get("name", f"{original.name} (Copy)")
        new_slug = request.data.get("slug", f"{original.slug}-copy")

        new_template = NotificationTemplate.objects.create(
            organization=original.organization,
            name=new_name,
            slug=new_slug,
            description=original.description,
            template_type=original.template_type,
            subject=original.subject,
            body_text=original.body_text,
            body_html=original.body_html,
            category=original.category,
            tags=original.tags,
            created_by=request.user,
        )

        for var in original.variables.all():
            var.pk = None
            var.template = new_template
            var.save()

        TemplateVersion.objects.create(
            template=new_template,
            version_number=1,
            subject=new_template.subject,
            body_text=new_template.body_text,
            body_html=new_template.body_html,
            change_notes=f"Duplicated from {original.name}",
            created_by=request.user,
            is_published=True,
        )

        return Response(
            TemplateDetailSerializer(new_template).data,
            status=status.HTTP_201_CREATED,
        )
