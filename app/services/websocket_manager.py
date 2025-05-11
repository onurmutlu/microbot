"""
WebSocket bağlantılarını yöneten servis modülü.

Bu modül, WebSocket bağlantılarını yönetmek, ping kontrollerini sağlamak ve 
mesaj gönderimini güvenli şekilde yapmak için gereken sınıfları içerir.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

from fastapi import WebSocket, WebSocketDisconnect, Depends, status
from typing import Dict, List, Set, Optional, Any, Callable
import json
import logging
from datetime import datetime
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import uuid

# Hata raporlama sistemini import et
from app.services.error_reporter import (
    report_websocket_error, ErrorSeverity, 
    ErrorCategory, error_reporter
)

# Yeniden bağlanma yöneticisini import et
from app.services.reconnect_manager import (
    reconnect_manager, ReconnectStrategy
)

logger = logging.getLogger(__name__)

class ConnectionStore:
    """WebSocket bağlantılarını saklayan sınıf"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}  # user_id -> [connection_ids]
        self.connection_user: Dict[str, str] = {}  # connection_id -> user_id
        self.user_subscriptions: Dict[str, List[str]] = {}  # connection_id -> [channels]
    
    def is_connected(self, connection_id: str) -> bool:
        """Bağlantının aktif olup olmadığını kontrol eder"""
        return connection_id in self.active_connections
    
    def add_connection(self, connection_id: str, websocket: WebSocket, user_id: Optional[str] = None):
        """Bağlantı ekler"""
        self.active_connections[connection_id] = websocket
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)
            self.connection_user[connection_id] = user_id
    
    def remove_connection(self, connection_id: str):
        """Bağlantıyı kaldırır"""
        # Kullanıcı bağlantılarından temizle
        if connection_id in self.connection_user:
            user_id = self.connection_user[connection_id]
            if user_id in self.user_connections:
                if connection_id in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(connection_id)
                # Kullanıcının bağlantısı kalmadıysa, kaydı temizle
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            del self.connection_user[connection_id]
        
        # Abonelikleri temizle
        if connection_id in self.user_subscriptions:
            del self.user_subscriptions[connection_id]
        
        # Aktif bağlantılardan kaldır
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
    
    def get_connections_for_user(self, user_id: str) -> List[str]:
        """Bir kullanıcının tüm bağlantılarını döndürür"""
        return self.user_connections.get(user_id, [])
    
    def get_subscribed_connections(self, channel: str) -> List[str]:
        """Belirli bir kanala abone olan bağlantıları döndürür"""
        return [
            conn_id for conn_id, channels in self.user_subscriptions.items()
            if channel in channels and conn_id in self.active_connections
        ]
    
    def get_all_connections(self) -> List[str]:
        """Tüm bağlantıları döndürür"""
        return list(self.active_connections.keys())
    
    def get_user_for_connection(self, connection_id: str) -> Optional[str]:
        """Bir bağlantıdan kullanıcı ID'sini döndürür"""
        return self.connection_user.get(connection_id)
    
    def get_websocket(self, connection_id: str) -> Optional[WebSocket]:
        """Bir bağlantının WebSocket nesnesini döndürür"""
        return self.active_connections.get(connection_id)
    
    def add_subscription(self, connection_id: str, channel: str) -> bool:
        """Bir bağlantıyı belirli bir kanala abone eder"""
        if connection_id in self.active_connections:
            if connection_id not in self.user_subscriptions:
                self.user_subscriptions[connection_id] = []
            if channel not in self.user_subscriptions[connection_id]:
                self.user_subscriptions[connection_id].append(channel)
                return True
        return False
    
    def remove_subscription(self, connection_id: str, channel: str) -> bool:
        """Bir bağlantının belirli bir kanala aboneliğini kaldırır"""
        if connection_id in self.user_subscriptions:
            if channel in self.user_subscriptions[connection_id]:
                self.user_subscriptions[connection_id].remove(channel)
                return True
        return False
    
    def get_subscriptions(self, connection_id: str) -> List[str]:
        """Bir bağlantının tüm aboneliklerini döndürür"""
        return self.user_subscriptions.get(connection_id, [])

class WebSocketManager:
    def __init__(self):
        """WebSocket bağlantılarını yöneten sınıf"""
        self.connection_store = ConnectionStore()
        self.cleanup_task = None
        logger.info("WebSocket Manager başlatıldı (cleanup görevi daha sonra başlatılacak)")
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: Optional[str] = None):
        """Yeni bir WebSocket bağlantısı ekler"""
        await websocket.accept()
        self.connection_store.add_connection(connection_id, websocket, user_id)
        logger.info(f"WebSocket bağlantısı kuruldu: {connection_id}, user_id: {user_id}")
    
    def disconnect(self, connection_id: str):
        """Bir WebSocket bağlantısını kaldırır"""
        self.connection_store.remove_connection(connection_id)
        logger.info(f"WebSocket bağlantısı kapatıldı: {connection_id}")
    
    async def send_personal_message(self, message: str, connection_id: str):
        """Belirli bir bağlantıya mesaj gönderir"""
        websocket = self.connection_store.get_websocket(connection_id)
        if websocket:
            try:
                await websocket.send_text(message)
                return True
            except Exception as e:
                logger.error(f"Mesaj gönderilemedi ({connection_id}): {str(e)}")
                self.disconnect(connection_id)
                return False
        return False
    
    async def broadcast(self, message: Dict[str, Any], connection_ids: Optional[List[str]] = None):
        """Tüm veya belirli bağlantılara mesaj gönderir"""
        if not connection_ids:
            connection_ids = self.connection_store.get_all_connections()
        
        send_tasks = []
        for connection_id in connection_ids:
            if self.connection_store.is_connected(connection_id):
                send_tasks.append(
                    self.send_personal_message(
                        json.dumps(message),
                        connection_id
                    )
                )
        
        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            success_count = 0
            for result in results:
                if result is True:
                    success_count += 1
            return success_count
        return 0
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Belirli bir kullanıcının tüm bağlantılarına mesaj gönderir"""
        connection_ids = self.connection_store.get_connections_for_user(user_id)
        return await self.broadcast(message, connection_ids)
    
    async def subscribe(self, connection_id: str, channel: str):
        """Bir bağlantıyı belirli bir kanala abone eder"""
        success = self.connection_store.add_subscription(connection_id, channel)
        if success:
            await self.send_personal_message(
                json.dumps({
                    "type": "subscription",
                    "status": "subscribed",
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                }),
                connection_id
            )
        return success
    
    async def unsubscribe(self, connection_id: str, channel: str):
        """Bir bağlantının belirli bir kanala aboneliğini kaldırır"""
        success = self.connection_store.remove_subscription(connection_id, channel)
        if success and self.connection_store.is_connected(connection_id):
            await self.send_personal_message(
                json.dumps({
                    "type": "subscription",
                    "status": "unsubscribed",
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                }),
                connection_id
            )
        return success
    
    async def publish_to_channel(self, channel: str, message: Dict[str, Any]):
        """Belirli bir kanala abone olan tüm bağlantılara mesaj gönderir"""
        subscribers = self.connection_store.get_subscribed_connections(channel)
        
        # Kanal bilgisini mesaja ekle
        if isinstance(message, dict):
            message["channel"] = channel
        
        if subscribers:
            return await self.broadcast(message, subscribers)
        return 0
    
    async def publish_to_topic(self, topic: str, message: Dict[str, Any]):
        """Belirli bir topice mesaj gönderir (publish_to_channel ile aynı)"""
        return await self.publish_to_channel(topic, message)
    
    def start_cleanup_task(self):
        """Düzenli aralıklarla temizlik yapan görevi başlatır"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_routine())
            logger.info("WebSocket temizlik görevi başlatıldı")
    
    def stop_cleanup_task(self):
        """Temizlik görevini durdurur"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            logger.info("WebSocket temizlik görevi durduruldu")
    
    async def _cleanup_routine(self):
        """Bozuk bağlantıları temizleme rutini"""
        try:
            while True:
                try:
                    # Her 5 dakikada bir temizlik yap
                    await asyncio.sleep(300)
                    
                    # Aktif bağlantıları kontrol et
                    dead_connections = []
                    for conn_id in self.connection_store.get_all_connections():
                        websocket = self.connection_store.get_websocket(conn_id)
                        if websocket:
                            try:
                                # Ping mesajı gönder
                                await websocket.send_text(json.dumps({
                                    "type": "ping", 
                                    "timestamp": datetime.now().isoformat()
                                }))
                            except Exception:
                                dead_connections.append(conn_id)
                    
                    # Ölü bağlantıları temizle
                    for conn_id in dead_connections:
                        self.disconnect(conn_id)
                    
                    if dead_connections:
                        logger.info(f"{len(dead_connections)} adet ölü WebSocket bağlantısı temizlendi")
                        
                except asyncio.CancelledError:
                    # Görev iptal edildi
                    raise
                except Exception as e:
                    logger.error(f"WebSocket temizleme hatası: {str(e)}")
                    await asyncio.sleep(60)  # Hata sonrası kısa bir süre bekle
        except asyncio.CancelledError:
            logger.info("WebSocket temizleme görevi iptal edildi")
    
    def get_stats(self) -> Dict[str, Any]:
        """WebSocket istatistiklerini döndürür"""
        return {
            "active_connections": len(self.connection_store.active_connections),
            "users_connected": len(self.connection_store.user_connections),
            "subscriptions": sum(len(subs) for subs in self.connection_store.user_subscriptions.values()),
            "timestamp": datetime.now().isoformat()
        }
    
    async def handle_websocket(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None):
        """WebSocket bağlantısını yönetir ve mesaj döngüsünü işler"""
        try:
            # Bağlantıyı kabul et
            await self.connect(websocket, client_id, user_id)
            
            # Hoş geldin mesajı gönder
            await self.send_personal_message(
                json.dumps({
                    "type": "connection",
                    "message": "Bağlantı başarıyla kuruldu",
                    "client_id": client_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }),
                client_id
            )
            
            # Mesaj döngüsü
            while True:
                try:
                    # Mesaj al
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Mesaj işleme
                    message_type = message.get("type", "")
                    
                    # Mesaj türüne göre işlem yap
                    if message_type == "ping":
                        # Ping yanıtı gönder
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                    elif message_type == "subscribe":
                        # Kanal aboneliği
                        channel = message.get("channel")
                        if channel:
                            await self.subscribe(client_id, channel)
                            await websocket.send_json({
                                "type": "subscription",
                                "status": "subscribed",
                                "channel": channel
                            })
                            
                    elif message_type == "unsubscribe":
                        # Kanal aboneliğini kaldır
                        channel = message.get("channel")
                        if channel:
                            await self.unsubscribe(client_id, channel)
                            await websocket.send_json({
                                "type": "subscription",
                                "status": "unsubscribed",
                                "channel": channel
                            })
                            
                    elif message_type == "broadcast":
                        # Yayın mesajı
                        content = message.get("content")
                        if content:
                            # Mesajı yayınla
                            await self.broadcast(content)
                    
                    elif message_type == "message":
                        # Kullanıcı mesajı
                        if user_id:
                            content = message.get("content", "")
                            target = message.get("target")
                            
                            # Hedef belirtilmişse, belirli bir kişiye gönder
                            if target:
                                send_count = await self.broadcast_to_user(target, {
                                    "type": "direct_message",
                                    "from": user_id,
                                    "content": content,
                                    "message_id": str(uuid.uuid4()),
                                    "timestamp": datetime.now().isoformat()
                                })
                                
                                await websocket.send_json({
                                    "type": "message_status",
                                    "message_id": str(uuid.uuid4()),
                                    "target": target,
                                    "delivered": send_count > 0,
                                    "timestamp": datetime.now().isoformat()
                                })
                            else:
                                # Yanıt gönder
                                await websocket.send_json({
                                    "type": "message_received",
                                    "message_id": str(uuid.uuid4()),
                                    "timestamp": datetime.now().isoformat()
                                })
                    
                except json.JSONDecodeError:
                    # JSON hatası durumunda uyarı gönder
                    await websocket.send_json({
                        "type": "error",
                        "message": "Geçersiz JSON formatı"
                    })
                
                except Exception as e:
                    # Diğer hata durumları
                    logger.error(f"WebSocket mesaj işleme hatası: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Sunucu hatası"
                    })
        
        except WebSocketDisconnect:
            # Bağlantı koptuğunda
            self.disconnect(client_id)
        
        except Exception as e:
            # Diğer hatalar
            logger.error(f"WebSocket bağlantı hatası: {str(e)}")
            self.disconnect(client_id)

# WebSocket manager singleton instance'ı
websocket_manager = WebSocketManager()