from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Any, Optional
import json
import asyncio
from datetime import datetime
from redis import Redis
from app.core.config import settings
from app.core.security import decode_access_token, WebSocketSecurity, websocket_rate_limiter
from app.core.logging import logger
from app.core.monitoring import websocket_monitor

class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_times: Dict[str, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self.redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.pubsub = self.redis.pubsub()
        self.channels = {
            "message_templates": "message_templates_updates",
            "auto_replies": "auto_replies_updates",
            "groups": "groups_updates",
            "scheduler": "scheduler_updates"
        }
        self.start_cleanup_task()

    async def connect(self, websocket: WebSocket, token: str) -> None:
        try:
            # Token doğrulama
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("Invalid token")

            # Rate limiting kontrolü
            if not await websocket_rate_limiter.check_rate_limit(websocket, user_id):
                raise ValueError("Rate limit exceeded")

            await websocket.accept()
            self.active_connections[user_id] = websocket
            self.connection_times[user_id] = datetime.now()
            
            # Redis kanallarına abone ol
            for channel in self.channels.values():
                await self.pubsub.subscribe(channel)
            
            # Redis mesaj dinleyicisini başlat
            asyncio.create_task(self._listen_redis_messages(user_id))
            
            logger.info(f"New WebSocket connection: {user_id}")
            websocket_monitor.connection_established(user_id)
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            await websocket.close(code=1008, reason=str(e))
            raise

    async def disconnect(self, user_id: str) -> None:
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
                del self.active_connections[user_id]
                del self.connection_times[user_id]
                
                # Redis aboneliklerini kaldır
                for channel in self.channels.values():
                    await self.pubsub.unsubscribe(channel)
                
                logger.info(f"WebSocket disconnected: {user_id}")
                websocket_monitor.connection_closed(user_id)
                
            except Exception as e:
                logger.error(f"Error during disconnect: {str(e)}")

    async def send_personal_message(self, user_id: str, message: Dict[str, Any]) -> None:
        if user_id in self.active_connections:
            try:
                # Rate limiting kontrolü
                if not await websocket_rate_limiter.check_rate_limit(self.active_connections[user_id], user_id):
                    logger.warning(f"Rate limit exceeded for user {user_id}")
                    return

                # Mesaj güvenliği kontrolü
                if not await WebSocketSecurity.validate_message_size(message):
                    logger.warning(f"Message size exceeds limit for user {user_id}")
                    return

                message = await WebSocketSecurity.sanitize_message(message)
                await self.active_connections[user_id].send_json(message)
                
                # Monitoring
                websocket_monitor.message_sent(user_id, message.get("type", "unknown"))
                
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {str(e)}")
                await self.disconnect(user_id)

    async def broadcast(self, message: Dict[str, Any], exclude_user: Optional[str] = None) -> None:
        for user_id, connection in self.active_connections.items():
            if user_id != exclude_user:
                try:
                    # Rate limiting kontrolü
                    if not await websocket_rate_limiter.check_rate_limit(connection, user_id):
                        continue

                    # Mesaj güvenliği kontrolü
                    if not await WebSocketSecurity.validate_message_size(message):
                        continue

                    message = await WebSocketSecurity.sanitize_message(message)
                    await connection.send_json(message)
                    
                    # Monitoring
                    websocket_monitor.message_sent(user_id, message.get("type", "unknown"))
                    
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
                    await self.disconnect(user_id)

    async def _listen_redis_messages(self, user_id: str) -> None:
        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = json.loads(message["data"])
                    websocket_monitor.message_received(user_id, data.get("type", "unknown"))
                    await self.send_personal_message(user_id, data)
            except Exception as e:
                logger.error(f"Error processing Redis message: {str(e)}")
                await asyncio.sleep(1)

    async def _cleanup_inactive_connections(self) -> None:
        while True:
            try:
                current_time = datetime.now()
                inactive_tokens = [
                    token for token, connect_time in self.connection_times.items()
                    if (current_time - connect_time).total_seconds() > settings.WS_CONNECTION_TIMEOUT
                ]
                for token in inactive_tokens:
                    await self.disconnect(token)
                await asyncio.sleep(settings.WS_CLEANUP_INTERVAL)
            except Exception as e:
                logger.error(f"Error in connection cleanup: {str(e)}")
                await asyncio.sleep(60)

    def start_cleanup_task(self) -> None:
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())

    def stop_cleanup_task(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    def get_connection_stats(self) -> Dict[str, Any]:
        return {
            "active_connections": len(self.active_connections),
            "connection_times": self.connection_times,
            "monitoring_stats": websocket_monitor.get_stats()
        }

    async def publish_update(self, channel: str, data: Dict[str, Any]) -> None:
        try:
            await self.redis.publish(self.channels[channel], json.dumps(data))
            logger.info(f"WebSocket update published to channel {channel}")
        except Exception as e:
            logger.error(f"Error publishing update to channel {channel}: {str(e)}")

websocket_manager = WebSocketManager() 