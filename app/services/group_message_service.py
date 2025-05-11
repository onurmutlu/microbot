import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

from app.models.message import Message
from app.models.group import Group
from app.models.message_log import MessageLog
from app.services.ai.content_optimizer import ContentOptimizer
from app.services.monitoring.prometheus_metrics import metric_service
from app.services.cache_service import cache_service
from app.config import settings

logger = logging.getLogger(__name__)

class GroupMessageService:
    """
    Telegram gruplarına mesaj gönderimi ile ilgili tüm işlemleri yöneten servis.
    AI içerik optimizasyonu ve önbellekleme özelliklerini kullanır.
    """
    
    def __init__(self, db: Session, client: TelegramClient, user_id: int):
        self.db = db
        self.client = client
        self.user_id = user_id
        self.content_optimizer = ContentOptimizer(db)
    
    async def send_message_to_group(
        self, 
        group_id: int, 
        message_text: str, 
        optimize_content: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Bir gruba akıllı mesaj gönderir. İçerik optimizasyonu yapabilir 
        ve sonuçları önbelleğe alabilir.
        
        Args:
            group_id: Hedef grup ID'si
            message_text: Gönderilecek mesaj içeriği
            optimize_content: İçerik optimizasyonu yapılsın mı
            use_cache: Önbellek kullanılsın mı
            
        Returns:
            Gönderim sonucu
        """
        try:
            # Grup varlığını kontrol et
            group = self.db.query(Group).filter(Group.telegram_id == group_id).first()
            if not group:
                return {
                    "success": False,
                    "error": "Grup bulunamadı"
                }
            
            # İçerik optimizasyonu
            optimized_message = message_text
            optimization_results = None
            
            if optimize_content and settings.CONTENT_OPTIMIZATION_ENABLED:
                # Önce önbellekten bak
                cache_key = f"optimized_message:{group_id}:{hash(message_text)}"
                
                if use_cache and settings.CACHE_ENABLED:
                    cached_result = await cache_service.get(cache_key)
                    if cached_result:
                        logger.info(f"İçerik optimizasyonu önbellekten alındı: {group_id}")
                        optimization_results = cached_result
                        if "optimized_message" in cached_result:
                            optimized_message = cached_result["optimized_message"]
                
                # Önbellekte yoksa optimize et
                if not optimization_results:
                    try:
                        optimization_results = await self.content_optimizer.optimize_message(
                            message_text, group_id
                        )
                        
                        # Sonuçları önbelleğe al
                        if use_cache and settings.CACHE_ENABLED:
                            await cache_service.set(
                                cache_key, 
                                optimization_results, 
                                expire=settings.CONTENT_ANALYSIS_CACHE_TTL
                            )
                        
                        # Optimize edilmiş mesajı kullan
                        if "optimized_message" in optimization_results:
                            optimized_message = optimization_results["optimized_message"]
                    except Exception as e:
                        logger.error(f"İçerik optimizasyonu hatası: {str(e)}")
            
            # Mesajı gönder
            try:
                # Mesaj boyutunu metrik olarak kaydet
                metric_service.observe_message_size(str(group_id), len(optimized_message))
                
                # Mesajı gönder
                sent_message = await self.client.send_message(
                    group_id, 
                    optimized_message
                )
                
                # Başarılı gönderimi kaydet
                metric_service.increment_group_message(str(group_id), "success")
                
                # MessageLog oluştur
                message_log = MessageLog(
                    telegram_id=group_id,
                    user_id=self.user_id,
                    message_content=optimized_message,
                    sent_at=datetime.utcnow(),
                    status="success",
                    has_media=False,  # Basitleştirilmiş
                    metadata={"message_id": sent_message.id} if sent_message else {}
                )
                self.db.add(message_log)
                self.db.commit()
                
                # Yanıtı hazırla
                return {
                    "success": True,
                    "message_id": sent_message.id if sent_message else None,
                    "original_message": message_text,
                    "sent_message": optimized_message,
                    "optimization_results": optimization_results,
                    "sent_at": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                # Hata durumunda
                logger.error(f"Mesaj gönderme hatası: {str(e)}")
                metric_service.increment_group_message(str(group_id), "error")
                
                # Telegram hatası olarak kaydet
                error_type = type(e).__name__
                metric_service.increment_telegram_error(error_type)
                
                # Hata logu oluştur
                message_log = MessageLog(
                    telegram_id=group_id,
                    user_id=self.user_id,
                    message_content=optimized_message,
                    sent_at=datetime.utcnow(),
                    status="error",
                    has_media=False,
                    metadata={"error": str(e), "error_type": error_type}
                )
                self.db.add(message_log)
                self.db.commit()
                
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": error_type,
                    "original_message": message_text,
                    "attempted_message": optimized_message
                }
                
        except Exception as e:
            logger.error(f"Genel mesaj gönderme hatası: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @cache_service.cached(ttl_seconds=300, key_prefix="group_stats")
    async def get_group_stats(self, group_id: int) -> Dict[str, Any]:
        """
        Bir grubun istatistiklerini getirir. Sonuç 5 dakika önbelleğe alınır.
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            Grup istatistikleri
        """
        try:
            # Veritabanı işlemi için metrik ölçümü başlat
            with metric_service.track_database_operation("query"):
                # Son 30 günlük mesajları al
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                logs = self.db.query(MessageLog).filter(
                    MessageLog.telegram_id == group_id,
                    MessageLog.sent_at >= thirty_days_ago
                ).all()
                
                # Grup bilgisini al
                group = self.db.query(Group).filter(Group.telegram_id == group_id).first()
            
            if not group:
                return {
                    "success": False,
                    "error": "Grup bulunamadı"
                }
                
            # Mesaj istatistikleri
            total_messages = len(logs)
            successful_messages = sum(1 for log in logs if log.status == 'success')
            error_messages = total_messages - successful_messages
            
            # Başarı oranı
            success_rate = (successful_messages / total_messages) * 100 if total_messages > 0 else 0
            
            # Grup aktivite analizini al
            content_analysis = await self.content_optimizer.analyze_group_content(group_id)
            
            return {
                "success": True,
                "group_id": group_id,
                "group_name": group.title if group else "Bilinmeyen Grup",
                "total_messages": total_messages,
                "successful_messages": successful_messages,
                "error_messages": error_messages,
                "success_rate": success_rate,
                "content_analysis": content_analysis,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Grup istatistikleri alma hatası: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def invalidate_group_cache(self, group_id: int) -> bool:
        """
        Bir grubun önbelleğini temizler.
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            İşlem başarılı mı
        """
        try:
            count = await cache_service.invalidate_group_cache(group_id)
            logger.info(f"Grup önbelleği temizlendi: {group_id}, silinen anahtar sayısı: {count}")
            return True
        except Exception as e:
            logger.error(f"Grup önbelleği temizleme hatası: {str(e)}")
            return False 