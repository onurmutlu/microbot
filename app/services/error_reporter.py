"""
Gelişmiş hata raporlama sistemi.

Bu modül, uygulamadaki hataları loglayan, kategorize eden ve gerekirse bildirim gönderen
merkezileştirilmiş bir hata raporlama sistemi sağlar.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

import logging
import traceback
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum, auto
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("error_reporter")

class ErrorSeverity(Enum):
    """Hata şiddet seviyeleri"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

class ErrorCategory(Enum):
    """Hata kategorileri"""
    SYSTEM = "system"
    DATABASE = "database"
    NETWORK = "network"
    WEBSOCKET = "websocket"
    API = "api"
    TELEGRAM = "telegram"
    SECURITY = "security"
    SCHEDULER = "scheduler"
    OTHER = "other"

class ErrorReport:
    """Bir hata raporu temsil eder"""
    def __init__(
        self,
        error: Exception,
        severity: ErrorSeverity,
        category: ErrorCategory,
        source: str,
        message: str = None,
        context: Dict[str, Any] = None,
        timestamp: datetime = None,
    ):
        self.error = error
        self.error_type = type(error).__name__
        self.severity = severity
        self.category = category
        self.source = source
        self.message = message or str(error)
        self.context = context or {}
        self.timestamp = timestamp or datetime.now()
        self.traceback = traceback.format_exc()
        self.report_id = f"{int(time.time())}-{id(error)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Raporu sözlük formatına dönüştür"""
        return {
            "report_id": self.report_id,
            "error_type": self.error_type,
            "severity": self.severity.name,
            "category": self.category.value,
            "source": self.source,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback
        }
    
    def to_json(self) -> str:
        """Raporu JSON formatına dönüştür"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

class ErrorReporter:
    """Hata raporlama sistemi"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ErrorReporter, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, log_dir: str = "logs/errors"):
        """Hata raporlama sistemini başlatır."""
        if ErrorReporter._initialized:
            return
            
        self.log_dir = log_dir
        self.error_handlers: Dict[ErrorCategory, List[Callable]] = {
            category: [] for category in ErrorCategory
        }
        self.notification_handlers: Dict[ErrorSeverity, List[Callable]] = {
            severity: [] for severity in ErrorSeverity
        }
        self.recent_errors: List[ErrorReport] = []
        self.max_recent_errors = 100
        self.stats: Dict[str, Any] = {
            "total_errors": 0,
            "by_category": {cat.value: 0 for cat in ErrorCategory},
            "by_severity": {sev.name: 0 for sev in ErrorSeverity},
            "by_source": {}
        }
        
        self.error_counts: Dict[str, int] = {}  # error_type -> count
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Log dizinini oluştur
        os.makedirs(self.log_dir, exist_ok=True)
        
        ErrorReporter._initialized = True
        logger.info("Hata raporlama sistemi başlatıldı")
    
    def report(
        self,
        error: Exception,
        severity: ErrorSeverity,
        category: ErrorCategory,
        source: str,
        message: str = None,
        context: Dict[str, Any] = None
    ) -> ErrorReport:
        """
        Yeni bir hata raporu oluştur
        
        Args:
            error: Yakalanan hata
            severity: Hata şiddet seviyesi
            category: Hata kategorisi
            source: Hata kaynağı (modül/sınıf adı)
            message: Özel hata mesajı (opsiyonel)
            context: Ek bağlam bilgisi (opsiyonel)
            
        Returns:
            Oluşturulan hata raporu
        """
        # Hata raporu oluştur
        report = ErrorReport(
            error=error,
            severity=severity,
            category=category,
            source=source,
            message=message,
            context=context
        )
        
        # İstatistikleri güncelle
        self.stats["total_errors"] += 1
        self.stats["by_category"][category.value] += 1
        self.stats["by_severity"][severity.name] += 1
        
        if source not in self.stats["by_source"]:
            self.stats["by_source"][source] = 0
        self.stats["by_source"][source] += 1
        
        error_type = type(error).__name__
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # Son hataları güncelle
        self.recent_errors.append(report)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
        
        # Log seviyesine göre loglama
        log_message = f"[{report.report_id}] {source}: {message or str(error)}"
        
        if severity == ErrorSeverity.DEBUG:
            logger.debug(log_message, exc_info=True)
        elif severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message, exc_info=True)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message, exc_info=True)
        elif severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, exc_info=True)
        
        # Hata işleyicilerini çağır
        for handler in self.error_handlers.get(category, []):
            try:
                handler(report)
            except Exception as e:
                logger.error(f"Hata işleyicisi çalıştırılırken hata oluştu: {str(e)}")
        
        # Bildirim işleyicilerini çağır (ağır işlemleri thread havuzunda çalıştır)
        if severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            for handler in self.notification_handlers.get(severity, []):
                self.executor.submit(self._run_notification_handler, handler, report)
        
        # Dosyaya kaydet
        self._save_to_file(report)
        
        return report
    
    def _run_notification_handler(self, handler: Callable, report: ErrorReport):
        """Bildirim işleyicisini çalıştır"""
        try:
            handler(report)
        except Exception as e:
            logger.error(f"Bildirim işleyicisi çalıştırılırken hata oluştu: {str(e)}")
    
    def _save_to_file(self, report: ErrorReport):
        """Raporu dosyaya kaydet"""
        try:
            # Günlük log dosyası
            today = datetime.now().strftime("%Y-%m-%d")
            filename = f"{self.log_dir}/errors_{today}.log"
            
            with open(filename, "a", encoding="utf-8") as f:
                f.write(f"--- ERROR REPORT: {report.report_id} ---\n")
                f.write(f"Time: {report.timestamp.isoformat()}\n")
                f.write(f"Severity: {report.severity.name}\n")
                f.write(f"Category: {report.category.value}\n")
                f.write(f"Source: {report.source}\n")
                f.write(f"Type: {report.error_type}\n")
                f.write(f"Message: {report.message}\n")
                f.write(f"Context: {json.dumps(report.context, ensure_ascii=False)}\n")
                f.write(f"Traceback:\n{report.traceback}\n")
                f.write("-" * 80 + "\n\n")
        except Exception as e:
            logger.error(f"Hata raporu dosyaya kaydedilirken hata oluştu: {str(e)}")
    
    def add_error_handler(self, category: ErrorCategory, handler: Callable[[ErrorReport], None]):
        """Belirli bir kategori için hata işleyicisi ekle"""
        if category not in self.error_handlers:
            self.error_handlers[category] = []
        self.error_handlers[category].append(handler)
    
    def add_notification_handler(self, severity: ErrorSeverity, handler: Callable[[ErrorReport], None]):
        """Belirli bir şiddet seviyesi için bildirim işleyicisi ekle"""
        if severity not in self.notification_handlers:
            self.notification_handlers[severity] = []
        self.notification_handlers[severity].append(handler)
    
    def get_stats(self) -> Dict[str, Any]:
        """Hata istatistiklerini getir"""
        return {
            **self.stats,
            "error_types": self.error_counts,
            "recent_errors": [err.to_dict() for err in self.recent_errors[-10:]]
        }
    
    def get_recent_errors(self, limit: int = 10, category: Optional[ErrorCategory] = None) -> List[Dict[str, Any]]:
        """Son hataları getir"""
        errors = self.recent_errors
        
        if category:
            errors = [err for err in errors if err.category == category]
            
        return [err.to_dict() for err in errors[-limit:]]
    
    def clear_stats(self):
        """İstatistikleri sıfırla"""
        self.stats = {
            "total_errors": 0,
            "by_category": {cat.value: 0 for cat in ErrorCategory},
            "by_severity": {sev.name: 0 for sev in ErrorSeverity},
            "by_source": {}
        }
        self.error_counts = {}

# Çağırıcılar için yardımcı fonksiyonlar

def report_error(
    error: Exception,
    severity: ErrorSeverity,
    category: ErrorCategory,
    source: str,
    message: str = None,
    context: Dict[str, Any] = None
) -> ErrorReport:
    """Hata raporu oluştur"""
    reporter = ErrorReporter()
    return reporter.report(error, severity, category, source, message, context)

def report_websocket_error(
    error: Exception,
    source: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    message: str = None,
    context: Dict[str, Any] = None
) -> ErrorReport:
    """WebSocket hatası rapor et"""
    return report_error(error, severity, ErrorCategory.WEBSOCKET, source, message, context)

def report_db_error(
    error: Exception, 
    source: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    message: str = None,
    context: Dict[str, Any] = None
) -> ErrorReport:
    """Veritabanı hatası rapor et"""
    return report_error(error, severity, ErrorCategory.DATABASE, source, message, context)

def report_network_error(
    error: Exception,
    source: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    message: str = None,
    context: Dict[str, Any] = None
) -> ErrorReport:
    """Ağ hatası rapor et"""
    return report_error(error, severity, ErrorCategory.NETWORK, source, message, context)

def report_telegram_error(
    error: Exception,
    source: str,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    message: str = None,
    context: Dict[str, Any] = None
) -> ErrorReport:
    """Telegram hatası rapor et"""
    return report_error(error, severity, ErrorCategory.TELEGRAM, source, message, context)

# Singleton örneği
error_reporter = ErrorReporter() 