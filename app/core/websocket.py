from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
from app.core.logging import logger

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: int = None):
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        self.active_connections[client_id].append(websocket)
        if user_id:
            self.user_connections[user_id] = websocket
        logger.info(f"WebSocket bağlantısı kuruldu: {client_id}")

    async def disconnect(self, websocket: WebSocket, client_id: str, user_id: int = None):
        if client_id in self.active_connections:
            self.active_connections[client_id].remove(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        if user_id and user_id in self.user_connections:
            del self.user_connections[user_id]
        logger.info(f"WebSocket bağlantısı kapatıldı: {client_id}")

    async def broadcast(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                try:
                    await connection.send_json(message)
                except WebSocketDisconnect:
                    await self.disconnect(connection, client_id)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except WebSocketDisconnect:
                del self.user_connections[user_id]

    async def handle_websocket(self, websocket: WebSocket, client_id: str, user_id: int = None):
        try:
            await self.connect(websocket, client_id, user_id)
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    # Mesaj işleme mantığı burada
                    await self.broadcast(client_id, message)
                except json.JSONDecodeError:
                    logger.error(f"Geçersiz JSON mesajı: {data}")
        except WebSocketDisconnect:
            await self.disconnect(websocket, client_id, user_id)
        except Exception as e:
            logger.error(f"WebSocket hatası: {str(e)}")
            await self.disconnect(websocket, client_id, user_id)

websocket_manager = WebSocketManager()

async def publish_websocket_update(channel: str, data: Dict[str, Any]):
    """
    WebSocket üzerinden güncelleme yayınlar.
    
    Args:
        channel: Güncelleme kanalı (message_templates, auto_replies, groups, scheduler)
        data: Yayınlanacak veri
    """
    try:
        await websocket_manager.broadcast(channel, data)
        logger.info(f"WebSocket update published to channel {channel}")
    except Exception as e:
        logger.error(f"Error publishing WebSocket update: {str(e)}")
        raise

async def broadcast_update(data: Dict[str, Any], exclude_user: str = None):
    """
    Tüm bağlı kullanıcılara güncelleme yayınlar.
    
    Args:
        data: Yayınlanacak veri
        exclude_user: Güncellemeyi almayacak kullanıcı ID'si
    """
    try:
        await websocket_manager.broadcast(data, exclude_user)
        logger.info("Broadcast update sent to all connected users")
    except Exception as e:
        logger.error(f"Error broadcasting update: {str(e)}")
        raise 