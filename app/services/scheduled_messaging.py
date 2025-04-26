import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from croniter import croniter

from app.models import MessageTemplate, Group, MessageLog
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

class ScheduledMessagingService:
    """Zamanlanmış mesaj gönderimi servisi."""
    
    def __init__(self, db: Session):
        self.db = db
        self.running_tasks = {}  # user_id -> task
        self.stop_flags = {}  # user_id -> bool
    
    async def start_scheduler_for_user(self, user_id: int) -> Dict[str, Any]:
        """Belirli bir kullanıcı için mesaj zamanlayıcısını başlatır."""
        # Zaten çalışıyorsa, önce durdur
        if user_id in self.running_tasks and not self.running_tasks[user_id].done():
            await self.stop_scheduler_for_user(user_id)
        
        # Stop flag'i sıfırla
        self.stop_flags[user_id] = False
        
        # Yeni task başlat
        telegram_service = TelegramService(self.db)
        task = asyncio.create_task(self._scheduler_task(user_id, telegram_service))
        self.running_tasks[user_id] = task
        
        return {
            "status": "started",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def stop_scheduler_for_user(self, user_id: int) -> Dict[str, Any]:
        """Belirli bir kullanıcı için mesaj zamanlayıcısını durdurur."""
        self.stop_flags[user_id] = True
        
        if user_id in self.running_tasks and not self.running_tasks[user_id].done():
            try:
                self.running_tasks[user_id].cancel()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
        
        return {
            "status": "stopped",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_scheduler_status(self, user_id: int) -> Dict[str, Any]:
        """Belirli bir kullanıcı için mesaj zamanlayıcısının durumunu döndürür."""
        # Aktif şablon sayısını bul
        active_templates = self.db.query(MessageTemplate).filter(
            MessageTemplate.user_id == user_id,
            MessageTemplate.is_active == True
        ).count()
        
        # Son 24 saatteki mesaj sayısını bul
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        messages_last_24h = self.db.query(MessageLog).filter(
            MessageLog.user_id == user_id,
            MessageLog.sent_at >= one_day_ago
        ).count()
        
        is_running = (
            user_id in self.running_tasks and 
            not self.running_tasks[user_id].done() and
            not self.stop_flags.get(user_id, True)
        )
        
        return {
            "is_running": is_running,
            "active_templates": active_templates,
            "messages_last_24h": messages_last_24h,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _scheduler_task(self, user_id: int, telegram_service: TelegramService) -> None:
        """Kullanıcı için mesaj zamanlama görevi."""
        try:
            while not self.stop_flags.get(user_id, False):
                await self._process_scheduled_templates(user_id, telegram_service)
                # Her 60 saniyede bir kontrol et
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info(f"Scheduler task for user {user_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in scheduler task for user {user_id}: {str(e)}")
    
    async def _process_scheduled_templates(self, user_id: int, telegram_service: TelegramService) -> None:
        """Kullanıcının zamanlanmış mesaj şablonlarını işler."""
        # Kullanıcının aktif şablonlarını al
        templates = self.db.query(MessageTemplate).filter(
            MessageTemplate.user_id == user_id,
            MessageTemplate.is_active == True
        ).all()
        
        if not templates:
            return
        
        # Kullanıcının aktif gruplarını al
        groups = self.db.query(Group).filter(
            Group.user_id == user_id,
            Group.is_active == True,
            Group.is_selected == True
        ).all()
        
        if not groups:
            return
        
        # Her şablon için kontrol et
        for template in templates:
            should_send = False
            now = datetime.utcnow()
            
            # Bu şablonla ilgili en son gönderilen mesajı bul
            last_log = self.db.query(MessageLog).filter(
                MessageLog.user_id == user_id,
                MessageLog.message_template_id == template.id
            ).order_by(MessageLog.sent_at.desc()).first()
            
            # Cron ifadesi varsa, cron planını kontrol et
            if template.cron_expression:
                try:
                    # En son gönderim zamanından (veya şimdi) sonraki adımı hesapla
                    base_time = last_log.sent_at if last_log else now - timedelta(minutes=1)
                    cron = croniter(template.cron_expression, base_time)
                    next_time = cron.get_next(datetime)
                    
                    # Bir sonraki zamanın geçip geçmediğini kontrol et
                    if next_time <= now:
                        should_send = True
                        logger.info(f"Cron expr '{template.cron_expression}' için gönderim zamanı geldi: {next_time}")
                except Exception as e:
                    logger.error(f"Cron ifadesi işlenirken hata: {template.cron_expression} - {str(e)}")
            else:
                # Basit interval_minutes kontrolü
                if last_log:
                    # Son gönderimden itibaren yeterli süre geçmiş mi?
                    time_since_last_send = now - last_log.sent_at
                    if time_since_last_send.total_seconds() >= template.interval_minutes * 60:
                        should_send = True
                else:
                    # Hiç gönderilmemiş, ilk kez gönder
                    should_send = True
            
            # Zamanı geldiyse gönder
            if should_send:
                try:
                    group_ids = [group.group_id for group in groups]
                    logger.info(f"Zamanlanmış mesaj gönderiliyor: template_id={template.id}, şablon={template.name}")
                    
                    # Mesajı gönder
                    result = await telegram_service.send_message(template.id, group_ids)
                    logger.info(f"Zamanlanmış mesaj gönderildi: başarılı={result['success_count']}, hata={result['error_count']}")
                    
                    # API sınırlamalarına takılmamak için kısa bir bekleme
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.error(f"Zamanlanmış mesaj gönderimi hatası: {str(e)}")
    
    async def stop_all_schedulers(self) -> List[Dict[str, Any]]:
        """Tüm çalışan zamanlayıcıları durdurur."""
        results = []
        for user_id in list(self.running_tasks.keys()):
            result = await self.stop_scheduler_for_user(user_id)
            results.append(result)
        return results
        
    async def validate_cron_expression(self, cron_expression: str) -> Dict[str, Any]:
        """
        Cron ifadesinin geçerliliğini kontrol eder ve sonraki çalışma zamanlarını döndürür
        """
        try:
            # Şu anki zamandan başlayarak sonraki zamanları hesapla
            now = datetime.utcnow()
            cron = croniter(cron_expression, now)
            
            # Sonraki 5 çalışma zamanını hesapla
            next_dates = []
            for _ in range(5):
                next_time = cron.get_next(datetime)
                next_dates.append(next_time.isoformat())
            
            return {
                "is_valid": True,
                "next_dates": next_dates,
                "error": None
            }
        except Exception as e:
            return {
                "is_valid": False,
                "next_dates": [],
                "error": str(e)
            }

# Singleton servis oluşturma
_instance = None

def get_scheduled_messaging_service(db: Session) -> ScheduledMessagingService:
    """
    ScheduledMessagingService için singleton instance alır
    
    Args:
        db: Veritabanı oturumu
        
    Returns:
        ScheduledMessagingService instance'ı
    """
    global _instance
    if _instance is None:
        _instance = ScheduledMessagingService(db)
    return _instance 