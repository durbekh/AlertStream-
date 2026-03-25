from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import APIKeyConfigViewSet, RateLimitViewSet

router = DefaultRouter()
router.register(r"configs", APIKeyConfigViewSet, basename="api-key-config")
router.register(r"rate-limits", RateLimitViewSet, basename="rate-limit")

urlpatterns = [
    path("", include(router.urls)),
]
