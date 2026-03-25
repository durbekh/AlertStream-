from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeliveryLogViewSet, DeliveryStatusViewSet, RetryLogViewSet

router = DefaultRouter()
router.register(r"logs", DeliveryLogViewSet, basename="delivery-log")
router.register(r"statuses", DeliveryStatusViewSet, basename="delivery-status")
router.register(r"retries", RetryLogViewSet, basename="retry-log")

urlpatterns = [
    path("", include(router.urls)),
]
