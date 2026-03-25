import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationMember

from .models import DeliveryLog, DeliveryStatus, RetryLog
from .serializers import (
    DeliveryLogDetailSerializer,
    DeliveryLogSerializer,
    DeliveryStatusSerializer,
    RetryLogSerializer,
)

logger = logging.getLogger(__name__)


class DeliveryLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for browsing delivery logs."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "channel": ["exact", "in"],
        "event": ["exact", "in"],
        "level": ["exact", "in"],
        "provider": ["exact"],
        "status_code": ["exact", "gte", "lte"],
        "timestamp": ["gte", "lte"],
    }
    search_fields = ["recipient", "message", "provider_message_id", "error_code"]
    ordering_fields = ["timestamp", "duration_ms", "status_code"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DeliveryLogDetailSerializer
        return DeliveryLogSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return DeliveryLog.objects.none()
        return DeliveryLog.objects.filter(organization=org)

    @action(detail=False, methods=["get"])
    def errors(self, request):
        """Get recent delivery errors."""
        org = request.user.organization
        errors = DeliveryLog.objects.filter(
            organization=org,
            level__in=["error", "critical"],
        ).order_by("-timestamp")[:100]

        serializer = DeliveryLogSerializer(errors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get delivery log summary by channel and event."""
        from django.db.models import Avg, Count

        org = request.user.organization
        summary = DeliveryLog.objects.filter(
            organization=org,
        ).values("channel", "event").annotate(
            count=Count("id"),
            avg_duration=Avg("duration_ms"),
        ).order_by("channel", "event")

        return Response(list(summary))


class DeliveryStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for tracking delivery statuses."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    serializer_class = DeliveryStatusSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        "channel": ["exact", "in"],
        "status": ["exact", "in"],
        "provider": ["exact"],
    }
    ordering_fields = ["updated_at", "created_at"]

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return DeliveryStatus.objects.none()
        return DeliveryStatus.objects.filter(
            notification__organization=org
        ).select_related("notification")


class RetryLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for browsing retry logs."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    serializer_class = RetryLogSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        "channel": ["exact"],
        "status": ["exact", "in"],
        "attempt_number": ["exact", "gte"],
    }
    ordering_fields = ["created_at", "scheduled_at"]

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return RetryLog.objects.none()
        return RetryLog.objects.filter(
            notification__organization=org
        ).select_related("notification")

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get pending retry attempts."""
        org = request.user.organization
        pending = RetryLog.objects.filter(
            notification__organization=org,
            status=RetryLog.RetryStatus.PENDING,
        ).order_by("scheduled_at")

        page = self.paginate_queryset(pending)
        if page is not None:
            serializer = RetryLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = RetryLogSerializer(pending, many=True)
        return Response(serializer.data)
