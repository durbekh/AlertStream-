import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for computing and aggregating analytics data."""

    @staticmethod
    def get_delivery_overview(organization, days=30, channel="all"):
        """Get a delivery overview summary for the dashboard."""
        from .models import DeliveryAnalytics

        start_date = timezone.now() - timedelta(days=days)
        filters = {
            "organization": organization,
            "granularity": "daily",
            "period_start__gte": start_date,
        }
        if channel != "all":
            filters["channel"] = channel
        else:
            filters["channel"] = "all"

        records = DeliveryAnalytics.objects.filter(**filters)

        agg = records.aggregate(
            total_sent=Sum("total_sent"),
            total_delivered=Sum("total_delivered"),
            total_failed=Sum("total_failed"),
            total_bounced=Sum("total_bounced"),
            avg_delivery_time=Avg("avg_delivery_time_ms"),
            total_cost=Sum("total_cost"),
            total_retries=Sum("total_retries"),
        )

        total_sent = agg["total_sent"] or 0
        total_delivered = agg["total_delivered"] or 0

        delivery_rate = 0.0
        if total_sent > 0:
            delivery_rate = round((total_delivered / total_sent) * 100, 2)

        # Get trend compared to previous period
        prev_start = start_date - timedelta(days=days)
        prev_filters = {**filters, "period_start__gte": prev_start, "period_start__lt": start_date}
        prev_records = DeliveryAnalytics.objects.filter(**prev_filters)
        prev_agg = prev_records.aggregate(total_sent=Sum("total_sent"))
        prev_sent = prev_agg["total_sent"] or 0

        trend = 0.0
        if prev_sent > 0:
            trend = round(((total_sent - prev_sent) / prev_sent) * 100, 2)

        return {
            "period_days": days,
            "channel": channel,
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_failed": agg["total_failed"] or 0,
            "total_bounced": agg["total_bounced"] or 0,
            "delivery_rate": delivery_rate,
            "avg_delivery_time_ms": round(agg["avg_delivery_time"] or 0),
            "total_cost": float(agg["total_cost"] or 0),
            "total_retries": agg["total_retries"] or 0,
            "volume_trend_percent": trend,
        }

    @staticmethod
    def get_engagement_overview(organization, days=30, channel="all"):
        """Get engagement metrics overview."""
        from .models import EngagementMetrics

        start_date = timezone.now() - timedelta(days=days)
        filters = {
            "organization": organization,
            "granularity": "daily",
            "period_start__gte": start_date,
        }
        if channel != "all":
            filters["channel"] = channel
        else:
            filters["channel"] = "all"

        records = EngagementMetrics.objects.filter(**filters)

        agg = records.aggregate(
            total_delivered=Sum("total_delivered"),
            total_opened=Sum("total_opened"),
            unique_opens=Sum("unique_opens"),
            total_clicked=Sum("total_clicked"),
            unique_clicks=Sum("unique_clicks"),
            total_unsubscribed=Sum("total_unsubscribed"),
            total_complained=Sum("total_complained"),
        )

        total_delivered = agg["total_delivered"] or 0
        total_opened = agg["total_opened"] or 0
        unique_opens = agg["unique_opens"] or 0
        total_clicked = agg["total_clicked"] or 0

        open_rate = 0.0
        click_rate = 0.0
        click_to_open_rate = 0.0

        if total_delivered > 0:
            open_rate = round((unique_opens / total_delivered) * 100, 2)
            click_rate = round((agg["unique_clicks"] or 0) / total_delivered * 100, 2)
        if unique_opens > 0:
            click_to_open_rate = round((agg["unique_clicks"] or 0) / unique_opens * 100, 2)

        return {
            "period_days": days,
            "channel": channel,
            "total_delivered": total_delivered,
            "total_opened": total_opened,
            "unique_opens": unique_opens,
            "total_clicked": total_clicked,
            "unique_clicks": agg["unique_clicks"] or 0,
            "total_unsubscribed": agg["total_unsubscribed"] or 0,
            "total_complained": agg["total_complained"] or 0,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "click_to_open_rate": click_to_open_rate,
        }

    @staticmethod
    def get_channel_comparison(organization, days=30):
        """Compare performance metrics across channels."""
        from .models import DeliveryAnalytics, EngagementMetrics

        start_date = timezone.now() - timedelta(days=days)
        channels_list = ["email", "sms", "push", "slack", "webhook"]
        comparison = []

        for ch in channels_list:
            delivery = DeliveryAnalytics.objects.filter(
                organization=organization,
                channel=ch,
                granularity="daily",
                period_start__gte=start_date,
            ).aggregate(
                total_sent=Sum("total_sent"),
                total_delivered=Sum("total_delivered"),
                total_failed=Sum("total_failed"),
                avg_delivery_time=Avg("avg_delivery_time_ms"),
                total_cost=Sum("total_cost"),
            )

            engagement = EngagementMetrics.objects.filter(
                organization=organization,
                channel=ch,
                granularity="daily",
                period_start__gte=start_date,
            ).aggregate(
                total_opened=Sum("total_opened"),
                total_clicked=Sum("total_clicked"),
                total_unsubscribed=Sum("total_unsubscribed"),
            )

            total_sent = delivery["total_sent"] or 0
            total_delivered = delivery["total_delivered"] or 0

            delivery_rate = 0.0
            if total_sent > 0:
                delivery_rate = round((total_delivered / total_sent) * 100, 2)

            open_rate = 0.0
            if total_delivered > 0:
                open_rate = round(((engagement["total_opened"] or 0) / total_delivered) * 100, 2)

            comparison.append({
                "channel": ch,
                "total_sent": total_sent,
                "total_delivered": total_delivered,
                "total_failed": delivery["total_failed"] or 0,
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "total_clicked": engagement["total_clicked"] or 0,
                "total_unsubscribed": engagement["total_unsubscribed"] or 0,
                "avg_delivery_time_ms": round(delivery["avg_delivery_time"] or 0),
                "total_cost": float(delivery["total_cost"] or 0),
            })

        return {"period_days": days, "channels": comparison}

    @staticmethod
    def aggregate_hourly_stats(organization):
        """Aggregate delivery stats for the last hour."""
        from apps.delivery.models import DeliveryLog, DeliveryStatus
        from apps.notifications.models import DeliveryAttempt

        from .models import DeliveryAnalytics

        now = timezone.now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        channels = ["email", "sms", "push", "slack", "webhook"]

        for channel in channels:
            attempts = DeliveryAttempt.objects.filter(
                notification__organization=organization,
                channel=channel,
                created_at__gte=hour_start,
                created_at__lt=hour_end,
            )

            total_sent = attempts.count()
            if total_sent == 0:
                continue

            total_delivered = attempts.filter(status="delivered").count()
            total_failed = attempts.filter(status="failed").count()
            total_bounced = attempts.filter(status="bounced").count()

            delivery_rate = Decimal(0)
            if total_sent > 0:
                delivery_rate = Decimal(total_delivered) / Decimal(total_sent)

            avg_time = attempts.filter(
                duration_ms__isnull=False
            ).aggregate(avg=Avg("duration_ms"))["avg"] or 0

            total_cost = attempts.aggregate(cost=Sum("cost"))["cost"] or Decimal(0)

            DeliveryAnalytics.objects.update_or_create(
                organization=organization,
                channel=channel,
                granularity="hourly",
                period_start=hour_start,
                defaults={
                    "period_end": hour_end,
                    "total_sent": total_sent,
                    "total_delivered": total_delivered,
                    "total_failed": total_failed,
                    "total_bounced": total_bounced,
                    "delivery_rate": delivery_rate,
                    "avg_delivery_time_ms": round(avg_time),
                    "total_cost": total_cost,
                },
            )
