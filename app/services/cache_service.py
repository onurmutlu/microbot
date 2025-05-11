import asyncio
import json
import logging
import pickle
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, cast
from functools import wraps
from datetime import timedelta

import redis.asyncio as redis
from fastapi import Request, Response
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

from app.config import settings
from app.services.monitoring.prometheus_metrics import metric_service

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CacheService:
    """
    Uygulama genelinde önbellekleme işlemlerini yönetir.
    Redis'i kullanarak API ve veritabanı yanıtlarını önbelleğe alır.
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._initialized = False
        self._prefix = settings.REDIS_PREFIX or "microbot"
    
    async def init(self):
        """Redis bağlantısını başlatır ve FastAPI önbelleklemeyi ayarlar"""
        if self._initialized:
            return
            
        try:
            self._redis = await redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                encoding="utf-8",
                decode_responses=False  # Binary yanıtları bırak
            )
            
            # Redis bağlantısını test et
            await self._redis.ping()
            
            # FastAPI önbellekleme
            redis_instance = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB
            )
            redis_backend = RedisBackend(redis_instance)
            FastAPICache.init(redis_backend, prefix=f"{self._prefix}:fastapi")
            
            self._initialized = True
            logger.info("Cache service başarıyla başlatıldı")
        except Exception as e:
            logger.error(f"Cache service başlatma hatası: {str(e)}")
            self._initialized = False
    
    async def ensure_initialized(self):
        """Servisin başlatıldığından emin olur"""
        if not self._initialized:
            await self.init()
    
    async def set(self, key: str, value: Any, expire: int = 600) -> bool:
        """
        Bir değeri önbelleğe kaydeder.
        
        Args:
            key: Önbellek anahtarı
            value: Kaydedilecek değer
            expire: Süre aşımı (saniye)
            
        Returns:
            İşlem başarılı mı
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return False
            
        try:
            # Serialization
            if isinstance(value, str):
                serialized_value = value
            else:
                serialized_value = pickle.dumps(value)
                
            # Redis'e kaydet
            full_key = f"{self._prefix}:{key}"
            await self._redis.set(full_key, serialized_value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Önbelleğe yazma hatası: {str(e)}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Önbellekten bir değer alır.
        
        Args:
            key: Önbellek anahtarı
            default: Varsayılan değer (anahtar bulunamazsa)
            
        Returns:
            Önbellekteki değer veya varsayılan değer
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return default
            
        try:
            # Redis'ten al
            full_key = f"{self._prefix}:{key}"
            value = await self._redis.get(full_key)
            
            if value is None:
                metric_service.increment_cache_miss("redis")
                return default
                
            try:
                # Deserialization
                result = pickle.loads(value)
                metric_service.increment_cache_hit("redis")
                return result
            except:
                # String ise
                metric_service.increment_cache_hit("redis")
                return value
        except Exception as e:
            logger.error(f"Önbellekten okuma hatası: {str(e)}")
            return default
    
    async def delete(self, key: str) -> bool:
        """
        Önbellekten bir anahtarı siler.
        
        Args:
            key: Önbellek anahtarı
            
        Returns:
            İşlem başarılı mı
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return False
            
        try:
            full_key = f"{self._prefix}:{key}"
            await self._redis.delete(full_key)
            return True
        except Exception as e:
            logger.error(f"Önbellek silme hatası: {str(e)}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Desene uyan tüm anahtarları siler.
        
        Args:
            pattern: Silme deseni (örn. "user:*")
            
        Returns:
            Silinen anahtar sayısı
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return 0
            
        try:
            full_pattern = f"{self._prefix}:{pattern}"
            keys = await self._redis.keys(full_pattern)
            
            if not keys:
                return 0
                
            count = await self._redis.delete(*keys)
            return count
        except Exception as e:
            logger.error(f"Desen silme hatası: {str(e)}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        Bir anahtarın önbellekte var olup olmadığını kontrol eder.
        
        Args:
            key: Önbellek anahtarı
            
        Returns:
            Anahtar var mı
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return False
            
        try:
            full_key = f"{self._prefix}:{key}"
            return await self._redis.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Anahtar kontrol hatası: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Bir sayısal değeri artırır.
        
        Args:
            key: Önbellek anahtarı
            amount: Artış miktarı
            
        Returns:
            Artıştan sonraki değer
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return 0
            
        try:
            full_key = f"{self._prefix}:{key}"
            return await self._redis.incrby(full_key, amount)
        except Exception as e:
            logger.error(f"Artırma hatası: {str(e)}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Bir anahtarın süre aşımını ayarlar.
        
        Args:
            key: Önbellek anahtarı
            seconds: Saniye cinsinden süre aşımı
            
        Returns:
            İşlem başarılı mı
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return False
            
        try:
            full_key = f"{self._prefix}:{key}"
            return await self._redis.expire(full_key, seconds)
        except Exception as e:
            logger.error(f"Süre aşımı ayarlama hatası: {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """
        Bir anahtarın kalan yaşam süresini döndürür.
        
        Args:
            key: Önbellek anahtarı
            
        Returns:
            Kalan süre (saniye). -1: süresiz, -2: anahtar yok
        """
        await self.ensure_initialized()
        
        if not self._redis:
            return -2
            
        try:
            full_key = f"{self._prefix}:{key}"
            return await self._redis.ttl(full_key)
        except Exception as e:
            logger.error(f"TTL sorgu hatası: {str(e)}")
            return -2
    
    async def invalidate_user_cache(self, user_id: int) -> int:
        """
        Belirli bir kullanıcıyla ilgili tüm önbellek verilerini geçersiz kılar.
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            Silinen anahtar sayısı
        """
        pattern = f"user:{user_id}:*"
        return await self.delete_pattern(pattern)
    
    async def invalidate_group_cache(self, group_id: int) -> int:
        """
        Belirli bir grupla ilgili tüm önbellek verilerini geçersiz kılar.
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            Silinen anahtar sayısı
        """
        pattern = f"group:{group_id}:*"
        return await self.delete_pattern(pattern)
    
    def cached(self, ttl_seconds: int = 60, key_prefix: str = ""):
        """
        Asenkron fonksiyonları önbelleğe alma decorator'ı.
        
        Args:
            ttl_seconds: Saniye cinsinden süre aşımı
            key_prefix: Anahtar öneki
            
        Returns:
            Decorator fonksiyonu
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                await self.ensure_initialized()
                
                # Cache anahtarı oluştur
                if key_prefix:
                    prefix = key_prefix
                else:
                    prefix = func.__module__ + "." + func.__name__
                
                # Args ve kwargs'tan anahtar oluştur
                key_parts = [prefix]
                
                # Fonksiyon argümanlarını anahtar olarak kullan
                for arg in args:
                    if arg is not None and not isinstance(arg, Request) and not isinstance(arg, Response):
                        key_parts.append(str(arg))
                
                # Keyword argümanlarını anahtar olarak kullan
                for k, v in sorted(kwargs.items()):
                    if v is not None and not isinstance(v, Request) and not isinstance(v, Response):
                        key_parts.append(f"{k}:{v}")
                
                cache_key = ":".join(key_parts)
                
                # Önbellekten kontrol et
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Fonksiyonu çalıştır
                result = await func(*args, **kwargs)
                
                # Sonucu önbelleğe al
                await self.set(cache_key, result, expire=ttl_seconds)
                
                return result
            return wrapper
        return decorator

# Singleton instance
cache_service = CacheService() 