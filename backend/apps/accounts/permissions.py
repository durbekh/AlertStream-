import logging

from django.utils import timezone
from rest_framework import permissions

from .models import APIKey

logger = logging.getLogger(__name__)


class IsOrganizationMember(permissions.BasePermission):
    """Ensure user belongs to an organization."""

    message = "You must belong to an organization to perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.organization is not None
        )


class IsOrganizationAdmin(permissions.BasePermission):
    """Ensure user is an admin or owner of their organization."""

    message = "You must be an organization admin to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ("admin", "owner")


class IsOrganizationOwner(permissions.BasePermission):
    """Ensure user is the owner of their organization."""

    message = "You must be the organization owner to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == "owner"


class HasAPIKeyPermission(permissions.BasePermission):
    """
    Custom permission that authenticates via API key.
    Checks X-API-Key header or Authorization: Api-Key <key>.
    """

    message = "Invalid or expired API key."

    def has_permission(self, request, view):
        api_key = self._extract_key(request)
        if not api_key:
            return False

        prefix = api_key[:8]
        hashed = APIKey.hash_key(api_key)

        try:
            key_obj = APIKey.objects.select_related("organization").get(
                prefix=prefix,
                hashed_key=hashed,
                is_active=True,
            )
        except APIKey.DoesNotExist:
            logger.warning(f"API key authentication failed for prefix: {prefix}")
            return False

        if key_obj.is_expired:
            logger.warning(f"Expired API key used: {prefix}")
            return False

        # Record usage
        ip = self._get_client_ip(request)
        key_obj.record_usage(ip_address=ip)

        # Attach organization and key to request
        request.organization = key_obj.organization
        request.api_key = key_obj
        return True

    def _extract_key(self, request):
        """Extract API key from various header formats."""
        # Check X-API-Key header
        api_key = request.META.get("HTTP_X_API_KEY")
        if api_key:
            return api_key

        # Check Authorization: Api-Key <key>
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Api-Key "):
            return auth_header[8:]

        return None

    def _get_client_ip(self, request):
        """Get client IP from request, considering proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class HasAPIKeyScope(permissions.BasePermission):
    """Check if API key has the required scope."""

    required_scope = None

    def has_permission(self, request, view):
        if not hasattr(request, "api_key"):
            return False

        api_key = request.api_key
        if not api_key.scopes:
            return True  # No scopes means full access

        required = self.required_scope or getattr(view, "required_scope", None)
        if required is None:
            return True

        return required in api_key.scopes


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object-level permission: only owner can modify."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, "organization"):
            return obj.organization == request.user.organization
        return False
