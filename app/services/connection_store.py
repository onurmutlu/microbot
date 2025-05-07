import asyncio
import logging
import time
from typing import Dict, List, Set, Optional, Callable, Any, Awaitable
from fastapi import WebSocket
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)

class ConnectionStats(BaseModel):
    """WebSocket bağlantı istatistikleri."""
    total_connections: int = 0
    active_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    failed_messages: int = 0
    connection_errors: int = 0
    avg_message_size: float = 0
    peak_connections: int = 0
    last_updated: float = 0

class ConnectionStore:
    """
    WebSocket bağlantılarını yöneten depolama sınıfı.
    Performans optimizasyonu için bağlantıları gruplar ve etkin bir şekilde yönetir.
    """
    def __init__(self, max_concurrent_broadcasts: int = 10):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.user_connections: Dict[str, Set[str]] = {}
        self.connection_timestamps: Dict[str, float] = {}
        self.broadcast_semaphore = asyncio.Semaphore(max_concurrent_broadcasts)
        self.stats = ConnectionStats()
        self.message_size_sum = 0
        self.message_count = 0
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # 60 saniye

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str) -> None:
        """Yeni bir WebSocket bağlantısı ekler."""
        # Bağlantı grupları oluştur veya güncelle
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        self.active_connections[user_id][client_id] = websocket
        
        # Kullanıcı-bağlantı ilişkisini güncelle
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        
        self.user_connections[user_id].add(client_id)
        self.connection_timestamps[client_id] = time.time()
        
        # İstatistikleri güncelle
        self.stats.total_connections += 1
        self.stats.active_connections = self._count_active_connections()
        self.stats.peak_connections = max(self.stats.peak_connections, self.stats.active_connections)
        self.stats.last_updated = time.time()
        
        await self._cleanup_if_needed()
        
        logger.info(f"Yeni bağlantı eklendi: user_id={user_id}, client_id={client_id}, "
                   f"aktif bağlantı sayısı: {self.stats.active_connections}")

    async def disconnect(self, client_id: str, user_id: str) -> None:
        """Bir WebSocket bağlantısını kaldırır."""
        if user_id in self.active_connections and client_id in self.active_connections[user_id]:
            del self.active_connections[user_id][client_id]
            
            # Kullanıcının bağlantı listesini güncelle
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(client_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Boş kullanıcı girişini temizle
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            
            # Timestamp'i temizle
            if client_id in self.connection_timestamps:
                del self.connection_timestamps[client_id]
            
            # İstatistikleri güncelle
            self.stats.active_connections = self._count_active_connections()
            self.stats.last_updated = time.time()
            
            logger.info(f"Bağlantı kaldırıldı: user_id={user_id}, client_id={client_id}, "
                       f"aktif bağlantı sayısı: {self.stats.active_connections}")

    async def send_personal_message(self, message: dict, user_id: str) -> int:
        """Belirli bir kullanıcıya ait tüm bağlantılara mesaj gönderir."""
        message_json = json.dumps(message)
        self._update_message_stats(message_json)
        
        sent_count = 0
        if user_id in self.active_connections:
            for client_id, websocket in list(self.active_connections[user_id].items()):
                try:
                    await websocket.send_text(message_json)
                    sent_count += 1
                    self.stats.messages_sent += 1
                except Exception as e:
                    logger.error(f"Kişisel mesaj gönderimi başarısız: user_id={user_id}, client_id={client_id}, hata: {str(e)}")
                    self.stats.failed_messages += 1
                    # Kapalı bağlantıyı temizle
                    await self.disconnect(client_id, user_id)
        
        self.stats.last_updated = time.time()
        return sent_count

    async def send_direct_message(self, message: dict, user_id: str, client_id: str) -> bool:
        """Belirli bir kullanıcının belirli bir client'ına mesaj gönderir."""
        if user_id in self.active_connections and client_id in self.active_connections[user_id]:
            message_json = json.dumps(message)
            self._update_message_stats(message_json)
            
            try:
                await self.active_connections[user_id][client_id].send_text(message_json)
                self.stats.messages_sent += 1
                self.stats.last_updated = time.time()
                return True
            except Exception as e:
                logger.error(f"Direkt mesaj gönderimi başarısız: user_id={user_id}, client_id={client_id}, hata: {str(e)}")
                self.stats.failed_messages += 1
                self.stats.last_updated = time.time()
                # Kapalı bağlantıyı temizle
                await self.disconnect(client_id, user_id)
        
        return False

    async def broadcast(self, message: dict) -> int:
        """Tüm bağlantılara mesaj yayınlar, eşzamanlı işlem sayısını sınırlar."""
        async with self.broadcast_semaphore:
            message_json = json.dumps(message)
            self._update_message_stats(message_json)
            
            sent_count = 0
            tasks = []
            
            # Tüm bağlantılara göndermek için toplu görevler oluştur
            for user_id, connections in list(self.active_connections.items()):
                for client_id, websocket in list(connections.items()):
                    tasks.append(self._send_to_client(message_json, websocket, user_id, client_id))
            
            # Toplu işlemleri çalıştır
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                sent_count = sum(1 for r in results if r is True)
            
            self.stats.last_updated = time.time()
            return sent_count

    async def broadcast_to_users(self, message: dict, user_ids: List[str]) -> int:
        """Belirli kullanıcılara mesaj yayınlar."""
        async with self.broadcast_semaphore:
            message_json = json.dumps(message)
            self._update_message_stats(message_json)
            
            sent_count = 0
            tasks = []
            
            for user_id in user_ids:
                if user_id in self.active_connections:
                    for client_id, websocket in list(self.active_connections[user_id].items()):
                        tasks.append(self._send_to_client(message_json, websocket, user_id, client_id))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                sent_count = sum(1 for r in results if r is True)
            
            self.stats.last_updated = time.time()
            return sent_count

    async def _send_to_client(self, message_json: str, websocket: WebSocket, user_id: str, client_id: str) -> bool:
        """Bir istemciye mesaj gönderir ve başarısızlık durumunda bağlantıyı temizler."""
        try:
            await websocket.send_text(message_json)
            self.stats.messages_sent += 1
            return True
        except Exception as e:
            logger.error(f"Broadcast mesaj gönderimi başarısız: user_id={user_id}, client_id={client_id}, hata: {str(e)}")
            self.stats.failed_messages += 1
            self.stats.connection_errors += 1
            # Kapalı bağlantıyı temizle
            await self.disconnect(client_id, user_id)
            return False

    def _update_message_stats(self, message_json: str) -> None:
        """Mesaj istatistiklerini günceller."""
        message_size = len(message_json)
        self.message_size_sum += message_size
        self.message_count += 1
        if self.message_count > 0:
            self.stats.avg_message_size = self.message_size_sum / self.message_count

    async def _cleanup_if_needed(self) -> None:
        """Belirli aralıklarla eski ve geçersiz bağlantıları temizler."""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            await self._cleanup_stale_connections()
            self._last_cleanup = current_time

    async def _cleanup_stale_connections(self) -> None:
        """Uzun süre etkin olmayan bağlantıları temizler."""
        current_time = time.time()
        stale_timeout = 3600  # 1 saat
        
        clients_to_clean = []
        for client_id, timestamp in list(self.connection_timestamps.items()):
            if current_time - timestamp > stale_timeout:
                # Kullanıcı ID'sini bul
                user_id = None
                for uid, clients in list(self.user_connections.items()):
                    if client_id in clients:
                        user_id = uid
                        break
                
                if user_id:
                    clients_to_clean.append((client_id, user_id))
        
        for client_id, user_id in clients_to_clean:
            logger.info(f"Eski bağlantı temizleniyor: user_id={user_id}, client_id={client_id}")
            await self.disconnect(client_id, user_id)

    def _count_active_connections(self) -> int:
        """Aktif bağlantı sayısını hesaplar."""
        count = 0
        for user_connections in self.active_connections.values():
            count += len(user_connections)
        return count

    def get_connection_stats(self) -> ConnectionStats:
        """Güncel bağlantı istatistiklerini döndürür."""
        self.stats.active_connections = self._count_active_connections()
        self.stats.last_updated = time.time()
        return self.stats

    def get_user_connection_count(self, user_id: str) -> int:
        """Bir kullanıcının aktif bağlantı sayısını döndürür."""
        if user_id in self.active_connections:
            return len(self.active_connections[user_id])
        return 0

# Singleton instance
connection_store = ConnectionStore() 