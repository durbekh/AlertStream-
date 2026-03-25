import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import HasAPIKeyPermission, IsOrganizationMember

from .models import DeliveryAttempt, Notification, NotificationLog
from .serializers import (
    BulkSendNotificationSerializer,
    DeliveryAttemptSerializer,
    NotificationCancelSerializer,
    NotificationDetailSerializer,
    NotificationListSerializer,
    NotificationLogSerializer,
    SendNotificationSerializer,
)
from .services import NotificationService

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.
    Supports both JWT and API Key authentication.
    """

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "status": ["exact", "in"],
        "priority": ["exact"],
        "channels": ["contains"],
        "created_at": ["gte", "lte"],
        "recipient": ["exact", "icontains"],
    }
    search_fields = ["recipient", "subject", "external_id", "group_id"]
    ordering_fields = ["created_at", "updated_at", "priority", "status"]

    def get_permissions(self):
        """Allow both JWT and API Key authentication."""
        return [
            permissions.IsAuthenticated() | HasAPIKeyPermission(),
        ]

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationListSerializer
        if self.action in ("create", "send"):
            return SendNotificationSerializer
        if self.action == "bulk_send":
            return BulkSendNotificationSerializer
        if self.action == "cancel":
            return NotificationCancelSerializer
        return NotificationDetailSerializer

    def get_queryset(self):
        org = self._get_organization()
        if not org:
            return Notification.objects.none()

        queryset = Notification.objects.filter(organization=org)

        if self.action == "retrieve":
            queryset = queryset.prefetch_related("delivery_attempts", "logs")

        return queryset

    def _get_organization(self):
        """Get organization from JWT user or API key."""
        if hasattr(self.request, "organization"):
            return self.request.organization
        if hasattr(self.request, "user") and self.request.user.is_authenticated:
            return self.request.user.organization
        return None

    def create(self, request, *args, **kwargs):
        """Send a notification."""
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = self._get_organization()
        if not org:
            return Response(
                {"error": "No organization found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            notification = NotificationService.create_notification(
                organization=org,
                created_by=request.user if request.user.is_authenticated else None,
                api_key=getattr(request, "api_key", None),
                **serializer.validated_data,
            )

            # Queue for async processing
            from tasks.notification_tasks import process_notification_task

            process_notification_task.delay(str(notification.id))

            return Response(
                NotificationDetailSerializer(notification).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"])
    def bulk_send(self, request):
        """Send multiple notifications at once."""
        serializer = BulkSendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = self._get_organization()
        if not org:
            return Response(
                {"error": "No organization found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []
        errors = []

        for idx, notif_data in enumerate(serializer.validated_data["notifications"]):
            try:
                notification = NotificationService.create_notification(
                    organization=org,
                    created_by=request.user if request.user.is_authenticated else None,
                    api_key=getattr(request, "api_key", None),
                    **notif_data,
                )
                from tasks.notification_tasks import process_notification_task

                process_notification_task.delay(str(notification.id))
                results.append(
                    {"index": idx, "id": str(notification.id), "status": "queued"}
                )
            except Exception as e:
                errors.append({"index": idx, "error": str(e)})

        return Response(
            {"results": results, "errors": errors},
            status=status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a pending notification."""
        serializer = NotificationCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            notification = NotificationService.cancel_notification(
                notification_id=pk,
                reason=serializer.validated_data.get("reason", ""),
            )
            return Response(
                NotificationDetailSerializer(notification).data,
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"])
    def status_detail(self, request, pk=None):
        """Get detailed delivery status."""
        try:
            status_data = NotificationService.get_notification_status(pk)
            return Response(status_data)
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """Get notification delivery timeline (logs)."""
        notification = self.get_object()
        logs = NotificationLog.objects.filter(notification=notification).order_by(
            "timestamp"
        )
        serializer = NotificationLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def attempts(self, request, pk=None):
        """Get delivery attempts for a notification."""
        notification = self.get_object()
        attempts = DeliveryAttempt.objects.filter(notification=notification)
        serializer = DeliveryAttemptSerializer(attempts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """Manually retry a failed notification."""
        notification = self.get_object()

        if notification.status not in (
            Notification.Status.FAILED,
            Notification.Status.PARTIALLY_DELIVERED,
        ):
            return Response(
                {"error": "Only failed notifications can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        channels = request.data.get("channels", notification.channels)

        from tasks.retry_tasks import retry_notification_task

        retry_notification_task.delay(str(notification.id), channels)

        return Response(
            {"message": "Retry queued.", "notification_id": str(notification.id)},
            status=status.HTTP_202_ACCEPTED,
        )
