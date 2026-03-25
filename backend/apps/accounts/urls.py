from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    APIKeyViewSet,
    ChangePasswordView,
    OrganizationViewSet,
    ProfileView,
    RegisterView,
)

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"api-keys", APIKeyViewSet, basename="api-key")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("", include(router.urls)),
]
