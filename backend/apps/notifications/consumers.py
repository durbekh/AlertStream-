import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for real-time notification delivery updates."""

    async def connect(self):
        self.org_id = self.scope["url_route"]["kwargs"]["org_id"]
        self.group_name = f"notifications_{self.org_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        is_member = await self._verify_organization_membership(user, self.org_id)
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(f"WebSocket connected: user={user.email}, org={self.org_id}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )
        logger.info(f"WebSocket disconnected: org={getattr(self, 'org_id', 'unknown')}")

    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        message_type = content.get("type")

        if message_type == "ping":
            await self.send_json({"type": "pong"})
        elif message_type == "subscribe":
            notification_id = content.get("notification_id")
            if notification_id:
                sub_group = f"notification_{notification_id}"
                await self.channel_layer.group_add(sub_group, self.channel_name)
                await self.send_json({
                    "type": "subscribed",
                    "notification_id": notification_id,
                })

    async def notification_update(self, event):
        """Send notification status update to WebSocket clients."""
        await self.send_json({
            "type": "notification_update",
            "data": event["data"],
        })

    async def delivery_update(self, event):
        """Send delivery attempt update to WebSocket clients."""
        await self.send_json({
            "type": "delivery_update",
            "data": event["data"],
        })

    @database_sync_to_async
    def _verify_organization_membership(self, user, org_id):
        """Verify user belongs to the given organization."""
        return str(user.organization_id) == str(org_id) if user.organization_id else False


def send_notification_update(organization_id, notification_data):
    """Utility function to send notification updates via WebSocket."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    group_name = f"notifications_{organization_id}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "notification_update",
            "data": notification_data,
        },
    )


def send_delivery_update(organization_id, delivery_data):
    """Utility function to send delivery updates via WebSocket."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    group_name = f"notifications_{organization_id}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "delivery_update",
            "data": delivery_data,
        },
    )
