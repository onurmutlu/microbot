"""
WebSocket hizmetleri için yönlendirici modül.

Bu modül, WebSocket hizmetleri için bir proxy sağlar ve asıl işlemleri
app/services/websocket_manager.py'deki WebSocketManager sınıfına yönlendirir.

License: MIT
Author: MicroBot Team
Version: 1.1.0
"""

from fastapi import WebSocket
from typing import Dict, List, Any, Optional
import logging
from app.services.websocket_manager import websocket_manager
import json
from datetime import datetime

logger = logging.getLogger(__name__)

async def connect(websocket: WebSocket, user_id: str, client_id: str):
    """WebSocket bağlantısını başlatır"""
    await websocket_manager.connect(websocket, user_id, client_id)

async def disconnect(user_id: str):
    """WebSocket bağlantısını kapatır"""
    await websocket_manager.disconnect(user_id)

async def send_personal_message(message: Dict[str, Any], client_id: str):
    """Belirli bir kullanıcıya mesaj gönderir"""
    message_str = json.dumps(message)
    await websocket_manager.send_personal_message(message_str, client_id)

async def broadcast(message: Dict[str, Any], user_ids: Optional[List[str]] = None):
    """Tüm bağlı kullanıcılara mesaj gönderir"""
    await websocket_manager.broadcast(message, user_ids)

async def subscribe_to_channel(client_id: str, channel: str):
    """Kullanıcıyı bir kanala abone eder"""
    await websocket_manager.subscribe(client_id, channel)

async def unsubscribe_from_channel(client_id: str, channel: str):
    """Kullanıcının bir kanala aboneliğini kaldırır"""
    await websocket_manager.unsubscribe(client_id, channel)

def get_connection_stats():
    """Bağlantı istatistiklerini döndürür"""
    return websocket_manager.get_connection_stats()

async def publish_update(channel: str, data: Dict[str, Any]):
    """Belirli bir kanala mesaj yayınlar"""
    clients_in_channel = [
        client_id for client_id, channels in websocket_manager.user_subscriptions.items()
        if channel in channels
    ]
    
    if not clients_in_channel:
        logger.warning(f"No clients subscribed to channel: {channel}")
        return 0
        
    await websocket_manager.broadcast({
        "type": "update",
        "channel": channel,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }, clients_in_channel)
    
    return len(clients_in_channel) 