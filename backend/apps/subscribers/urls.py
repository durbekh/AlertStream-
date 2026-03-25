from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SubscriberGroupViewSet, SubscriberViewSet, public_unsubscribe

router = DefaultRouter()
router.register(r"groups", SubscriberGroupViewSet, basename="subscriber-group")
router.register(r"", SubscriberViewSet, basename="subscriber")

urlpatterns = [
    path("unsubscribe/", public_unsubscribe, name="public-unsubscribe"),
    path("", include(router.urls)),
]
