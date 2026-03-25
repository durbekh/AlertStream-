import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationMember

from .models import Preference, Subscriber, SubscriberGroup, Unsubscribe
from .serializers import (
    PreferenceSerializer,
    SubscriberCreateSerializer,
    SubscriberDetailSerializer,
    SubscriberGroupCreateSerializer,
    SubscriberGroupDetailSerializer,
    SubscriberGroupListSerializer,
    SubscriberListSerializer,
    UnsubscribePublicSerializer,
    UnsubscribeSerializer,
)

logger = logging.getLogger(__name__)


class SubscriberViewSet(viewsets.ModelViewSet):
    """ViewSet for managing subscribers."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "email": ["exact", "icontains"],
        "is_active": ["exact"],
        "tags": ["contains"],
        "created_at": ["gte", "lte"],
    }
    search_fields = ["email", "name", "first_name", "last_name", "external_id", "phone"]
    ordering_fields = ["name", "email", "created_at", "total_notifications", "last_notified_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return SubscriberListSerializer
        if self.action in ("create", "update", "partial_update"):
            return SubscriberCreateSerializer
        return SubscriberDetailSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return Subscriber.objects.none()
        return Subscriber.objects.filter(
            organization=org,
        ).prefetch_related("groups", "preferences")

    @action(detail=True, methods=["get", "put"])
    def preferences(self, request, pk=None):
        """Get or update subscriber notification preferences."""
        subscriber = self.get_object()

        if request.method == "GET":
            prefs = Preference.objects.filter(subscriber=subscriber)
            serializer = PreferenceSerializer(prefs, many=True)
            return Response(serializer.data)

        serializer = PreferenceSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        subscriber.preferences.all().delete()
        for pref_data in serializer.validated_data:
            Preference.objects.create(subscriber=subscriber, **pref_data)

        return Response(
            {"message": "Preferences updated.", "count": len(serializer.validated_data)},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def bulk_import(self, request):
        """Bulk import subscribers from a list."""
        subscribers_data = request.data.get("subscribers", [])
        if not subscribers_data:
            return Response(
                {"error": "No subscribers provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = request.user.organization
        created = 0
        updated = 0
        errors = []

        for idx, data in enumerate(subscribers_data):
            try:
                email = data.get("email", "")
                if email:
                    subscriber, was_created = Subscriber.objects.update_or_create(
                        organization=org,
                        email=email,
                        defaults={
                            "name": data.get("name", ""),
                            "first_name": data.get("first_name", ""),
                            "last_name": data.get("last_name", ""),
                            "phone": data.get("phone", ""),
                            "external_id": data.get("external_id", ""),
                            "custom_data": data.get("custom_data", {}),
                            "tags": data.get("tags", []),
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                    group_ids = data.get("group_ids", [])
                    if group_ids:
                        groups = SubscriberGroup.objects.filter(
                            id__in=group_ids, organization=org
                        )
                        subscriber.groups.add(*groups)
                else:
                    errors.append({"index": idx, "error": "Email is required."})
            except Exception as e:
                errors.append({"index": idx, "error": str(e)})

        return Response(
            {
                "created": created,
                "updated": updated,
                "errors": errors,
                "total_processed": created + updated,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Deactivate a subscriber."""
        subscriber = self.get_object()
        subscriber.is_active = False
        subscriber.save(update_fields=["is_active", "updated_at"])

        return Response(
            {"message": "Subscriber deactivated.", "id": str(subscriber.id)},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """Reactivate a deactivated subscriber."""
        subscriber = self.get_object()
        subscriber.is_active = True
        subscriber.save(update_fields=["is_active", "updated_at"])

        return Response(
            {"message": "Subscriber reactivated.", "id": str(subscriber.id)},
            status=status.HTTP_200_OK,
        )


class SubscriberGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for managing subscriber groups/segments."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "group_type": ["exact"],
        "is_active": ["exact"],
    }
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return SubscriberGroupListSerializer
        if self.action in ("create", "update", "partial_update"):
            return SubscriberGroupCreateSerializer
        return SubscriberGroupDetailSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return SubscriberGroup.objects.none()
        return SubscriberGroup.objects.filter(organization=org).prefetch_related("subscribers")

    @action(detail=True, methods=["post"])
    def add_subscribers(self, request, pk=None):
        """Add subscribers to a group."""
        group = self.get_object()
        subscriber_ids = request.data.get("subscriber_ids", [])

        if not subscriber_ids:
            return Response(
                {"error": "subscriber_ids is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscribers = Subscriber.objects.filter(
            id__in=subscriber_ids, organization=group.organization
        )
        group.subscribers.add(*subscribers)

        return Response(
            {"message": f"Added {subscribers.count()} subscribers to group.", "group_id": str(group.id)},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def remove_subscribers(self, request, pk=None):
        """Remove subscribers from a group."""
        group = self.get_object()
        subscriber_ids = request.data.get("subscriber_ids", [])

        if not subscriber_ids:
            return Response(
                {"error": "subscriber_ids is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscribers = Subscriber.objects.filter(id__in=subscriber_ids)
        group.subscribers.remove(*subscribers)

        return Response(
            {"message": f"Removed {subscribers.count()} subscribers from group."},
            status=status.HTTP_200_OK,
        )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def public_unsubscribe(request):
    """Public endpoint for subscribers to unsubscribe via token."""
    serializer = UnsubscribePublicSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data["token"]
    try:
        subscriber = Subscriber.objects.get(unsubscribe_token=token)
    except Subscriber.DoesNotExist:
        return Response(
            {"error": "Invalid unsubscribe token."},
            status=status.HTTP_404_NOT_FOUND,
        )

    Unsubscribe.objects.create(
        subscriber=subscriber,
        channel=serializer.validated_data.get("channel", ""),
        category=serializer.validated_data.get("category", ""),
        reason=serializer.validated_data["reason"],
        feedback=serializer.validated_data.get("feedback", ""),
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return Response(
        {"message": "You have been unsubscribed successfully."},
        status=status.HTTP_200_OK,
    )
