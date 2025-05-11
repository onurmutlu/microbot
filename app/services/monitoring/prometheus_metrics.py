import os
import time
from typing import Dict, Any, Optional, List
from prometheus_client import Counter, Gauge, Histogram, Summary
import logging
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Metrikler
GROUP_MESSAGE_COUNTER = Counter(
    'telegram_group_messages_total', 
    'Telegram gruplarına gönderilen toplam mesaj sayısı',
    ['group_id', 'status']
)

MESSAGE_SIZE_HISTOGRAM = Histogram(
    'telegram_message_size_bytes',
    'Telegram mesaj boyutu dağılımı (byte cinsinden)',
    ['group_id'],
    buckets=(64, 128, 256, 512, 1024, 2048, 4096, 8192)
)

ACTIVE_USERS_GAUGE = Gauge(
    'active_users_total',
    'Aktif kullanıcı sayısı'
)

API_REQUEST_COUNTER = Counter(
    'api_requests_total',
    'API endpoint\'lerine yapılan istek sayısı',
    ['endpoint', 'method', 'status']
)

API_REQUEST_LATENCY = Histogram(
    'api_request_latency_seconds',
    'API isteği işleme süresi',
    ['endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

TELEGRAM_CLIENT_ERRORS = Counter(
    'telegram_client_errors_total',
    'Telegram client hata sayısı',
    ['error_type']
)

DATABASE_OPERATION_LATENCY = Histogram(
    'database_operation_latency_seconds',
    'Veritabanı işlem süresi',
    ['operation_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)

CACHE_HIT_COUNTER = Counter(
    'cache_hit_total',
    'Önbellek isabet sayısı',
    ['cache_type']
)

CACHE_MISS_COUNTER = Counter(
    'cache_miss_total',
    'Önbellek ıskalama sayısı',
    ['cache_type']
)

SCHEDULED_TASKS_GAUGE = Gauge(
    'scheduled_tasks_total',
    'Zamanlanmış görev sayısı',
    ['status']
)

SYSTEM_RESOURCES_GAUGE = Gauge(
    'system_resources',
    'Sistem kaynak kullanımı',
    ['resource_type']
)

class PrometheusMetricService:
    """
    Uygulama genelinde Prometheus metriklerini toplamak için servis
    """
    
    @staticmethod
    def increment_group_message(group_id: str, status: str = "success"):
        """
        Gönderilen grup mesajı sayısını artırır
        
        Args:
            group_id: Grup ID'si
            status: Mesaj durumu (success, error, etc.)
        """
        try:
            GROUP_MESSAGE_COUNTER.labels(group_id=group_id, status=status).inc()
        except Exception as e:
            logger.error(f"Mesaj sayacı artırma hatası: {str(e)}")
    
    @staticmethod
    def observe_message_size(group_id: str, size_bytes: int):
        """
        Mesaj boyutunu kaydeder
        
        Args:
            group_id: Grup ID'si
            size_bytes: Mesaj boyutu (byte cinsinden)
        """
        try:
            MESSAGE_SIZE_HISTOGRAM.labels(group_id=group_id).observe(size_bytes)
        except Exception as e:
            logger.error(f"Mesaj boyutu gözlemleme hatası: {str(e)}")
    
    @staticmethod
    def set_active_users(count: int):
        """
        Aktif kullanıcı sayısını ayarlar
        
        Args:
            count: Aktif kullanıcı sayısı
        """
        try:
            ACTIVE_USERS_GAUGE.set(count)
        except Exception as e:
            logger.error(f"Aktif kullanıcı sayısı ayarlama hatası: {str(e)}")
    
    @staticmethod
    def increment_api_request(endpoint: str, method: str, status: str):
        """
        API isteği sayısını artırır
        
        Args:
            endpoint: API endpoint'i
            method: HTTP metodu
            status: HTTP durum kodu
        """
        try:
            API_REQUEST_COUNTER.labels(endpoint=endpoint, method=method, status=status).inc()
        except Exception as e:
            logger.error(f"API isteği sayacı artırma hatası: {str(e)}")
    
    @staticmethod
    @contextmanager
    def track_api_latency(endpoint: str):
        """
        API isteği işleme süresini ölçer
        
        Args:
            endpoint: API endpoint'i
        """
        try:
            start_time = time.time()
            yield
            duration = time.time() - start_time
            API_REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        except Exception as e:
            logger.error(f"API latency izleme hatası: {str(e)}")
            yield
    
    @staticmethod
    def track_api_latency_decorator(endpoint: str):
        """
        API isteği işleme süresini ölçmek için decorator
        
        Args:
            endpoint: API endpoint'i
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with PrometheusMetricService.track_api_latency(endpoint):
                    return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def increment_telegram_error(error_type: str):
        """
        Telegram hatası sayısını artırır
        
        Args:
            error_type: Hata türü
        """
        try:
            TELEGRAM_CLIENT_ERRORS.labels(error_type=error_type).inc()
        except Exception as e:
            logger.error(f"Telegram hatası sayacı artırma hatası: {str(e)}")
    
    @staticmethod
    @contextmanager
    def track_database_operation(operation_type: str):
        """
        Veritabanı işlem süresini ölçer
        
        Args:
            operation_type: İşlem türü (query, insert, update, delete)
        """
        try:
            start_time = time.time()
            yield
            duration = time.time() - start_time
            DATABASE_OPERATION_LATENCY.labels(operation_type=operation_type).observe(duration)
        except Exception as e:
            logger.error(f"Veritabanı işlem süresi izleme hatası: {str(e)}")
            yield
    
    @staticmethod
    def increment_cache_hit(cache_type: str):
        """
        Önbellek isabet sayısını artırır
        
        Args:
            cache_type: Önbellek türü
        """
        try:
            CACHE_HIT_COUNTER.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Önbellek isabet sayacı artırma hatası: {str(e)}")
    
    @staticmethod
    def increment_cache_miss(cache_type: str):
        """
        Önbellek ıskalama sayısını artırır
        
        Args:
            cache_type: Önbellek türü
        """
        try:
            CACHE_MISS_COUNTER.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Önbellek ıskalama sayacı artırma hatası: {str(e)}")
    
    @staticmethod
    def set_scheduled_tasks(status: str, count: int):
        """
        Zamanlanmış görev sayısını ayarlar
        
        Args:
            status: Görev durumu (active, paused, completed, error)
            count: Görev sayısı
        """
        try:
            SCHEDULED_TASKS_GAUGE.labels(status=status).set(count)
        except Exception as e:
            logger.error(f"Zamanlanmış görev sayısı ayarlama hatası: {str(e)}")
    
    @staticmethod
    def set_system_resource(resource_type: str, value: float):
        """
        Sistem kaynak kullanımını ayarlar
        
        Args:
            resource_type: Kaynak türü (cpu, memory, disk)
            value: Kaynak kullanım değeri
        """
        try:
            SYSTEM_RESOURCES_GAUGE.labels(resource_type=resource_type).set(value)
        except Exception as e:
            logger.error(f"Sistem kaynağı ayarlama hatası: {str(e)}")

# Singleton instance
metric_service = PrometheusMetricService() 