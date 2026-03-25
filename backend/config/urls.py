from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    # JWT Auth
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # App URLs
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/templates/", include("apps.templates_engine.urls")),
    path("api/v1/channels/", include("apps.channels.urls")),
    path("api/v1/routing/", include("apps.routing.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

admin.site.site_header = "AlertStream Administration"
admin.site.site_title = "AlertStream Admin"
admin.site.index_title = "Notification Service Management"
