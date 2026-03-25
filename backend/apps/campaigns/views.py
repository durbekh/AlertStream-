import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationMember

from .models import Campaign, CampaignResult
from .serializers import (
    CampaignCreateSerializer,
    CampaignDetailSerializer,
    CampaignListSerializer,
    CampaignResultSerializer,
)

logger = logging.getLogger(__name__)


class CampaignViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification campaigns."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "status": ["exact", "in"],
        "campaign_type": ["exact"],
        "channels": ["contains"],
        "created_at": ["gte", "lte"],
    }
    search_fields = ["name", "description"]
    ordering_fields = ["name", "status", "created_at", "started_at", "total_sent"]

    def get_serializer_class(self):
        if self.action == "list":
            return CampaignListSerializer
        if self.action in ("create", "update", "partial_update"):
            return CampaignCreateSerializer
        return CampaignDetailSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return Campaign.objects.none()
        return Campaign.objects.filter(
            organization=org
        ).prefetch_related("segments", "segments__subscriber_group").select_related("schedule", "template")

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Start sending a campaign."""
        campaign = self.get_object()

        if not campaign.can_start():
            return Response(
                {"error": f"Campaign cannot be started in '{campaign.get_status_display()}' state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from .tasks import execute_campaign_task

            campaign.mark_started()
            execute_campaign_task.delay(str(campaign.id))

            return Response(
                {
                    "message": "Campaign started.",
                    "campaign_id": str(campaign.id),
                    "status": campaign.status,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Failed to start campaign {campaign.id}: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        """Pause a sending campaign."""
        campaign = self.get_object()

        if campaign.status != Campaign.Status.SENDING:
            return Response(
                {"error": "Only sending campaigns can be paused."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=["status", "updated_at"])

        return Response(
            {"message": "Campaign paused.", "status": campaign.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        """Resume a paused campaign."""
        campaign = self.get_object()

        if campaign.status != Campaign.Status.PAUSED:
            return Response(
                {"error": "Only paused campaigns can be resumed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import execute_campaign_task

        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=["status", "updated_at"])
        execute_campaign_task.delay(str(campaign.id))

        return Response(
            {"message": "Campaign resumed.", "status": campaign.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a campaign."""
        campaign = self.get_object()

        if campaign.status in (Campaign.Status.COMPLETED, Campaign.Status.CANCELLED):
            return Response(
                {"error": "Campaign is already completed or cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign.status = Campaign.Status.CANCELLED
        campaign.save(update_fields=["status", "updated_at"])

        return Response(
            {"message": "Campaign cancelled.", "status": campaign.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Get delivery results for a campaign."""
        campaign = self.get_object()
        results = CampaignResult.objects.filter(campaign=campaign).select_related(
            "subscriber", "notification"
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            results = results.filter(status=status_filter)

        page = self.paginate_queryset(results)
        if page is not None:
            serializer = CampaignResultSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CampaignResultSerializer(results, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """Get aggregated statistics for a campaign."""
        campaign = self.get_object()
        results = CampaignResult.objects.filter(campaign=campaign)

        stats = {
            "campaign_id": str(campaign.id),
            "status": campaign.status,
            "total_recipients": results.count(),
            "sent": results.filter(status__in=["sent", "delivered", "opened", "clicked"]).count(),
            "delivered": results.filter(status__in=["delivered", "opened", "clicked"]).count(),
            "opened": results.filter(status__in=["opened", "clicked"]).count(),
            "clicked": results.filter(status="clicked").count(),
            "bounced": results.filter(status="bounced").count(),
            "failed": results.filter(status="failed").count(),
            "unsubscribed": results.filter(status="unsubscribed").count(),
            "delivery_rate": campaign.delivery_rate,
            "open_rate": campaign.open_rate,
            "click_rate": campaign.click_rate,
        }

        return Response(stats, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplicate a campaign."""
        original = self.get_object()

        new_campaign = Campaign.objects.create(
            organization=original.organization,
            name=request.data.get("name", f"{original.name} (Copy)"),
            description=original.description,
            campaign_type=original.campaign_type,
            template=original.template,
            subject_override=original.subject_override,
            body_override=original.body_override,
            channels=original.channels,
            context_data=original.context_data,
            send_to_all=original.send_to_all,
            tags=original.tags,
            created_by=request.user,
        )

        for segment in original.segments.all():
            segment.pk = None
            segment.campaign = new_campaign
            segment.save()

        return Response(
            CampaignDetailSerializer(new_campaign).data,
            status=status.HTTP_201_CREATED,
        )
