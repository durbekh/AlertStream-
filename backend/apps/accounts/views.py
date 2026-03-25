from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import APIKey, Organization
from .permissions import IsOrganizationAdmin, IsOrganizationMember, IsOrganizationOwner
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    ChangePasswordSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Register a new user account."""

    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "message": "Account created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the current user's profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    """Change the current user's password."""

    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class OrganizationViewSet(viewsets.ModelViewSet):
    """Manage organizations."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all()
        if self.request.user.organization:
            return Organization.objects.filter(pk=self.request.user.organization_id)
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [permissions.IsAuthenticated(), IsOrganizationAdmin()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsOrganizationOwner()]
        return super().get_permissions()

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """List organization members."""
        org = self.get_object()
        members = User.objects.filter(organization=org)
        serializer = UserSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        """Invite a user to the organization."""
        org = self.get_object()
        email = request.data.get("email")
        role = request.data.get("role", "member")

        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
            if user.organization:
                return Response(
                    {"error": "User already belongs to an organization."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.organization = org
            user.role = role
            user.save(update_fields=["organization", "role"])
            return Response(
                {"message": f"User {email} added to organization."},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found. They must register first."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        """Remove a member from the organization."""
        org = self.get_object()
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"error": "user_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id, organization=org)
            if user == request.user:
                return Response(
                    {"error": "You cannot remove yourself."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.organization = None
            user.role = "member"
            user.save(update_fields=["organization", "role"])
            return Response(
                {"message": "Member removed successfully."},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found in this organization."},
                status=status.HTTP_404_NOT_FOUND,
            )


class APIKeyViewSet(viewsets.ModelViewSet):
    """Manage API keys for programmatic access."""

    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    def get_queryset(self):
        return APIKey.objects.filter(
            organization=self.request.user.organization
        ).select_related("created_by")

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """Revoke an API key."""
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save(update_fields=["is_active"])
        return Response(
            {"message": "API key revoked successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        """Regenerate an API key (creates new key, revokes old)."""
        old_key = self.get_object()
        old_key.is_active = False
        old_key.save(update_fields=["is_active"])

        raw_key, prefix = APIKey.generate_key()
        hashed = APIKey.hash_key(raw_key)

        new_key = APIKey.objects.create(
            name=old_key.name,
            prefix=prefix,
            hashed_key=hashed,
            organization=old_key.organization,
            created_by=request.user,
            scopes=old_key.scopes,
            rate_limit=old_key.rate_limit,
            expires_at=old_key.expires_at,
        )

        serializer = APIKeySerializer(new_key)
        data = serializer.data
        data["key"] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)
