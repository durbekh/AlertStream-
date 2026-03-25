import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationAdmin, IsOrganizationMember

from .models import Channel
from .serializers import (
    ChannelCreateSerializer,
    ChannelDetailSerializer,
    ChannelListSerializer,
    ChannelTestSerializer,
)

logger = logging.getLogger(__name__)


class ChannelViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification channels."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "channel_type": ["exact", "in"],
        "is_active": ["exact"],
        "is_default": ["exact"],
    }
    search_fields = ["name"]
    ordering_fields = ["name", "channel_type", "priority", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ChannelListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ChannelCreateSerializer
        if self.action == "test":
            return ChannelTestSerializer
        return ChannelDetailSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return Channel.objects.none()
        return Channel.objects.filter(organization=org).select_related(
            "email_config",
            "sms_config",
            "push_config",
            "webhook_config",
            "slack_config",
        )

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        return super().get_permissions()

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Send a test notification through this channel."""
        channel = self.get_object()
        serializer = ChannelTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from apps.channels.providers import get_provider

            provider = get_provider(channel.channel_type, channel.organization)
            result = provider.send(
                recipient=serializer.validated_data["test_recipient"],
                recipient_data={},
                subject="AlertStream Test Notification",
                body=serializer.validated_data["test_message"],
                body_html=f"<p>{serializer.validated_data['test_message']}</p>",
                metadata={"test": True},
            )
            channel.record_test(success=True)

            return Response(
                {"status": "success", "message": "Test notification sent.", "details": result},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            channel.record_test(success=False)
            logger.error(f"Channel test failed for {channel.id}: {e}")
            return Response(
                {"status": "failed", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        """Toggle channel active state."""
        channel = self.get_object()
        channel.is_active = not channel.is_active
        channel.save(update_fields=["is_active", "updated_at"])

        return Response(
            {
                "id": str(channel.id),
                "is_active": channel.is_active,
                "message": f"Channel {'activated' if channel.is_active else 'deactivated'}.",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        """Set a channel as the default for its type."""
        channel = self.get_object()

        Channel.objects.filter(
            organization=channel.organization,
            channel_type=channel.channel_type,
            is_default=True,
        ).update(is_default=False)

        channel.is_default = True
        channel.save(update_fields=["is_default", "updated_at"])

        return Response(
            {"message": f"{channel.name} set as default {channel.get_channel_type_display()} channel."},
            status=status.HTTP_200_OK,
        )
