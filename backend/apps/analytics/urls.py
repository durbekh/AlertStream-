from django.urls import path

from .views import (
    channel_performance,
    delivery_overview,
    delivery_timeseries,
    engagement_overview,
    engagement_timeseries,
    top_links,
)

urlpatterns = [
    path("delivery/overview/", delivery_overview, name="analytics-delivery-overview"),
    path("delivery/timeseries/", delivery_timeseries, name="analytics-delivery-timeseries"),
    path("engagement/overview/", engagement_overview, name="analytics-engagement-overview"),
    path("engagement/timeseries/", engagement_timeseries, name="analytics-engagement-timeseries"),
    path("channels/performance/", channel_performance, name="analytics-channel-performance"),
    path("links/top/", top_links, name="analytics-top-links"),
]
