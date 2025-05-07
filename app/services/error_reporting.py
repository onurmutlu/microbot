import logging
import time
import json
import os
import asyncio
from enum import Enum, auto
from typing import Dict, List, Callable, Optional, Any, Set
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from app.config import settings

logger = logging.getLogger(__name__)

class ErrorSeverity(str, Enum):
    """Hata şiddet seviyeleri"""
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ErrorCategory(str, Enum):
    """Hata kategorileri"""
    WEBSOCKET = "websocket"
    DATABASE = "database"
    TELEGRAM = "telegram"
    SECURITY = "security"
    NETWORK = "network"
    API = "api"
    AUTH = "auth"
    UNKNOWN = "unknown"

class ErrorReport(BaseModel):
    """Hata raporu modeli"""
    id: str
    timestamp: float
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    source: str = "system"
    user_id: Optional[str] = None
    resolved: bool = False
    resolution_time: Optional[float] = None
    resolution_notes: Optional[str] = None

class ErrorReportStats(BaseModel):
    """Hata raporu istatistikleri"""
    total_errors: int = 0
    active_errors: int = 0
    resolved_errors: int = 0
    error_categories: Dict[str, int] = Field(default_factory=dict)
    error_severities: Dict[str, int] = Field(default_factory=dict)
    error_sources: Dict[str, int] = Field(default_factory=dict)
    error_trends: Dict[str, int] = Field(default_factory=dict)  # Son 24 saat, saat başına
    recently_reported: List[str] = Field(default_factory=list)
    recently_resolved: List[str] = Field(default_factory=list)
    avg_resolution_time: Optional[float] = None
    last_updated: float = Field(default_factory=time.time)

class NotificationHandler:
    """Hata bildirimlerini yöneten temel sınıf"""
    async def notify(self, error_report: ErrorReport) -> None:
        """Hata bildirimini işler"""
        pass

class LoggingNotificationHandler(NotificationHandler):
    """Hataları log'a kaydeden bildirim işleyici"""
    def __init__(self, log_level: int = logging.ERROR):
        self.log_level = log_level
    
    async def notify(self, error_report: ErrorReport) -> None:
        """Hata bildirimini loglara yazar"""
        log_message = f"HATA RAPORU [{error_report.category}/{error_report.severity}]: {error_report.error_type} - {error_report.message}"
        
        # Şiddet seviyesine göre uygun log seviyesini belirle
        level = self.log_level
        if error_report.severity == ErrorSeverity.CRITICAL:
            level = logging.CRITICAL
        elif error_report.severity == ErrorSeverity.HIGH:
            level = logging.ERROR
        elif error_report.severity == ErrorSeverity.MEDIUM:
            level = logging.WARNING
        elif error_report.severity == ErrorSeverity.LOW:
            level = logging.INFO
        elif error_report.severity == ErrorSeverity.INFO:
            level = logging.DEBUG
        
        logger.log(level, log_message, extra={"error_report": error_report.model_dump()})

class WebhookNotificationHandler(NotificationHandler):
    """Webhook üzerinden bildirim gönderen işleyici"""
    def __init__(self, webhook_url: str, min_severity: ErrorSeverity = ErrorSeverity.HIGH):
        self.webhook_url = webhook_url
        self.min_severity = min_severity
    
    async def notify(self, error_report: ErrorReport) -> None:
        """Webhook üzerinden bildirim gönderir"""
        # Minimum şiddet seviyesi kontrolü
        severity_levels = {
            ErrorSeverity.INFO: 0,
            ErrorSeverity.LOW: 1, 
            ErrorSeverity.MEDIUM: 2,
            ErrorSeverity.HIGH: 3,
            ErrorSeverity.CRITICAL: 4
        }
        
        if severity_levels.get(error_report.severity, 0) < severity_levels.get(self.min_severity, 0):
            return
        
        # Burada webhook'a HTTP isteği gönderme kodları olacak
        # Örnek implementasyon, gerçek projede httpx veya aiohttp kullanılabilir
        logger.info(f"Webhook bildirimi gönderildi: {self.webhook_url}")

class ErrorReportingService:
    """
    Gelişmiş hata raporlama servisi.
    Hataları toplar, sınıflandırır, raporlar ve izler.
    """
    def __init__(self):
        self.reports: Dict[str, ErrorReport] = {}
        self.notification_handlers: List[NotificationHandler] = []
        self.stats = ErrorReportStats()
        self.notification_lock = asyncio.Lock()
        
        # Varsayılan olarak logging handler'ı ekle
        self.add_notification_handler(LoggingNotificationHandler())
        
        # İstatistik güncellemesi için zamanı başlat
        self._last_stats_update = time.time()
        self._last_save = time.time()
        self._stats_update_interval = 60  # 1 dakika
        self._save_interval = 300  # 5 dakika
        
        # Trend analizi için saatlik hata sayımları
        self._hourly_counts: Dict[str, int] = {}
        
        # Rapor dosya yolu
        self.reports_dir = os.path.join(settings.LOGS_DIR, "error_reports")
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
    
    def add_notification_handler(self, handler: NotificationHandler) -> None:
        """Yeni bir bildirim işleyici ekler"""
        self.notification_handlers.append(handler)
    
    async def report_error(self, 
                          error_type: str, 
                          message: str, 
                          details: Optional[Dict[str, Any]] = None,
                          category: ErrorCategory = ErrorCategory.UNKNOWN,
                          severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                          source: str = "system",
                          user_id: Optional[str] = None) -> str:
        """
        Yeni bir hata raporu oluşturur ve kaydeder.
        Hata ID'sini döndürür.
        """
        # Benzersiz bir hata ID'si oluştur (timestamp + rastgele karakter)
        error_id = f"ERR_{int(time.time())}_{hash(message) % 10000:04d}"
        
        # Hata raporunu oluştur
        report = ErrorReport(
            id=error_id,
            timestamp=time.time(),
            error_type=error_type,
            message=message,
            details=details,
            category=category,
            severity=severity,
            source=source,
            user_id=user_id,
            resolved=False
        )
        
        # Hata raporunu depola
        self.reports[error_id] = report
        
        # İstatistikleri güncelle
        await self._update_stats_with_new_report(report)
        
        # Bildirimleri gönder
        await self._send_notifications(report)
        
        # Belirli aralıklarla istatistikleri güncelle ve kaydet
        await self._periodic_maintenance()
        
        return error_id
    
    async def resolve_error(self, error_id: str, resolution_notes: Optional[str] = None) -> bool:
        """Bir hatayı çözüldü olarak işaretler"""
        if error_id in self.reports and not self.reports[error_id].resolved:
            self.reports[error_id].resolved = True
            self.reports[error_id].resolution_time = time.time()
            self.reports[error_id].resolution_notes = resolution_notes
            
            # İstatistikleri güncelle
            self.stats.active_errors -= 1
            self.stats.resolved_errors += 1
            self.stats.recently_resolved.append(error_id)
            
            # Son 10 çözülen hatayı tut
            if len(self.stats.recently_resolved) > 10:
                self.stats.recently_resolved = self.stats.recently_resolved[-10:]
            
            # Ortalama çözüm süresini güncelle
            resolved_reports = [r for r in self.reports.values() if r.resolved and r.resolution_time]
            if resolved_reports:
                resolution_times = [(r.resolution_time - r.timestamp) for r in resolved_reports]
                self.stats.avg_resolution_time = sum(resolution_times) / len(resolution_times)
            
            self.stats.last_updated = time.time()
            
            # Dosyaya kaydet
            await self._periodic_maintenance(force_save=True)
            
            return True
        return False
    
    def get_error_report(self, error_id: str) -> Optional[ErrorReport]:
        """Belirli bir hata raporunu getirir"""
        return self.reports.get(error_id)
    
    def get_error_reports(self, 
                         limit: int = 100, 
                         offset: int = 0,
                         category: Optional[ErrorCategory] = None,
                         severity: Optional[ErrorSeverity] = None,
                         resolved: Optional[bool] = None,
                         source: Optional[str] = None,
                         user_id: Optional[str] = None,
                         sort_by: str = "timestamp",
                         sort_desc: bool = True) -> List[ErrorReport]:
        """Hata raporlarını filtrelere göre getirir"""
        # Filtrelere göre raporları seç
        filtered_reports = self.reports.values()
        
        if category:
            filtered_reports = [r for r in filtered_reports if r.category == category]
        
        if severity:
            filtered_reports = [r for r in filtered_reports if r.severity == severity]
        
        if resolved is not None:
            filtered_reports = [r for r in filtered_reports if r.resolved == resolved]
        
        if source:
            filtered_reports = [r for r in filtered_reports if r.source == source]
        
        if user_id:
            filtered_reports = [r for r in filtered_reports if r.user_id == user_id]
        
        # Sıralama
        if sort_by == "timestamp":
            filtered_reports = sorted(filtered_reports, key=lambda r: r.timestamp, reverse=sort_desc)
        elif sort_by == "severity":
            severity_order = {
                ErrorSeverity.CRITICAL: 4,
                ErrorSeverity.HIGH: 3,
                ErrorSeverity.MEDIUM: 2,
                ErrorSeverity.LOW: 1,
                ErrorSeverity.INFO: 0
            }
            filtered_reports = sorted(filtered_reports, 
                                      key=lambda r: (severity_order.get(r.severity, 0), r.timestamp), 
                                      reverse=sort_desc)
        
        # Sayfalama
        return list(filtered_reports)[offset:offset+limit]
    
    def get_recent_errors(self, 
                        limit: int = 10, 
                        category: Optional[ErrorCategory] = None) -> List[Dict[str, Any]]:
        """Son hataları getirir"""
        # Filtreleme ve sayfalama için get_error_reports'u kullan
        reports = self.get_error_reports(
            limit=limit, 
            category=category, 
            sort_by="timestamp", 
            sort_desc=True
        )
        
        # Dict olarak dön
        return [r.model_dump() for r in reports]
    
    def get_stats(self) -> Dict[str, Any]:
        """Güncel hata istatistiklerini döndürür"""
        return self.stats.model_dump()
    
    def clear_stats(self) -> None:
        """Hata istatistiklerini sıfırlar"""
        self.stats = ErrorReportStats()
        self._hourly_counts = {}
        self.stats.last_updated = time.time()
    
    async def _update_stats_with_new_report(self, report: ErrorReport) -> None:
        """Yeni bir hata raporu ile istatistikleri günceller"""
        self.stats.total_errors += 1
        self.stats.active_errors += 1
        
        # Kategori istatistiklerini güncelle
        category = report.category.value
        self.stats.error_categories[category] = self.stats.error_categories.get(category, 0) + 1
        
        # Şiddet seviyesi istatistiklerini güncelle
        severity = report.severity.value
        self.stats.error_severities[severity] = self.stats.error_severities.get(severity, 0) + 1
        
        # Kaynak istatistiklerini güncelle
        source = report.source
        self.stats.error_sources[source] = self.stats.error_sources.get(source, 0) + 1
        
        # Son bildirilen hataları güncelle
        self.stats.recently_reported.append(report.id)
        if len(self.stats.recently_reported) > 10:
            self.stats.recently_reported = self.stats.recently_reported[-10:]
        
        # Saat başına hata trendlerini güncelle
        hour_key = datetime.fromtimestamp(report.timestamp).strftime("%Y-%m-%d %H:00")
        self._hourly_counts[hour_key] = self._hourly_counts.get(hour_key, 0) + 1
        
        # Son 24 saat için trend verilerini güncelle
        now = datetime.now()
        trends = {}
        
        for i in range(24):
            hour_time = now - timedelta(hours=i)
            hour_str = hour_time.strftime("%Y-%m-%d %H:00")
            trends[hour_str] = self._hourly_counts.get(hour_str, 0)
        
        self.stats.error_trends = trends
        self.stats.last_updated = time.time()
    
    async def _send_notifications(self, report: ErrorReport) -> None:
        """Tüm bildirim işleyicilere hata raporunu gönderir"""
        async with self.notification_lock:
            for handler in self.notification_handlers:
                try:
                    await handler.notify(report)
                except Exception as e:
                    logger.error(f"Bildirim gönderimi başarısız: {str(e)}")
    
    async def _periodic_maintenance(self, force_save: bool = False) -> None:
        """Periyodik bakım işlemleri: istatistik güncelleme ve kaydetme"""
        current_time = time.time()
        
        # İstatistik güncelleme zamanı geldiyse
        if force_save or (current_time - self._last_stats_update > self._stats_update_interval):
            # Aktif/çözülen hata sayılarını doğrula
            active_count = sum(1 for r in self.reports.values() if not r.resolved)
            resolved_count = sum(1 for r in self.reports.values() if r.resolved)
            
            self.stats.active_errors = active_count
            self.stats.resolved_errors = resolved_count
            
            # Saatlik hata trendlerini güncelle
            now = datetime.now()
            trends = {}
            
            for i in range(24):
                hour_time = now - timedelta(hours=i)
                hour_str = hour_time.strftime("%Y-%m-%d %H:00")
                trends[hour_str] = self._hourly_counts.get(hour_str, 0)
            
            self.stats.error_trends = trends
            self.stats.last_updated = current_time
            self._last_stats_update = current_time
        
        # Dosyaya kaydetme zamanı geldiyse
        if force_save or (current_time - self._last_save > self._save_interval):
            await self._save_reports_to_file()
            self._last_save = current_time
    
    async def _save_reports_to_file(self) -> None:
        """Hata raporlarını dosyaya kaydeder"""
        try:
            # İstatistikleri kaydet
            stats_file = os.path.join(self.reports_dir, "error_stats.json")
            with open(stats_file, "w") as f:
                json.dump(self.stats.model_dump(), f, indent=2)
            
            # Son hataları kaydet
            reports_file = os.path.join(self.reports_dir, "recent_errors.json")
            recent_reports = sorted(
                [r.model_dump() for r in self.reports.values()], 
                key=lambda x: x["timestamp"], 
                reverse=True
            )[:100]  # Son 100 hata
            
            with open(reports_file, "w") as f:
                json.dump(recent_reports, f, indent=2)
            
            logger.debug(f"Hata raporları dosyaya kaydedildi: {len(recent_reports)} hata")
        except Exception as e:
            logger.error(f"Hata raporlarını dosyaya kaydetme başarısız: {str(e)}")
    
    @classmethod
    async def load_from_file(cls) -> 'ErrorReportingService':
        """Dosyadan hata raporlarını yükler"""
        service = cls()
        
        try:
            # Dosyaların varlığını kontrol et
            reports_file = os.path.join(service.reports_dir, "recent_errors.json")
            stats_file = os.path.join(service.reports_dir, "error_stats.json")
            
            if os.path.exists(reports_file):
                with open(reports_file, "r") as f:
                    reports_data = json.load(f)
                    
                for report_data in reports_data:
                    error_id = report_data.get("id")
                    if error_id:
                        service.reports[error_id] = ErrorReport(**report_data)
            
            if os.path.exists(stats_file):
                with open(stats_file, "r") as f:
                    stats_data = json.load(f)
                    service.stats = ErrorReportStats(**stats_data)
            
            # Saatlik sayımları güncelle
            for report in service.reports.values():
                hour_key = datetime.fromtimestamp(report.timestamp).strftime("%Y-%m-%d %H:00")
                service._hourly_counts[hour_key] = service._hourly_counts.get(hour_key, 0) + 1
            
            logger.info(f"Hata raporları dosyadan yüklendi: {len(service.reports)} rapor")
        except Exception as e:
            logger.error(f"Hata raporlarını dosyadan yükleme başarısız: {str(e)}")
        
        return service

# Singleton instance
error_reporter = ErrorReportingService() 