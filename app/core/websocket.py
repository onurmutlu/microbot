"""
WebSocket işlemleri için yardımcı fonksiyonlar ve yönlendiriciler.

Bu modül, WebSocket işlemleri için kullanılan yardımcı fonksiyonları içerir.
WebSocketManager sınıfı app/services/websocket_manager.py'ye taşındı.

License: MIT
Author: MicroBot Team
Version: 1.1.0
"""

from typing import Dict, Any
import json
import logging
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

async def publish_websocket_update(channel: str, data: Dict[str, Any]):
    """
    WebSocket üzerinden güncelleme yayınlar.
    
    Args:
        channel: Güncelleme kanalı (message_templates, auto_replies, groups, scheduler)
        data: Yayınlanacak veri
    """
    try:
        # Kanal adını client_id olarak kullanarak ilgili abonelere mesaj gönder
        clients_in_channel = [
            client_id for client_id, channels in websocket_manager.user_subscriptions.items()
            if channel in channels
        ]
        
        if clients_in_channel:
            await websocket_manager.broadcast({
                "type": "update",
                "channel": channel,
                "data": data,
                "timestamp": json.dumps(data)
            }, clients_in_channel)
            
            logger.info(f"WebSocket update published to channel {channel}")
        else:
            logger.debug(f"No clients subscribed to channel {channel}")
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
        # Hariç tutulacak kullanıcıları belirle
        exclude_clients = []
        if exclude_user:
            exclude_clients = [
                client_id for client_id in websocket_manager.active_connections.keys()
                if client_id.startswith(exclude_user)
            ]
        
        # Tüm kullanıcılara mesaj gönder (hariç tutulanlar dışında)
        all_clients = [
            client_id for client_id in websocket_manager.active_connections.keys()
            if client_id not in exclude_clients
        ]
        
        if all_clients:
            await websocket_manager.broadcast(data, all_clients)
            logger.info("Broadcast update sent to all connected users")
        else:
            logger.debug("No active clients to broadcast to")
    except Exception as e:
        logger.error(f"Error broadcasting update: {str(e)}")
        raise 