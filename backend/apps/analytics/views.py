import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationMember

from .models import DeliveryAnalytics, EngagementMetrics
from .services import AnalyticsService

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsOrganizationMember])
def delivery_overview(request):
    """Get a delivery overview dashboard for the organization."""
    org = request.user.organization
    days = int(request.query_params.get("days", 30))
    channel = request.query_params.get("channel", "all")

    overview = AnalyticsService.get_delivery_overview(org, days=days, channel=channel)
    return Response(overview)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsOrganizationMember])
def delivery_timeseries(request):
    """Get delivery statistics as a time series."""
    org = request.user.organization
    days = int(request.query_params.get("days", 30))
    granularity = request.query_params.get("granularity", "daily")
    channel = request.query_params.get("channel", "all")

    if granularity not in ("hourly", "daily", "weekly", "monthly"):
        return Response(
            {"error": "Invalid granularity. Use: hourly, daily, weekly, monthly"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    start_date = timezone.now() - timedelta(days=days)

    records = DeliveryAnalytics.objects.filter(
        organization=org,
        channel=channel,
        granularity=granularity,
        period_start__gte=start_date,
    ).order_by("period_start")

    data = [
        {
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "total_sent": r.total_sent,
            "total_delivered": r.total_delivered,
            "total_failed": r.total_failed,
            "total_bounced": r.total_bounced,
            "delivery_rate": r.delivery_rate_percent,
            "avg_delivery_time_ms": r.avg_delivery_time_ms,
            "total_cost": float(r.total_cost),
        }
        for r in records
    ]

    return Response({"granularity": granularity, "channel": channel, "data": data})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsOrganizationMember])
def engagement_overview(request):
    """Get engagement metrics overview."""
    org = request.user.organization
    days = int(request.query_params.get("days", 30))
    channel = request.query_params.get("channel", "all")

    overview = AnalyticsService.get_engagement_overview(org, days=days, channel=channel)
    return Response(overview)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsOrganizationMember])
def engagement_timeseries(request):
    """Get engagement metrics as a time series."""
    org = request.user.organization
    days = int(request.query_params.get("days", 30))
    granularity = request.query_params.get("granularity", "daily")
    channel = request.query_params.get("channel", "all")

    start_date = timezone.now() - timedelta(days=days)

    records = EngagementMetrics.objects.filter(
        organization=org,
        channel=channel,
        granularity=granularity,
        period_start__gte=start_date,
    ).order_by("period_start")

    data = [
        {
            "period_start": r.period_start.isoformat(),
            "total_delivered": r.total_delivered,
            "total_opened": r.total_opened,
            "unique_opens": r.unique_opens,
            "total_clicked": r.total_clicked,
            "unique_clicks": r.unique_clicks,
            "total_unsubscribed": r.total_unsubscribed,
            "open_rate": r.open_rate_percent,
            "click_rate": r.click_rate_percent,
        }
        for r in records
    ]

    return Response({"granularity": granularity, "channel": channel, "data": data})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsOrganizationMember])
def channel_performance(request):
    """Compare performance across channels."""
    org = request.user.organization
    days = int(request.query_params.get("days", 30))

    performance = AnalyticsService.get_channel_comparison(org, days=days)
    return Response(performance)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsOrganizationMember])
def top_links(request):
    """Get top clicked links across all campaigns."""
    org = request.user.organization
    days = int(request.query_params.get("days", 30))
    limit = int(request.query_params.get("limit", 20))

    start_date = timezone.now() - timedelta(days=days)

    recent = EngagementMetrics.objects.filter(
        organization=org,
        period_start__gte=start_date,
    ).exclude(top_clicked_links=[])

    link_counts = {}
    for record in recent:
        for link in record.top_clicked_links:
            url = link.get("url", "")
            clicks = link.get("clicks", 0)
            link_counts[url] = link_counts.get(url, 0) + clicks

    sorted_links = sorted(link_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    data = [{"url": url, "total_clicks": clicks} for url, clicks in sorted_links]

    return Response({"links": data, "period_days": days})
