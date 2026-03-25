import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationAdmin, IsOrganizationMember

from .models import APIKey, RateLimit
from .serializers import (
    APIKeyConfigUpdateSerializer,
    APIKeyExtendedSerializer,
    RateLimitCreateSerializer,
    RateLimitSerializer,
)

logger = logging.getLogger(__name__)


class APIKeyConfigViewSet(viewsets.ModelViewSet):
    """Manage extended API key configuration (tiers, rate limits, IP whitelist)."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {"tier": ["exact"]}
    search_fields = ["account_api_key__name"]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return APIKeyConfigUpdateSerializer
        return APIKeyExtendedSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return APIKey.objects.none()
        return APIKey.objects.filter(
            account_api_key__organization=org
        ).select_related("account_api_key")

    @action(detail=True, methods=["post"])
    def reset_daily(self, request, pk=None):
        """Reset daily request counter for an API key."""
        config = self.get_object()
        config.reset_daily_counts()
        return Response(
            {"message": "Daily counts reset.", "daily_request_count": 0},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reset_monthly(self, request, pk=None):
        """Reset monthly counters for an API key."""
        config = self.get_object()
        config.reset_monthly_counts()
        return Response(
            {"message": "Monthly counts reset.", "monthly_notification_count": 0},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def usage(self, request, pk=None):
        """Get usage statistics for an API key."""
        config = self.get_object()
        return Response({
            "key_name": config.account_api_key.name,
            "tier": config.tier,
            "daily_usage": {
                "count": config.daily_request_count,
                "limit": config.daily_request_limit,
                "remaining": max(0, config.daily_request_limit - config.daily_request_count),
                "percent": round(
                    (config.daily_request_count / config.daily_request_limit) * 100, 2
                ) if config.daily_request_limit > 0 else 0,
            },
            "monthly_usage": {
                "notifications": config.monthly_notification_count,
                "limit": config.monthly_notification_limit,
                "remaining": max(0, config.monthly_notification_limit - config.monthly_notification_count),
                "percent": round(
                    (config.monthly_notification_count / config.monthly_notification_limit) * 100, 2
                ) if config.monthly_notification_limit > 0 else 0,
            },
            "last_used": config.account_api_key.last_used_at,
            "total_requests": config.account_api_key.request_count,
        })


class RateLimitViewSet(viewsets.ModelViewSet):
    """Manage rate limit configurations."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        "scope": ["exact"],
        "resource": ["exact"],
        "is_active": ["exact"],
    }
    ordering_fields = ["resource", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create",):
            return RateLimitCreateSerializer
        return RateLimitSerializer

    def get_queryset(self):
        org = self.request.user.organization
        if not org:
            return RateLimit.objects.none()
        return RateLimit.objects.filter(organization=org)

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """Reset the counter for a rate limit."""
        rate_limit = self.get_object()
        rate_limit.current_count = 0
        from django.utils import timezone
        rate_limit.window_start = timezone.now()
        rate_limit.save(update_fields=["current_count", "window_start"])

        return Response(
            {"message": "Rate limit counter reset.", "current_count": 0},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get a summary of all active rate limits and current usage."""
        org = request.user.organization
        limits = RateLimit.objects.filter(organization=org, is_active=True)

        data = []
        for limit in limits:
            data.append({
                "id": str(limit.id),
                "resource": limit.resource,
                "scope": limit.scope,
                "max_requests": limit.max_requests,
                "current_count": limit.current_count,
                "window_type": limit.window_type,
                "usage_percent": round(
                    (limit.current_count / limit.max_requests) * 100, 2
                ) if limit.max_requests > 0 else 0,
                "is_within_window": limit.is_within_window(),
            })

        return Response({"rate_limits": data})
