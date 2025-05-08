"""
Server-Sent Events (SSE) bağlantılarını yöneten modül.

Bu modül, SSE bağlantılarını yönetmek için gereken sınıf ve fonksiyonları içerir.
SSE, sunucudan istemciye gerçek zamanlı veri akışı sağlayan bir protokoldür.

License: MIT
Author: MicroBot Team
Version: 1.0.0
"""

from fastapi import WebSocket
from typing import Dict, Any, Optional, List, Set
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class SSEManager:
    """Server-Sent Events (SSE) bağlantılarını yöneten sınıf
    
    Bu sınıf, SSE bağlantılarını, mesaj kuyruklarını ve konu aboneliklerini yönetir.
    SSE ile WebSocket arasındaki temel fark, SSE'nin sadece sunucudan istemciye
    tek yönlü veri akışı sağlamasıdır.
    
    Attributes:
        active_connections: Aktif SSE bağlantılarını tutan sözlük
        connection_times: Bağlantı zamanlarını tutan sözlük
        topic_subscriptions: Konu aboneliklerini tutan sözlük
    """
    
    def __init__(self):
        """SSE Manager için gereken değişkenleri başlat"""
        self.active_connections: Dict[str, asyncio.Queue] = {}
        self.connection_times: Dict[str, datetime] = {}
        self.topic_subscriptions: Dict[str, Set[str]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self.connection_timeout = 3600  # 1 saat (saniye cinsinden)
        self.cleanup_interval = 300  # 5 dakika (saniye cinsinden)
        
        # Performans metrikleri
        self.metrics: Dict[str, List[Dict[str, Any]]] = {
            'broadcast': [],
            'send_to_client': [],
            'publish_to_topic': [],
            'connect': [],
            'disconnect': []
        }
        self.metrics_max_items = 100  # Her metrik türü için saklanacak maksimum öğe sayısı
        
        # Asenkron başlatma işlemleri uygulama başlatıldığında yapılacak
        logger.info("SSE Manager başlatıldı (cleanup görevi daha sonra başlatılacak)")
    
    async def connect(self, client_id: str, queue: asyncio.Queue) -> None:
        """Yeni bir SSE bağlantısını kaydet"""
        start_time = datetime.now()
        
        self.active_connections[client_id] = queue
        self.connection_times[client_id] = datetime.now()
        logger.info(f"SSE bağlantısı eklendi: {client_id}")
        
        # Metrik kaydı
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self._record_metric('connect', {
            'client_id': client_id,
            'duration_ms': duration
        })
    
    async def disconnect(self, client_id: str) -> None:
        """Bir SSE bağlantısını kaldır"""
        start_time = datetime.now()
        
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        if client_id in self.connection_times:
            connection_duration = (datetime.now() - self.connection_times[client_id]).total_seconds()
            del self.connection_times[client_id]
        else:
            connection_duration = 0
        
        # Tüm aboneliklerden çıkar
        unsubscribed_topics = []
        for topic, subscribers in self.topic_subscriptions.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
                unsubscribed_topics.append(topic)
        
        logger.info(f"SSE bağlantısı kaldırıldı: {client_id}")
        
        # Metrik kaydı
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self._record_metric('disconnect', {
            'client_id': client_id,
            'connection_duration_seconds': connection_duration,
            'unsubscribed_topics_count': len(unsubscribed_topics),
            'duration_ms': duration
        })
    
    async def broadcast(self, message: Dict[str, Any], exclude_client: Optional[str] = None) -> None:
        """Tüm aktif SSE bağlantılarına mesaj gönder"""
        start_time = datetime.now()
        success_count = 0
        error_count = 0
        
        # Hız için önceden JSON dönüşümü yap
        message_with_timestamp = message.copy()
        if 'timestamp' not in message_with_timestamp:
            message_with_timestamp['timestamp'] = datetime.now().isoformat()
        
        for client_id, queue in self.active_connections.items():
            if exclude_client and client_id == exclude_client:
                continue
                
            try:
                await queue.put(message_with_timestamp)
                success_count += 1
                logger.debug(f"Mesaj gönderildi (client_id: {client_id}): {message}")
            except Exception as e:
                error_count += 1
                logger.error(f"Mesaj gönderme hatası (client_id: {client_id}): {str(e)}")
        
        # Performans ölçümü
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"Broadcast tamamlandı: {success_count} başarılı, {error_count} hata, {duration:.2f}ms")
        
        # Ölçümleri kaydet
        self._record_metric('broadcast', {
            'success_count': success_count,
            'error_count': error_count,
            'duration_ms': duration
        })
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Belirli bir istemciye mesaj gönder"""
        if client_id not in self.active_connections:
            logger.warning(f"İstemci bulunamadı: {client_id}")
            return False
            
        start_time = datetime.now()
        
        try:
            # Timestamp ekle
            if 'timestamp' not in message:
                message['timestamp'] = datetime.now().isoformat()
                
            await self.active_connections[client_id].put(message)
            
            # Performans ölçümü
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(f"Mesaj gönderildi (client_id: {client_id}, süre: {duration:.2f}ms): {message}")
            
            # Ölçümleri kaydet
            self._record_metric('send_to_client', {
                'success': True,
                'client_id': client_id,
                'duration_ms': duration
            })
            
            return True
        except Exception as e:
            # Performans ölçümü
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Mesaj gönderme hatası (client_id: {client_id}, süre: {duration:.2f}ms): {str(e)}")
            
            # Ölçümleri kaydet
            self._record_metric('send_to_client', {
                'success': False,
                'client_id': client_id,
                'duration_ms': duration,
                'error': str(e)
            })
            
            return False
    
    async def subscribe(self, client_id: str, topic: str) -> bool:
        """Bir istemciyi belirli bir konuya abone et"""
        start_time = datetime.now()
        
        if client_id not in self.active_connections:
            logger.warning(f"Abone olmak için istemci bulunamadı: {client_id}")
            return False
            
        if topic not in self.topic_subscriptions:
            self.topic_subscriptions[topic] = set()
            
        self.topic_subscriptions[topic].add(client_id)
        logger.info(f"İstemci abone oldu (client_id: {client_id}, topic: {topic})")
        
        # Abonelik onayı gönder
        await self.send_to_client(client_id, {
            "type": "subscription",
            "status": "subscribed",
            "topic": topic,
            "timestamp": datetime.now().isoformat()
        })
        
        # Metrik kaydı
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self._record_metric('subscribe', {
            'client_id': client_id,
            'topic': topic,
            'duration_ms': duration
        })
        
        return True
    
    async def unsubscribe(self, client_id: str, topic: str) -> bool:
        """Bir istemcinin belirli bir konuya aboneliğini kaldır"""
        start_time = datetime.now()
        
        if topic not in self.topic_subscriptions:
            logger.warning(f"Konu bulunamadı: {topic}")
            return False
            
        if client_id not in self.topic_subscriptions[topic]:
            logger.warning(f"İstemci bu konuya abone değil (client_id: {client_id}, topic: {topic})")
            return False
            
        self.topic_subscriptions[topic].remove(client_id)
        logger.info(f"İstemci aboneliği kaldırıldı (client_id: {client_id}, topic: {topic})")
        
        # Abonelik iptali onayı gönder
        if client_id in self.active_connections:
            await self.send_to_client(client_id, {
                "type": "subscription",
                "status": "unsubscribed",
                "topic": topic,
                "timestamp": datetime.now().isoformat()
            })
        
        # Metrik kaydı
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self._record_metric('unsubscribe', {
            'client_id': client_id,
            'topic': topic,
            'duration_ms': duration
        })
            
        return True
    
    async def publish_to_topic(self, topic: str, message: Dict[str, Any]) -> int:
        """Belirli bir konuya abone olan tüm istemcilere mesaj gönder"""
        start_time = datetime.now()
        
        if topic not in self.topic_subscriptions or not self.topic_subscriptions[topic]:
            logger.warning(f"Konuya abone istemci yok: {topic}")
            return 0
            
        count = 0
        error_count = 0
        for client_id in self.topic_subscriptions[topic]:
            if client_id in self.active_connections:
                try:
                    # Mesaja topic bilgisi ekle
                    message_with_topic = message.copy()
                    message_with_topic["topic"] = topic
                    
                    await self.active_connections[client_id].put(message_with_topic)
                    count += 1
                except Exception as e:
                    error_count += 1
                    logger.error(f"Konuya mesaj gönderme hatası (client_id: {client_id}, topic: {topic}): {str(e)}")
        
        logger.info(f"Konuya mesaj gönderildi (topic: {topic}, alıcı sayısı: {count})")
        
        # Metrik kaydı
        duration = (datetime.now() - start_time).total_seconds() * 1000
        self._record_metric('publish_to_topic', {
            'topic': topic,
            'recipient_count': count,
            'error_count': error_count,
            'total_subscribers': len(self.topic_subscriptions[topic]),
            'duration_ms': duration
        })
        
        return count
    
    async def _cleanup_inactive_connections(self) -> None:
        """Belirli bir süredir aktif olmayan bağlantıları temizle"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                now = datetime.now()
                expired_clients = []
                
                for client_id, connect_time in self.connection_times.items():
                    if (now - connect_time).total_seconds() > self.connection_timeout:
                        expired_clients.append(client_id)
                
                for client_id in expired_clients:
                    logger.info(f"Zaman aşımına uğrayan bağlantı kaldırılıyor: {client_id}")
                    await self.disconnect(client_id)
                    
                if expired_clients:
                    logger.info(f"Temizlenen bağlantı sayısı: {len(expired_clients)}")
                    
            except asyncio.CancelledError:
                logger.info("Temizlik görevi iptal edildi")
                break
            except Exception as e:
                logger.error(f"Temizlik görevi hatası: {str(e)}")
                await asyncio.sleep(60)  # Hata durumunda 1 dakika bekle
    
    def start_cleanup_task(self) -> None:
        """Temizlik görevini başlat"""
        if not self._cleanup_task:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_inactive_connections())
                logger.info("SSE temizlik görevi başlatıldı")
            except RuntimeError:
                logger.warning("Event loop çalışmıyor, SSE temizlik görevi başlatılamadı")
    
    def stop_cleanup_task(self) -> None:
        """Temizlik görevini durdur"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("SSE temizlik görevi durduruldu")
            
    def get_stats(self) -> Dict[str, Any]:
        """SSE yöneticisi hakkında istatistikler döndür"""
        now = datetime.now()
        
        # Bağlantı sürelerini hesapla
        connection_durations = []
        for client_id, connect_time in self.connection_times.items():
            duration_seconds = (now - connect_time).total_seconds()
            connection_durations.append(duration_seconds)
        
        avg_connection_duration = 0
        if connection_durations:
            avg_connection_duration = sum(connection_durations) / len(connection_durations)
        
        # Konu bazlı abonelik sayıları
        topic_stats = {topic: len(subscribers) for topic, subscribers in self.topic_subscriptions.items()}
        
        # En popüler konular
        popular_topics = sorted(topic_stats.items(), key=lambda x: x[1], reverse=True)[:5] if topic_stats else []
        
        return {
            "active_connections": len(self.active_connections),
            "topics": topic_stats,
            "total_topic_subscribers": sum(len(subscribers) for subscribers in self.topic_subscriptions.values()),
            "avg_connection_duration_seconds": round(avg_connection_duration, 2),
            "popular_topics": dict(popular_topics),
            "metrics": self._get_metrics_summary()
        }
    
    def _record_metric(self, metric_type: str, data: Dict[str, Any]) -> None:
        """Performans metriği kaydet"""
        if metric_type not in self.metrics:
            self.metrics[metric_type] = []
            
        # Zamanlama bilgisini ekle
        data['recorded_at'] = datetime.now().isoformat()
        
        # Metriği listeye ekle
        self.metrics[metric_type].append(data)
        
        # Liste boyutunu kontrol et
        if len(self.metrics[metric_type]) > self.metrics_max_items:
            # En eski metriği çıkar
            self.metrics[metric_type].pop(0)
    
    def _get_metrics_summary(self) -> Dict[str, Any]:
        """Metrik özeti döndür"""
        summary = {}
        
        for metric_type, metrics in self.metrics.items():
            if not metrics:
                summary[metric_type] = {"count": 0}
                continue
                
            # Toplam sayı
            count = len(metrics)
            
            # Süre metrikleri için ortalama
            if metrics and 'duration_ms' in metrics[0]:
                durations = [m['duration_ms'] for m in metrics if 'duration_ms' in m]
                avg_duration = sum(durations) / len(durations) if durations else 0
                max_duration = max(durations) if durations else 0
                
                summary[metric_type] = {
                    "count": count,
                    "avg_duration_ms": round(avg_duration, 2),
                    "max_duration_ms": round(max_duration, 2)
                }
            else:
                summary[metric_type] = {"count": count}
        
        return summary

# Global SSE yönetici örneği singleton pattern ile
_sse_manager_instance = None

def get_sse_manager():
    """SSE Manager için singleton örneği oluşturur"""
    global _sse_manager_instance
    if _sse_manager_instance is None:
        _sse_manager_instance = SSEManager()
    return _sse_manager_instance

sse_manager = get_sse_manager() 