import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_campaign_task(self, campaign_id):
    """Execute a campaign by sending notifications to all targeted subscribers."""
    from apps.notifications.services import NotificationService
    from apps.subscribers.models import Subscriber

    from .models import Campaign, CampaignResult

    try:
        campaign = Campaign.objects.select_related(
            "organization", "template"
        ).get(pk=campaign_id)
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found")
        return

    if campaign.status not in (Campaign.Status.SENDING,):
        logger.info(f"Campaign {campaign_id} is not in sending state, skipping")
        return

    logger.info(f"Starting campaign execution: {campaign.name} ({campaign_id})")

    # Resolve target subscribers
    subscribers = _resolve_subscribers(campaign)
    campaign.estimated_recipients = subscribers.count()
    campaign.save(update_fields=["estimated_recipients"])

    batch_size = 100
    total_processed = 0

    for batch_start in range(0, subscribers.count(), batch_size):
        # Check if campaign was paused or cancelled
        campaign.refresh_from_db(fields=["status"])
        if campaign.status in (Campaign.Status.PAUSED, Campaign.Status.CANCELLED):
            logger.info(f"Campaign {campaign_id} was {campaign.status}, stopping execution")
            return

        batch = subscribers[batch_start:batch_start + batch_size]

        for subscriber in batch:
            try:
                _send_to_subscriber(campaign, subscriber)
                total_processed += 1
            except Exception as e:
                logger.error(
                    f"Failed to send campaign {campaign_id} to subscriber {subscriber.id}: {e}"
                )
                CampaignResult.objects.update_or_create(
                    campaign=campaign,
                    subscriber=subscriber,
                    defaults={
                        "status": CampaignResult.Status.FAILED,
                        "error_message": str(e),
                    },
                )

    # Update final counts
    results = CampaignResult.objects.filter(campaign=campaign)
    campaign.total_sent = results.exclude(status=CampaignResult.Status.PENDING).count()
    campaign.total_delivered = results.filter(
        status__in=["delivered", "opened", "clicked"]
    ).count()
    campaign.total_failed = results.filter(
        status__in=["failed", "bounced"]
    ).count()
    campaign.mark_completed()

    logger.info(
        f"Campaign {campaign.name} completed: {campaign.total_sent} sent, "
        f"{campaign.total_delivered} delivered, {campaign.total_failed} failed"
    )


def _resolve_subscribers(campaign):
    """Resolve the set of subscribers targeted by a campaign."""
    from apps.subscribers.models import Subscriber

    org = campaign.organization

    if campaign.send_to_all:
        return Subscriber.objects.filter(
            organization=org, is_active=True
        )

    included_groups = campaign.segments.filter(is_excluded=False).values_list(
        "subscriber_group_id", flat=True
    )
    excluded_groups = campaign.segments.filter(is_excluded=True).values_list(
        "subscriber_group_id", flat=True
    )

    queryset = Subscriber.objects.filter(
        organization=org,
        is_active=True,
        groups__in=included_groups,
    ).distinct()

    if excluded_groups:
        excluded_ids = Subscriber.objects.filter(
            groups__in=excluded_groups
        ).values_list("id", flat=True)
        queryset = queryset.exclude(id__in=excluded_ids)

    return queryset


@transaction.atomic
def _send_to_subscriber(campaign, subscriber):
    """Send the campaign notification to a single subscriber."""
    from apps.notifications.services import NotificationService

    from .models import CampaignResult

    # Check subscriber preferences
    if not subscriber.is_active:
        return

    # Build recipient data from subscriber
    recipient_data = {
        "email": subscriber.email,
        "phone": subscriber.phone,
        "device_token": subscriber.device_token,
    }

    # Merge campaign context with subscriber-specific data
    context = {**campaign.context_data}
    context.update({
        "subscriber_name": subscriber.name,
        "subscriber_email": subscriber.email,
        "unsubscribe_url": f"/unsubscribe/{subscriber.unsubscribe_token}",
    })
    if subscriber.custom_data:
        context.update(subscriber.custom_data)

    notification = NotificationService.create_notification(
        organization=campaign.organization,
        recipient=subscriber.email,
        channels=campaign.channels,
        subject=campaign.subject_override or "",
        body=campaign.body_override or "",
        template_id=str(campaign.template_id) if campaign.template_id else None,
        context=context,
        metadata={"campaign_id": str(campaign.id)},
        recipient_data=recipient_data,
        group_id=str(campaign.id),
    )

    CampaignResult.objects.update_or_create(
        campaign=campaign,
        subscriber=subscriber,
        defaults={
            "notification": notification,
            "status": CampaignResult.Status.SENT,
            "sent_at": timezone.now(),
        },
    )


@shared_task
def process_scheduled_campaigns():
    """Check for campaigns that are due to run and execute them."""
    from .models import Campaign, CampaignSchedule

    schedules = CampaignSchedule.objects.filter(
        campaign__status__in=[Campaign.Status.SCHEDULED],
    ).select_related("campaign")

    now = timezone.now()

    for schedule in schedules:
        if schedule.should_run():
            logger.info(f"Starting scheduled campaign: {schedule.campaign.name}")
            schedule.campaign.mark_started()
            schedule.last_run_at = now
            schedule.save(update_fields=["last_run_at"])
            execute_campaign_task.delay(str(schedule.campaign.id))


@shared_task
def update_campaign_stats(campaign_id):
    """Update campaign statistics from delivery results."""
    from .models import Campaign, CampaignResult

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return

    results = CampaignResult.objects.filter(campaign=campaign)
    campaign.total_sent = results.exclude(status=CampaignResult.Status.PENDING).count()
    campaign.total_delivered = results.filter(
        status__in=["delivered", "opened", "clicked"]
    ).count()
    campaign.total_failed = results.filter(status__in=["failed", "bounced"]).count()
    campaign.total_opened = results.filter(status__in=["opened", "clicked"]).count()
    campaign.total_clicked = results.filter(status="clicked").count()
    campaign.save(update_fields=[
        "total_sent", "total_delivered", "total_failed",
        "total_opened", "total_clicked", "updated_at",
    ])
