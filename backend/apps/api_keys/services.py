import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for managing API key operations and validation."""

    CACHE_PREFIX = "apikey_"
    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    def validate_key(raw_key):
        """Validate an API key and return the associated organization.

        Performs lookup with caching to reduce database queries.
        """
        from apps.accounts.models import APIKey

        prefix = raw_key[:8]
        cache_key = f"{APIKeyService.CACHE_PREFIX}{prefix}"

        cached = cache.get(cache_key)
        if cached:
            if cached == "__invalid__":
                return None
            return cached

        hashed = APIKey.hash_key(raw_key)

        try:
            key_obj = APIKey.objects.select_related("organization").get(
                prefix=prefix,
                hashed_key=hashed,
                is_active=True,
            )
        except APIKey.DoesNotExist:
            cache.set(cache_key, "__invalid__", 60)
            return None

        if key_obj.is_expired:
            cache.set(cache_key, "__invalid__", 60)
            return None

        result = {
            "key_id": str(key_obj.id),
            "organization_id": str(key_obj.organization_id),
            "organization_name": key_obj.organization.name,
            "scopes": key_obj.scopes,
            "rate_limit": key_obj.rate_limit,
        }
        cache.set(cache_key, result, APIKeyService.CACHE_TTL)
        return result

    @staticmethod
    def check_rate_limit(api_key_id, resource="api_calls"):
        """Check if the API key is within its rate limit.

        Uses Redis-based sliding window for accurate rate limiting.
        """
        from .models import RateLimit

        limits = RateLimit.objects.filter(
            api_key_id=api_key_id,
            resource=resource,
            is_active=True,
        )

        for limit in limits:
            if not limit.check_limit():
                logger.warning(
                    f"Rate limit exceeded for API key {api_key_id}: "
                    f"{limit.resource} ({limit.current_count}/{limit.max_requests})"
                )
                return False
            limit.increment()

        return True

    @staticmethod
    def check_rate_limit_redis(key_identifier, resource, max_requests, window_seconds):
        """Check rate limit using Redis sliding window counter."""
        cache_key = f"ratelimit:{key_identifier}:{resource}"

        current = cache.get(cache_key, 0)
        if current >= max_requests:
            return False

        pipe_result = cache.incr(cache_key)
        if pipe_result == 1:
            cache.expire(cache_key, window_seconds)

        return True

    @staticmethod
    def get_usage_stats(api_key_id):
        """Get comprehensive usage statistics for an API key."""
        from apps.accounts.models import APIKey
        from apps.notifications.models import Notification

        try:
            key = APIKey.objects.get(pk=api_key_id)
        except APIKey.DoesNotExist:
            return None

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        notifications_today = Notification.objects.filter(
            api_key=key,
            created_at__gte=today_start,
        ).count()

        notifications_month = Notification.objects.filter(
            api_key=key,
            created_at__gte=month_start,
        ).count()

        return {
            "key_id": str(key.id),
            "key_name": key.name,
            "total_requests": key.request_count,
            "last_used": key.last_used_at,
            "notifications_today": notifications_today,
            "notifications_this_month": notifications_month,
        }

    @staticmethod
    def invalidate_key_cache(api_key_prefix):
        """Invalidate the cache for an API key."""
        cache_key = f"{APIKeyService.CACHE_PREFIX}{api_key_prefix}"
        cache.delete(cache_key)

    @staticmethod
    def rotate_key(old_key_id, user):
        """Rotate an API key (deactivate old, create new)."""
        from apps.accounts.models import APIKey

        try:
            old_key = APIKey.objects.get(pk=old_key_id)
        except APIKey.DoesNotExist:
            raise ValueError("API key not found")

        # Deactivate old key
        old_key.is_active = False
        old_key.save(update_fields=["is_active"])

        APIKeyService.invalidate_key_cache(old_key.prefix)

        # Create new key
        raw_key, prefix = APIKey.generate_key()
        hashed = APIKey.hash_key(raw_key)

        new_key = APIKey.objects.create(
            name=old_key.name,
            prefix=prefix,
            hashed_key=hashed,
            organization=old_key.organization,
            created_by=user,
            scopes=old_key.scopes,
            rate_limit=old_key.rate_limit,
            expires_at=old_key.expires_at,
        )

        return new_key, raw_key
