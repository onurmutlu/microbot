import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from croniter import croniter
from telethon.errors import FloodWaitError, ChatWriteForbiddenError

from app.models import MessageTemplate, Group, MessageLog, Schedule
from app.services.telegram_service import TelegramService
from app.services.group_analyzer import GroupAnalyzer

logger = logging.getLogger(__name__)

class ScheduledMessagingService:
    """Zamanlanmış mesaj gönderimi servisi."""
    
    def __init__(self, db: Session):
        self.db = db
        self.running_tasks = {}  # user_id -> task
        self.stop_flags = {}  # user_id -> bool
        self.cooldown_groups = {}  # group_id -> {until: datetime, reason: str, attempt: int}
    
    async def start_scheduler_for_user(self, user_id: int) -> Dict[str, Any]:
        """Belirli bir kullanıcı için mesaj zamanlayıcısını başlatır."""
        # Zaten çalışıyorsa, önce durdur
        if user_id in self.running_tasks and not self.running_tasks[user_id].done():
            await self.stop_scheduler_for_user(user_id)
        
        # Stop flag'i sıfırla
        self.stop_flags[user_id] = False
        
        # Yeni task başlat
        telegram_service = TelegramService(self.db, user_id)
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
        
        # Soğutma modundaki grup sayısını al
        now = datetime.utcnow()
        cooled_groups = sum(1 for group_id, data in self.cooldown_groups.items() 
                            if data.get('until', now) > now)
        
        is_running = (
            user_id in self.running_tasks and 
            not self.running_tasks[user_id].done() and
            not self.stop_flags.get(user_id, True)
        )
        
        return {
            "is_running": is_running,
            "active_templates": active_templates,
            "messages_last_24h": messages_last_24h,
            "cooled_groups": cooled_groups,
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
        
        # Grup aktivite analizini yap
        client = await telegram_service.get_client()
        group_analyzer = GroupAnalyzer(client)
        
        # Optimal gönderim aralıklarını hesapla
        optimal_intervals = {}
        for group in groups:
            optimal_intervals[group.telegram_id] = group_analyzer.get_optimal_interval(group.telegram_id)
        
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
                # Dinamik interval kontrolü
                if last_log:
                    # Standart interval kullan
                    time_since_last_send = now - last_log.sent_at
                    dynamic_interval = self._get_dynamic_interval(template, optimal_intervals)
                    
                    if time_since_last_send.total_seconds() >= dynamic_interval * 60:
                        should_send = True
                        logger.info(f"Dinamik interval için gönderim zamanı geldi: {dynamic_interval} dk, son gönderim: {last_log.sent_at}")
                else:
                    # Hiç gönderilmemiş, ilk kez gönder
                    should_send = True
            
            # Zamanı geldiyse gönder
            if should_send:
                try:
                    # Soğutma durumunda olmayan grupları filtrele
                    available_groups = self._filter_available_groups(groups)
                    if not available_groups:
                        logger.info("Tüm gruplar soğutma durumunda, gönderimi atla")
                        continue
                    
                    group_ids = [group.telegram_id for group in available_groups]
                    logger.info(f"Zamanlanmış mesaj gönderiliyor: template_id={template.id}, şablon={template.name}")
                    
                    # Mesajı gönder
                    result = await telegram_service.send_message(template.id, group_ids)
                    logger.info(f"Zamanlanmış mesaj gönderildi: başarılı={result['success_count']}, hata={result['error_count']}")
                    
                    # Hata durumlarını kontrol et ve grupları soğutmaya al
                    if 'results' in result:
                        for group_result in result['results']:
                            if group_result.get('status') == 'error':
                                group_id = group_result.get('group_id')
                                error_msg = group_result.get('error', '')
                                await self._handle_group_error(group_id, error_msg)
                    
                    # API sınırlamalarına takılmamak için kısa bir bekleme
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.error(f"Zamanlanmış mesaj gönderimi hatası: {str(e)}")
                    if isinstance(e, FloodWaitError):
                        # FloodWait durumunda tüm işlemi beklet
                        wait_time = e.seconds
                        logger.warning(f"FloodWait hatası! {wait_time} saniye bekleniyor")
                        await asyncio.sleep(wait_time)
    
    def _get_dynamic_interval(self, template: MessageTemplate, optimal_intervals: Dict[str, int]) -> int:
        """
        Şablon ve grup aktivitesi bazlı dinamik mesaj aralığı hesaplar
        
        Args:
            template: Mesaj şablonu
            optimal_intervals: Grup ID -> optimal dakika sözlüğü
            
        Returns:
            Dakika cinsinden dinamik interval
        """
        # Şablonun temel aralığını al
        base_interval = template.interval_minutes
        
        if not optimal_intervals:
            return base_interval
            
        # Optimal ortalamayı hesapla
        avg_interval = sum(optimal_intervals.values()) / len(optimal_intervals)
        
        # Şablon tipine göre interval ayarlaması yap
        if template.message_type == "BROADCAST":
            # Broadcast için daha çok grup aktivitesine bağlı kalarak interval ayarla
            # Ama minimum 3 dakika olsun
            return max(3, int(avg_interval))
        elif template.message_type == "DIRECT":
            # Direct mesajlar için şablonun kendi intervali daha önemli
            return base_interval
        else:
            # Diğer mesaj tipleri için iki değerin ortalamasını al
            return max(3, int((base_interval + avg_interval) / 2))
    
    def _filter_available_groups(self, groups: List[Group]) -> List[Group]:
        """
        Soğutma süresinde olmayan grupları filtreler
        
        Args:
            groups: Filtre uygulanacak gruplar
            
        Returns:
            Kullanılabilir gruplar listesi
        """
        now = datetime.utcnow()
        available_groups = []
        
        for group in groups:
            # Grup ID'sinin string veya int olması durumunda kontrol et
            group_id = str(group.telegram_id)
            
            if group_id in self.cooldown_groups:
                cooldown_data = self.cooldown_groups[group_id]
                if cooldown_data.get('until', now) > now:
                    # Grup hala soğutuluyor
                    logger.info(f"Grup {group.title} ({group_id}) soğutuluyor. Sebep: {cooldown_data.get('reason')}, Bitiş: {cooldown_data.get('until')}")
                    continue
                else:
                    # Soğutma süresi bitti, temizle
                    logger.info(f"Grup {group.title} ({group_id}) için soğutma süresi bitti, gönderime dahil ediliyor")
                    self.cooldown_groups.pop(group_id, None)
            
            available_groups.append(group)
        
        return available_groups
    
    async def _handle_group_error(self, group_id: str, error_msg: str) -> None:
        """
        Grup gönderim hatalarını işler ve soğutma süresi belirler
        
        Args:
            group_id: Grup ID'si
            error_msg: Hata mesajı
        """
        now = datetime.utcnow()
        cooldown_minutes = 5  # Varsayılan 5 dakika
        reason = "error"
        
        # Grup ID string olarak standartlaştır
        group_id = str(group_id)
        
        # Daha önce soğutma var mı kontrol et
        if group_id in self.cooldown_groups:
            attempt = self.cooldown_groups[group_id].get('attempt', 0) + 1
        else:
            attempt = 1
            
        # Hata türüne göre soğutma süresi belirle
        if "flood" in error_msg.lower():
            cooldown_minutes = 30 * attempt  # Her hata tekrarında süreyi artır
            reason = "flood_wait"
        elif "forbidden" in error_msg.lower() or "admin" in error_msg.lower():
            cooldown_minutes = 120  # Yetki hatalarında 2 saat
            reason = "permission_error"
        elif "not found" in error_msg.lower():
            cooldown_minutes = 240  # Grup bulunamadı hatalarında 4 saat
            reason = "not_found"
        else:
            # Genel hatalarda, deneme sayısına göre soğutma
            cooldown_minutes = 5 * attempt  # Her hata tekrarında süreyi artır
            
        # Maksimum 24 saat soğutma uygula
        cooldown_minutes = min(cooldown_minutes, 24 * 60)
            
        # Soğutma verilerini güncelle
        self.cooldown_groups[group_id] = {
            'until': now + timedelta(minutes=cooldown_minutes),
            'reason': reason,
            'attempt': attempt,
            'error': error_msg
        }
        
        # Günlüğe kaydet
        group = self.db.query(Group).filter_by(telegram_id=group_id).first()
        group_name = group.title if group else f"ID: {group_id}"
        
        logger.warning(f"Grup {group_name} ({group_id}) soğutmaya alındı. Sebep: {reason}, Süre: {cooldown_minutes} dk, Deneme: {attempt}")
        
        # Grubu geçici olarak devre dışı bırakmayı düşünebilirsiniz (çok tekrar eden hatalar için)
        if attempt > 5:
            logger.error(f"Grup {group_name} ({group_id}) çok fazla hata verdi, manuel müdahale gerekebilir.")
            # TODO: Admin bildirim sistemi eklenebilir
    
    async def get_group_cooldown_info(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Kullanıcının soğutma modundaki gruplarının bilgilerini döndürür
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            Soğutma modundaki grupların detaylı bilgisi
        """
        # Kullanıcının gruplarını al
        user_groups = self.db.query(Group).filter_by(user_id=user_id).all()
        user_group_ids = [str(g.telegram_id) for g in user_groups]
        
        now = datetime.utcnow()
        result = []
        
        # Soğutma modundaki grupları filtrele
        for group_id, cooldown_data in self.cooldown_groups.items():
            if group_id in user_group_ids and cooldown_data.get('until', now) > now:
                # İlgili grup bilgilerini bul
                group = next((g for g in user_groups if str(g.telegram_id) == group_id), None)
                if group:
                    result.append({
                        "group_id": group_id,
                        "group_name": group.title,
                        "cooldown_until": cooldown_data.get('until').isoformat(),
                        "reason": cooldown_data.get('reason', 'unknown'),
                        "attempt": cooldown_data.get('attempt', 1),
                        "error": cooldown_data.get('error', 'unknown')
                    })
        
        return result
    
    async def reset_group_cooldown(self, group_id: str) -> Dict[str, Any]:
        """
        Belirli bir grup için soğutma modunu sıfırlar
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            İşlem sonucu
        """
        group_id = str(group_id)
        
        if group_id in self.cooldown_groups:
            self.cooldown_groups.pop(group_id, None)
            logger.info(f"Grup {group_id} için soğutma manuel olarak sıfırlandı")
            return {
                "success": True,
                "message": f"Grup {group_id} için soğutma sıfırlandı",
                "group_id": group_id
            }
        else:
            return {
                "success": False,
                "message": f"Grup {group_id} soğutma modunda değil",
                "group_id": group_id
            }
    
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
    
    async def get_scheduled_messages_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Kullanıcının zamanlanmış mesaj istatistiklerini döndürür
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            Zamanlanmış mesaj istatistikleri
        """
        try:
            # Aktif şablonları al
            active_templates = self.db.query(MessageTemplate).filter(
                MessageTemplate.user_id == user_id,
                MessageTemplate.is_active == True
            ).all()
            
            # Son 24 saatteki mesajları al
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            recent_logs = self.db.query(MessageLog).filter(
                MessageLog.user_id == user_id,
                MessageLog.sent_at >= one_day_ago
            ).all()
            
            # Başarı/Hata oranları
            success_count = sum(1 for log in recent_logs if log.status == 'success')
            error_count = sum(1 for log in recent_logs if log.status == 'error')
            success_rate = (success_count / len(recent_logs)) * 100 if recent_logs else 0
            
            # Grup bazlı analiz
            group_stats = {}
            for log in recent_logs:
                group_id = str(log.telegram_id)
                if group_id not in group_stats:
                    group_stats[group_id] = {"success": 0, "error": 0, "total": 0}
                
                group_stats[group_id]["total"] += 1
                if log.status == 'success':
                    group_stats[group_id]["success"] += 1
                elif log.status == 'error':
                    group_stats[group_id]["error"] += 1
            
            # Şablon performansı
            template_stats = {}
            for log in recent_logs:
                if log.message_template_id:
                    template_id = log.message_template_id
                    if template_id not in template_stats:
                        template_stats[template_id] = {"success": 0, "error": 0, "total": 0}
                    
                    template_stats[template_id]["total"] += 1
                    if log.status == 'success':
                        template_stats[template_id]["success"] += 1
                    elif log.status == 'error':
                        template_stats[template_id]["error"] += 1
            
            # Aktif şablon bilgilerini ekle
            templates_info = []
            for template in active_templates:
                stats = template_stats.get(template.id, {"success": 0, "error": 0, "total": 0})
                success_rate = (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                
                templates_info.append({
                    "id": template.id,
                    "name": template.name,
                    "type": template.message_type,
                    "interval": template.interval_minutes,
                    "total_sent": stats["total"],
                    "success_rate": success_rate
                })
            
            # Mesaj gönderim saat dağılımı
            hour_distribution = {}
            for log in recent_logs:
                hour = log.sent_at.hour
                hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
            
            return {
                "total_active_templates": len(active_templates),
                "messages_last_24h": len(recent_logs),
                "success_rate": success_rate,
                "error_rate": 100 - success_rate,
                "templates": templates_info,
                "group_stats": [
                    {
                        "group_id": group_id,
                        "total_messages": stats["total"],
                        "success_rate": (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                    } for group_id, stats in group_stats.items()
                ],
                "hour_distribution": [
                    {"hour": hour, "count": count} for hour, count in hour_distribution.items()
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"İstatistik toplama hatası: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
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