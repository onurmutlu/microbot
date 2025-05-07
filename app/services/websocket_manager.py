"""
WebSocket bağlantılarını yöneten servis modülü.

Bu modül, WebSocket bağlantılarını yönetmek, ping kontrollerini sağlamak ve 
mesaj gönderimini güvenli şekilde yapmak için gereken sınıfları içerir.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any, Callable
import json
import logging
from datetime import datetime
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

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
    """Bağlantı bilgilerini saklayan yardımcı sınıf"""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_times: Dict[str, datetime] = {}
        self.reconnect_attempts: Dict[str, int] = {}
        self.last_ping_time: Dict[str, datetime] = {}
        self.user_subscriptions: Dict[str, List[str]] = {}

    def add_connection(self, client_id: str, websocket: WebSocket):
        self.active_connections[client_id] = websocket
        self.connection_times[client_id] = datetime.now()
        self.last_ping_time[client_id] = datetime.now()
        if client_id not in self.reconnect_attempts:
            self.reconnect_attempts[client_id] = 0
        if client_id not in self.user_subscriptions:
            self.user_subscriptions[client_id] = []
            
    def remove_connection(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_times:
            del self.connection_times[client_id]
        if client_id in self.last_ping_time:
            del self.last_ping_time[client_id]
            
    def get_connection(self, client_id: str) -> Optional[WebSocket]:
        return self.active_connections.get(client_id)
        
    def get_all_connections(self) -> Dict[str, WebSocket]:
        return self.active_connections.copy()
        
    def is_connected(self, client_id: str) -> bool:
        return client_id in self.active_connections
        
    def get_inactive_clients(self, timeout_seconds: int) -> List[str]:
        current_time = datetime.now()
        return [
            client_id for client_id, last_time in self.last_ping_time.items()
            if (current_time - last_time).total_seconds() > timeout_seconds
        ]
        
    def update_ping_time(self, client_id: str):
        self.last_ping_time[client_id] = datetime.now()

class WebSocketManager:
    def __init__(self):
        """WebSocket bağlantı yöneticisi başlatma"""
        self.connection_store = ConnectionStore()
        self.ping_tasks: Dict[str, asyncio.Task] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self.broadcast_semaphore = asyncio.Semaphore(10)  # Eşzamanlı broadcast sayısını sınırla
        
        # Performans metrikleri
        self.metrics: Dict[str, List[Dict[str, Any]]] = {
            'broadcast': [],
            'send_personal': [],
            'connect': [],
            'disconnect': []
        }
        self.metrics_max_items = 100
        self.connection_timeout = 30  # saniye
        self.ping_interval = 20  # saniye
        self.max_reconnect_attempts = 5
        self.executor = ThreadPoolExecutor(max_workers=4)  # Ağır işlemler için thread havuzu
        
        # Hata düzeltmesi: asyncio loop kontrolü
        try:
            loop = asyncio.get_running_loop()
            self._cleanup_task = loop.create_task(self._cleanup_inactive_connections())
            logger.info("WebSocket Manager başlatıldı (mevcut event loop)")
        except RuntimeError:
            logger.info("WebSocket Manager başlatıldı (cleanup görevi ertelendi)")
            self._cleanup_task = None  # Ana uygulama event loop başladığında başlatılacak
        
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_queued": 0,
            "errors": 0,
            "last_cleanup": None
        }
        logger.info("WebSocket Manager başlatıldı")

    async def connect(self, websocket: WebSocket, user_id: str, client_id: str):
        """Yeni bir WebSocket bağlantısını kabul et"""
        try:
            start_time = datetime.now()
            
            # WebSocket'in durumunu kontrol et ve henüz kabul edilmemişse kabul et
            if not getattr(websocket, "_accepted", False):
                await websocket.accept()
            
            # Önceki bağlantıyı temizle
            if self.connection_store.is_connected(client_id):
                # Ping görevini iptal et
                if client_id in self.ping_tasks:
                    self.ping_tasks[client_id].cancel()
                    del self.ping_tasks[client_id]
            
            # Yeni bağlantıyı kaydet
            self.connection_store.add_connection(client_id, websocket)
            self.connection_store.reconnect_attempts[client_id] = 0  # Yeni bağlantıda sayacı sıfırla
            
            # Ping döngüsünü başlat
            self.ping_tasks[client_id] = asyncio.create_task(self._ping_loop(client_id))
            
            # Bağlantı başarılı mesajı gönder
            await websocket.send_json({
                "type": "connection",
                "status": "connected",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Yeniden bağlanma yöneticisine bilgi ver
            reconnect_manager.connection_succeeded(client_id)
            
            # Metrik kaydı
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.stats["active_connections"] = len(self.connection_store.active_connections)
            self.stats["total_connections"] += 1
            
            self._record_metric('connect', {
                'client_id': client_id,
                'duration_ms': duration
            })
            
            logger.info(f"Yeni WebSocket bağlantısı: {client_id}")
        except Exception as e:
            # Hata raporlama 
            report_websocket_error(
                error=e,
                source="WebSocketManager.connect",
                context={"client_id": client_id, "user_id": user_id}
            )
            logger.error(f"WebSocket bağlantı hatası: {str(e)}")
            raise

    async def _ping_loop(self, client_id: str):
        """Bağlantıyı canlı tutmak için düzenli ping gönderir"""
        try:
            while self.connection_store.is_connected(client_id):
                try:
                    await asyncio.sleep(self.ping_interval)
                    if not self.connection_store.is_connected(client_id):
                        break
                        
                    connection = self.connection_store.get_connection(client_id)
                    # WebSocket zaten kapalı mı kontrolü
                    if hasattr(connection, "client_state") and connection.client_state == "disconnected":
                        logger.debug(f"Bağlantı zaten kapalı, ping döngüsü durduruluyor: {client_id}")
                        break
                    
                    try:
                        # Ping gönder
                        await connection.send_json({
                            "type": "ping",
                            "timestamp": datetime.now().isoformat()
                        })
                        # Başarılı ping kaydı
                        self.connection_store.update_ping_time(client_id)
                        logger.debug(f"Ping gönderildi: {client_id}")
                    except RuntimeError as e:
                        # Bağlantı zaten kapatılmış olabilir
                        if "websocket.send" in str(e) and "websocket.close" in str(e):
                            logger.warning(f"Ping gönderilemiyor, bağlantı kapanmış: {client_id}")
                            await self.handle_connection_error(client_id)
                            break
                        else:
                            raise
                except asyncio.CancelledError:
                    logger.debug(f"Ping döngüsü iptal edildi: {client_id}")
                    break
                except Exception as e:
                    logger.error(f"Ping hatası: {str(e)}")
                    await self.handle_connection_error(client_id)
                    break
        except asyncio.CancelledError:
            logger.debug(f"Ping döngüsü iptal edildi: {client_id}")
        except Exception as e:
            logger.error(f"Ping döngüsü hatası: {str(e)}")

    async def disconnect(self, client_id: str):
        """WebSocket bağlantısını kapat"""
        start_time = datetime.now()
        try:
            # Ping döngüsünü durdur
            if client_id in self.ping_tasks:
                try:
                    self.ping_tasks[client_id].cancel()
                except Exception as e:
                    logger.error(f"Ping görevini iptal etme hatası: {str(e)}")
                finally:
                    if client_id in self.ping_tasks:
                        del self.ping_tasks[client_id]
            
            # WebSocket bağlantısını kapat
            if self.connection_store.is_connected(client_id):
                try:
                    connection = self.connection_store.get_connection(client_id)
                    # Bağlantı zaten kapalı mı kontrol et
                    if hasattr(connection, "client_state") and connection.client_state == "disconnected":
                        logger.debug(f"Bağlantı zaten kapalı: {client_id}")
                    else:
                        await connection.close()
                except Exception as e:
                    logger.error(f"WebSocket kapatma hatası: {str(e)}")
                finally:
                    # Bağlantı kaynakları temizleme
                    self.connection_store.remove_connection(client_id)
            
            # Metrik kaydı
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.stats["active_connections"] = len(self.connection_store.active_connections)
            
            self._record_metric('disconnect', {
                'client_id': client_id,
                'duration_ms': duration
            })
            
            logger.info(f"WebSocket bağlantısı kapatıldı: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket bağlantı kapatma hatası: {str(e)}")

    async def send_personal_message(self, message: str, client_id: str):
        """Belirli bir kullanıcıya mesaj gönder"""
        start_time = datetime.now()
        try:
            if self.connection_store.is_connected(client_id):
                connection = self.connection_store.get_connection(client_id)
                # Bağlantı durumunu kontrol et
                if hasattr(connection, "client_state") and connection.client_state == "disconnected":
                    logger.warning(f"Bağlantı kapalı, mesaj gönderilemiyor: {client_id}")
                    return
                    
                await connection.send_text(message)
                self.stats["messages_sent"] += 1
                
                # Metrik kaydı
                duration = (datetime.now() - start_time).total_seconds() * 1000
                self._record_metric('send_personal', {
                    'client_id': client_id,
                    'duration_ms': duration,
                    'success': True
                })
        except Exception as e:
            # Metrik kaydı
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.stats["errors"] += 1
            
            self._record_metric('send_personal', {
                'client_id': client_id,
                'duration_ms': duration,
                'success': False,
                'error': str(e)
            })
            
            logger.error(f"Kişisel mesaj gönderme hatası: {str(e)}")
            await self.handle_connection_error(client_id)

    async def broadcast(self, message: dict, user_ids: Optional[List[str]] = None):
        """Tüm bağlı kullanıcılara mesaj gönder - Optimize edilmiş"""
        async with self.broadcast_semaphore:  # Eşzamanlı broadcast sayısını sınırla
            start_time = datetime.now()
            try:
                success_count = 0
                error_count = 0
                message_json = json.dumps(message)
                
                # Bağlantıları kopyala (yerel erişim hızlandırma)
                connections = self.connection_store.get_all_connections()
                client_ids = list(connections.keys())
                
                # Hedef filtreleme
                if user_ids is not None:
                    client_ids = [cid for cid in client_ids if cid in user_ids]
                
                # Performans için toplu gönderi
                if client_ids:
                    tasks = []
                    for client_id in client_ids:
                        connection = connections.get(client_id)
                        if connection:
                            if hasattr(connection, "client_state") and connection.client_state == "disconnected":
                                continue
                                
                            # Asenkron gönderi görevlerini oluştur
                            tasks.append(self._send_message_safe(connection, message_json, client_id))
                    
                    # Tüm görevleri çalıştır
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Sonuçları işle
                        for result in results:
                            if isinstance(result, Exception):
                                error_count += 1
                                # Hata raporlama 
                                report_websocket_error(
                                    error=result,
                                    source="WebSocketManager.broadcast.gather",
                                    severity=ErrorSeverity.WARNING,
                                    context={"message_type": message.get("type", "unknown")}
                                )
                            elif isinstance(result, bool):
                                if result:
                                    success_count += 1
                                else:
                                    error_count += 1
                
                # Metrik kaydı
                duration = (datetime.now() - start_time).total_seconds() * 1000
                self.stats["messages_sent"] += success_count
                self.stats["errors"] += error_count
                
                self._record_metric('broadcast', {
                    'success_count': success_count,
                    'error_count': error_count,
                    'duration_ms': duration,
                    'clients_count': len(client_ids)
                })
                
                logger.debug(f"Broadcast tamamlandı: {success_count} başarılı, {error_count} hata")
            except Exception as e:
                # Hata raporlama
                report_websocket_error(
                    error=e,
                    source="WebSocketManager.broadcast",
                    context={"message": str(message)[:200]}
                )
                logger.error(f"Broadcast hatası: {str(e)}")
                self.stats["errors"] += 1

    async def _send_message_safe(self, connection: WebSocket, message: str, client_id: str) -> bool:
        """Güvenli mesaj gönderme yardımcı fonksiyonu"""
        try:
            await connection.send_text(message)
            return True
        except Exception as e:
            logger.error(f"Mesaj gönderme hatası ({client_id}): {str(e)}")
            asyncio.create_task(self.handle_connection_error(client_id))
            return False

    async def handle_connection_error(self, client_id: str):
        """Bağlantı hatasını işle"""
        try:
            logger.warning(f"Bağlantı hatası işleniyor: {client_id}")
            
            # Bağlantı sorunlu olabilir, kapatmaya çalış
            if self.connection_store.is_connected(client_id):
                connection = self.connection_store.get_connection(client_id)
                try:
                    if hasattr(connection, "client_state") and connection.client_state != "disconnected":
                        await connection.close(code=1006, reason="Bağlantı hatası")
                except Exception as e:
                    # Hata raporlama
                    report_websocket_error(
                        error=e,
                        source="WebSocketManager.handle_connection_error",
                        severity=ErrorSeverity.WARNING,
                        context={"client_id": client_id}
                    )
                    logger.error(f"Bağlantı kapatma hatası: {str(e)}")
                
                # Kaynakları temizle
                self.connection_store.remove_connection(client_id)
                if client_id in self.ping_tasks:
                    self.ping_tasks[client_id].cancel()
                    del self.ping_tasks[client_id]
                    
                # Yeniden bağlantı yöneticisine bildir
                reconnect_manager.connection_failed(client_id, reason="connection_error")
                
                logger.info(f"Bağlantı hatası nedeniyle kapatıldı: {client_id}")
            
        except Exception as e:
            # Hata raporlama
            report_websocket_error(
                error=e,
                source="WebSocketManager.handle_connection_error",
                context={"client_id": client_id}
            )
            logger.error(f"Bağlantı hatası işleme hatası: {str(e)}")

    async def _cleanup_inactive_connections(self) -> None:
        """Aktif olmayan bağlantıları temizler - Optimize edilmiş"""
        try:
            while True:
                try:
                    # Zaman aşımına uğramış bağlantıları al (thread havuzunda çalışabilir)
                    inactive_clients = self.connection_store.get_inactive_clients(self.connection_timeout)
                    
                    for client_id in inactive_clients:
                        logger.info(f"Zaman aşımı nedeniyle bağlantı kapatılıyor: {client_id}")
                        await self.disconnect(client_id)
                    
                    if inactive_clients:
                        self.stats["last_cleanup"] = datetime.now().isoformat()
                    
                    await asyncio.sleep(60)  # Her dakika kontrol et
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Bağlantı temizleme hatası: {str(e)}")
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Temizlik görevi iptal edildi")
        except Exception as e:
            logger.error(f"Temizlik görevi hatası: {str(e)}")

    def start_cleanup_task(self) -> None:
        """Temizlik görevini başlatır"""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())
                logger.info("Temizlik görevi başlatıldı")
            except RuntimeError:
                logger.warning("Event loop çalışmıyor, temizlik görevi ertelendi")
        else:
            logger.debug("Temizlik görevi zaten çalışıyor")
        return self._cleanup_task

    def stop_cleanup_task(self) -> None:
        """Temizlik görevini durdurur"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Temizlik görevi iptal edildi")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Bağlantı istatistiklerini döndürür - Genişletilmiş"""
        connections = self.connection_store.get_all_connections()
        
        # Reconnect istatistiklerini ekle
        reconnect_stats = reconnect_manager.get_stats()
        
        return {
            "active_connections": len(connections),
            "connections_by_client": {
                client_id: {
                    "connection_time": self.connection_store.connection_times.get(client_id, datetime.now()).isoformat(),
                    "subscriptions": self.connection_store.user_subscriptions.get(client_id, []),
                    "reconnect_attempts": self.connection_store.reconnect_attempts.get(client_id, 0),
                    "last_ping": self.connection_store.last_ping_time.get(client_id, datetime.now()).isoformat()
                }
                for client_id in connections.keys()
            },
            "metrics": self._get_metrics_summary(),
            "stats": self.stats,
            "reconnect_stats": reconnect_stats
        }
        
    def _record_metric(self, metric_type: str, data: Dict[str, Any]) -> None:
        """Performans metriği kaydeder"""
        if metric_type in self.metrics:
            self.metrics[metric_type].append({
                "timestamp": datetime.now().isoformat(),
                **data
            })
            
            # Maksimum öğe sayısını aşmamak için eski kayıtları sil
            if len(self.metrics[metric_type]) > self.metrics_max_items:
                self.metrics[metric_type] = self.metrics[metric_type][-self.metrics_max_items:]
                
    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Metrik özetini döndürür - Genişletilmiş"""
        result = {}
        for metric_type, data in self.metrics.items():
            if data:
                # Son 5 metriği göster
                recent_data = data[-5:]
                
                # İstatistik hesaplama
                duration_values = [item.get("duration_ms", 0) for item in data if "duration_ms" in item]
                
                result[metric_type] = {
                    "count": len(data),
                    "recent": recent_data
                }
                
                # Ortalama süre hesapla
                if duration_values:
                    result[metric_type].update({
                        "avg_duration_ms": sum(duration_values) / len(duration_values),
                        "min_duration_ms": min(duration_values) if duration_values else 0,
                        "max_duration_ms": max(duration_values) if duration_values else 0
                    })
                    
        return result

    async def subscribe(self, client_id: str, channel: str):
        """Kullanıcıyı bir kanala abone et"""
        try:
            if not self.connection_store.is_connected(client_id):
                logger.warning(f"Bağlantı bulunamadı, abone olunamıyor: {client_id}")
                return False
                
            if channel not in self.connection_store.user_subscriptions.get(client_id, []):
                if client_id not in self.connection_store.user_subscriptions:
                    self.connection_store.user_subscriptions[client_id] = []
                self.connection_store.user_subscriptions[client_id].append(channel)
                
                # Abonelik başarılı mesajı gönder
                await self.send_personal_message(json.dumps({
                    "type": "subscription",
                    "status": "subscribed",
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                }), client_id)
                logger.info(f"Kullanıcı {client_id} kanala abone oldu: {channel}")
                return True
            return False
        except Exception as e:
            logger.error(f"Abonelik hatası: {str(e)}")
            return False

    async def unsubscribe(self, client_id: str, channel: str):
        """Kullanıcının bir kanala olan aboneliğini kaldır"""
        try:
            subscriptions = self.connection_store.user_subscriptions.get(client_id, [])
            if channel in subscriptions:
                self.connection_store.user_subscriptions[client_id].remove(channel)
                
                # Abonelik iptali mesajı gönder (bağlantı aktifse)
                if self.connection_store.is_connected(client_id):
                    await self.send_personal_message(json.dumps({
                        "type": "subscription",
                        "status": "unsubscribed",
                        "channel": channel,
                        "timestamp": datetime.now().isoformat()
                    }), client_id)
                
                logger.info(f"Kullanıcı {client_id} kanaldan ayrıldı: {channel}")
                return True
            else:
                logger.warning(f"Abonelik bulunamadı: {client_id} -> {channel}")
                return False
        except Exception as e:
            logger.error(f"Abonelik kaldırma hatası: {str(e)}")
            return False

    async def reconnect(self, client_id: str, websocket: WebSocket):
        """Bağlantıyı yeniden kur"""
        try:
            # Yeniden bağlanma kontrolü
            if not reconnect_manager.should_reconnect(client_id):
                logger.warning(f"Maksimum yeniden bağlanma denemesi aşıldı: {client_id}")
                return False
                
            # Eski bağlantıyı temizle
            await self.disconnect(client_id)
            
            # Yeniden bağlanma isteği
            if not getattr(websocket, "_accepted", False):
                await websocket.accept()
                
            # Yeni bağlantıyı kaydet
            self.connection_store.add_connection(client_id, websocket)
            
            # Ping döngüsünü başlat
            self.ping_tasks[client_id] = asyncio.create_task(self._ping_loop(client_id))
            
            # Bağlantı durumunu bildir
            await websocket.send_json({
                "type": "connection",
                "status": "reconnected",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Yeniden bağlanma yöneticisine bilgi ver
            reconnect_manager.connection_succeeded(client_id)
            
            logger.info(f"WebSocket yeniden bağlandı: {client_id}")
            return True
        except Exception as e:
            # Hata raporlama
            report_websocket_error(
                error=e,
                source="WebSocketManager.reconnect",
                context={"client_id": client_id}
            )
            logger.error(f"WebSocket yeniden bağlanma hatası: {str(e)}")
            
            # Yeniden bağlanma yöneticisine bilgi ver
            reconnect_manager.connection_failed(client_id, reason=str(e))
            return False

# Global WebSocket yöneticisi örneği
websocket_manager = WebSocketManager()