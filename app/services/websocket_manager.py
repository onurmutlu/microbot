from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import logging
from datetime import datetime
from app.core.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_subscriptions: Dict[str, Set[str]] = {}
        self.connection_times: Dict[str, datetime] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_subscriptions[user_id] = set()
        self.connection_times[user_id] = datetime.now()
        logger.info(f"User {user_id} connected to WebSocket")

    async def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            del self.user_subscriptions[user_id]
            del self.connection_times[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {str(e)}")
                await self.disconnect(user_id)

    async def broadcast(self, message: dict, user_ids: List[str] = None):
        if user_ids is None:
            user_ids = list(self.active_connections.keys())
        
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    async def subscribe(self, user_id: str, channel: str):
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].add(channel)
            logger.info(f"User {user_id} subscribed to channel {channel}")

    async def unsubscribe(self, user_id: str, channel: str):
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].discard(channel)
            logger.info(f"User {user_id} unsubscribed from channel {channel}")

    def is_connected(self, user_id: str) -> bool:
        return user_id in self.active_connections

    def get_connection_time(self, user_id: str) -> datetime:
        return self.connection_times.get(user_id)

websocket_manager = WebSocketManager() 