from fastapi import FastAPI, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi.routing import APIRoute
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Set, List, Tuple, Optional, Callable, Any
import hashlib
import re
import logging

from app.core.logging import logger
from app.config import settings

logger = logging.getLogger("app.middleware.rate_limiter")

# API istek sınırlama için basit bir sözlük tabanlı önbellek
# IP -> (zamanlar listesi, son temizleme zamanı)
request_cache: Dict[str, Tuple[list, float]] = {}

# Temizleme intervali (saniye)
CLEANUP_INTERVAL = 60.0

class RateLimiterBackend:
    """Rate limiter için kayıt tutma backend'i"""
    
    def __init__(self):
        """In-memory rate limiter backend"""
        self.requests: Dict[str, List[float]] = {}
        self.blocked: Dict[str, float] = {}
        self.last_cleanup = time.time()
        self.lock = asyncio.Lock()
    
    async def cleanup(self, cleanup_interval: int = 60):
        """Eski kayıtları temizle"""
        if time.time() - self.last_cleanup < cleanup_interval:
            return
            
        async with self.lock:
            current_time = time.time()
            self.last_cleanup = current_time
            
            # Eski istek verilerini temizle
            for key in list(self.requests.keys()):
                self.requests[key] = [ts for ts in self.requests[key] if current_time - ts < 3600]
                if not self.requests[key]:
                    del self.requests[key]
            
            # Süresi dolan engelleri kaldır
            for key in list(self.blocked.keys()):
                if current_time > self.blocked[key]:
                    del self.blocked[key]
    
    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        """Bir anahtarın hız sınırını aşıp aşmadığını kontrol eder"""
        await self.cleanup()
        
        # Engellenen IP adresi kontrolü
        async with self.lock:
            if key in self.blocked and time.time() < self.blocked[key]:
                return True
        
        # İstek sayma
        current_time = time.time()
        request_timestamps = await self._get_requests(key)
        
        # Belirtilen zaman penceresi içindeki istekleri filtrele
        window_start = current_time - window
        relevant_requests = [ts for ts in request_timestamps if ts > window_start]
        
        # İstek sayısı limiti aşıyor mu kontrol et
        if len(relevant_requests) >= limit:
            return True
        
        # Yeni isteği kaydet
        await self._add_request(key, current_time)
        return False
    
    async def block_key(self, key: str, duration: int):
        """Bir anahtarı belirli bir süre için engeller"""
        async with self.lock:
            self.blocked[key] = time.time() + duration
            logger.warning(f"IP adresi {duration} saniye engellendi: {key}")
    
    async def _get_requests(self, key: str) -> List[float]:
        """Bir anahtar için istek zaman damgalarını döndürür"""
        async with self.lock:
            if key not in self.requests:
                self.requests[key] = []
            return self.requests[key].copy()
    
    async def _add_request(self, key: str, timestamp: float):
        """Bir anahtara yeni bir istek zaman damgası ekler"""
        async with self.lock:
            if key not in self.requests:
                self.requests[key] = []
            self.requests[key].append(timestamp)

class RateLimiter(BaseHTTPMiddleware):
    """
    İstek hızını sınırlayan middleware.
    
    Belirli bir süre içinde belirli bir IP adresinden gelen 
    istek sayısını sınırlar.
    """
    
    def __init__(
        self, 
        app: FastAPI,
        general_limit: int = 100,
        general_window: int = 60,
        api_limit: int = 50,
        api_window: int = 60,
        auth_limit: int = 10,
        auth_window: int = 60,
        block_duration: int = 300,
        whitelist: List[str] = None,
        backend: Optional[RateLimiterBackend] = None,
    ):
        """
        Rate limiter middleware'i başlatır.
        
        Args:
            app: FastAPI uygulaması
            general_limit: Genel istek limiti (varsayılan: 100 istek)
            general_window: Genel zaman penceresi (saniye, varsayılan: 60)
            api_limit: API istekleri limiti (varsayılan: 50 istek)
            api_window: API istekleri zaman penceresi (saniye, varsayılan: 60)
            auth_limit: Kimlik doğrulama istekleri limiti (varsayılan: 10 istek)
            auth_window: Kimlik doğrulama istekleri zaman penceresi (saniye, varsayılan: 60)
            block_duration: Engelleme süresi (saniye, varsayılan: 300)
            whitelist: Beyaz listedeki IP adresleri
            backend: Rate limiter backend'i
        """
        super().__init__(app)
        self.general_limit = general_limit
        self.general_window = general_window
        self.api_limit = api_limit
        self.api_window = api_window
        self.auth_limit = auth_limit
        self.auth_window = auth_window
        self.block_duration = block_duration
        self.whitelist = whitelist or ["127.0.0.1", "::1", "localhost"]
        self.backend = backend or RateLimiterBackend()
        
        # Path kategorileri için regex
        self.auth_regex = re.compile(r"^/api/auth/")
        self.api_regex = re.compile(r"^/api/")
        
        logger.info(f"Rate limiter başlatıldı: {general_limit}/{general_window}s")
    
    async def get_limit_for_path(self, path: str) -> Tuple[int, int]:
        """Belirli bir path için limit ve zaman penceresi döndürür"""
        if self.auth_regex.match(path):
            return self.auth_limit, self.auth_window
        elif self.api_regex.match(path):
            return self.api_limit, self.api_window
        else:
            return self.general_limit, self.general_window
    
    def get_client_ip(self, request: Request) -> str:
        """İstemci IP adresini belirler"""
        # X-Forwarded-For header'ı varsa kullan (proxy arkasında ise)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            # Doğrudan bağlantı durumunda
            ip = request.client.host if request.client else "unknown"
        return ip
    
    def get_rate_limit_key(self, request: Request) -> str:
        """Rate limit için eşsiz anahtar oluşturur"""
        ip = self.get_client_ip(request)
        path_prefix = request.url.path.split("/")[1:3]
        path_key = "/".join(path_prefix)
        
        # Eğer oturum açılmışsa, kullanıcı ID'sini de ekle
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"{ip}:{path_key}:{user_id}"
        return f"{ip}:{path_key}"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Middleware ana fonksiyonu"""
        # Beyaz listedeki IP'leri kontrol et
        client_ip = self.get_client_ip(request)
        if client_ip in self.whitelist:
            return await call_next(request)
        
        # Health check ve static dosya isteklerini atla
        path = request.url.path
        if path == "/health" or path.startswith("/static/"):
            return await call_next(request)
        
        # Path için limit ve zaman penceresi belirle
        limit, window = await self.get_limit_for_path(path)
        
        # Rate limit anahtarı oluştur
        key = self.get_rate_limit_key(request)
        
        # Rate limit kontrolü
        is_limited = await self.backend.is_rate_limited(key, limit, window)
        
        if is_limited:
            # Ardışık sınır aşımı için engelleme
            await self.backend.block_key(key, self.block_duration)
            
            logger.warning(f"Rate limit aşıldı: {key}, path: {path}")
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Çok fazla istek gönderdiniz. Lütfen daha sonra tekrar deneyin.",
                    "retry_after": self.block_duration
                },
                headers={"Retry-After": str(self.block_duration)}
            )
        
        # Normal işlem devam eder
        return await call_next(request)

def add_rate_limiter(app: FastAPI, settings_obj=None):
    """
    Uygulamaya rate limiter middleware ekler.
    
    Args:
        app: FastAPI uygulaması
        settings_obj: Ayarları içeren nesne (isteğe bağlı)
    """
    config = settings_obj or settings
    
    # Ayarlardan değerleri al (yoksa varsayılanları kullan)
    general_limit = getattr(config, "RATE_LIMIT_GENERAL", 100)
    general_window = getattr(config, "RATE_LIMIT_GENERAL_WINDOW", 60)
    api_limit = getattr(config, "RATE_LIMIT_API", 50)
    api_window = getattr(config, "RATE_LIMIT_API_WINDOW", 60)
    auth_limit = getattr(config, "RATE_LIMIT_AUTH", 10)
    auth_window = getattr(config, "RATE_LIMIT_AUTH_WINDOW", 60)
    block_duration = getattr(config, "RATE_LIMIT_BLOCK_DURATION", 300)
    whitelist = getattr(config, "RATE_LIMIT_WHITELIST", ["127.0.0.1", "::1", "localhost"])
    
    # Rate limiter oluştur ve ekle
    limiter = RateLimiter(
        app=app,
        general_limit=general_limit,
        general_window=general_window,
        api_limit=api_limit,
        api_window=api_window,
        auth_limit=auth_limit,
        auth_window=auth_window,
        block_duration=block_duration,
        whitelist=whitelist
    )
    
    # Middleware'i uygula
    app.add_middleware(RateLimiter)
    
    logger.info("Rate limiter middleware eklendi")
    return limiter

def check_rate_limit(client_ip: str) -> Tuple[bool, int, float]:
    """
    Bir IP adresi için rate limit kontrolü yapar.
    
    Args:
        client_ip: İstemci IP adresi
        
    Returns:
        Tuple[bool, int, float]: (Limit aşıldı mı, kalan istek sayısı, sıfırlama zamanı)
    """
    current_time = time.time()
    
    # Son 60 saniye içindeki istekleri sakla
    window_start_time = current_time - 60
    
    # Cache'de kayıt yoksa oluştur
    if client_ip not in request_cache:
        request_cache[client_ip] = ([], current_time)
    
    # İstek zamanlarını al
    request_times, _ = request_cache[client_ip]
    
    # Son bir dakika içindeki istekleri filtrele
    recent_requests = [t for t in request_times if t > window_start_time]
    
    # Limit kontrolü
    limit = settings.RATE_LIMIT_PER_MINUTE
    is_exceeded = len(recent_requests) >= limit
    
    # Bu isteği ekle (zaten limit aşılsa bile ekliyoruz ki ileride Retry-After doğru hesaplansın)
    recent_requests.append(current_time)
    request_cache[client_ip] = (recent_requests, current_time)
    
    # En eski isteğin zamanını bul ve sıfırlama zamanını hesapla
    if recent_requests:
        # İlk istek + 60 saniye, yani pencere dışına çıkacağı zaman
        oldest_request = min(recent_requests)
        reset_time = oldest_request + 60
    else:
        reset_time = current_time + 60
    
    # Kalan istek sayısı
    remaining = max(0, limit - len(recent_requests))
    
    return is_exceeded, remaining, reset_time

def _get_client_ip(request: Request) -> str:
    """
    İstemci IP adresini alır.
    Proxy arkasındaysa X-Forwarded-For header'ından almaya çalışır.
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # X-Forwarded-For header'ı virgülle ayrılmış IP adresleri içerebilir
        # İlk IP adresi genellikle gerçek istemci IP'sidir
        return xff.split(",")[0].strip()
    
    # Normal durumda client host adresini kullan
    return request.client.host if request.client else "unknown"

def _should_skip_rate_limiting(path: str) -> bool:
    """
    Belirli path'ler için rate limiting atlanmalı mı?
    """
    # Sağlık kontrolü endpointleri için rate limiti atla
    skip_paths = {
        "/health", 
        "/api/health", 
        "/metrics",
        "/api/ping",
        "/ping",
        "/favicon.ico"
    }
    
    # Static dosya yolları için atla
    if path.startswith("/static/"):
        return True
        
    return path in skip_paths

async def periodic_cleanup():
    """
    Rate limiter önbelleğini periyodik olarak temizleyen bir arka plan görevi
    """
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL)
            cleanup_old_requests()
        except Exception as e:
            logger.error(f"Rate limiter temizleme hatası: {str(e)}")

def cleanup_old_requests():
    """
    Eski istekleri önbellekten temizler
    """
    current_time = time.time()
    window_start_time = current_time - 60
    remove_keys = []
    
    for ip, (request_times, last_cleanup_time) in request_cache.items():
        # Son temizlemeden bu yana 5 dakika geçtiyse ve son istek 1 dakikadan eskiyse
        # bu IP'yi tamamen kaldır
        if current_time - last_cleanup_time > 300 and (not request_times or max(request_times) < window_start_time):
            remove_keys.append(ip)
            continue
            
        # Son bir dakika içindeki istekleri tut, eskileri sil
        recent_requests = [t for t in request_times if t > window_start_time]
        
        # İstek zamanlarını güncelle
        if len(recent_requests) < len(request_times):
            request_cache[ip] = (recent_requests, current_time)
    
    # Gereksiz kayıtları temizle
    for ip in remove_keys:
        del request_cache[ip]
        
    if remove_keys:
        logger.debug(f"{len(remove_keys)} IP adresi rate limiter önbelleğinden temizlendi")

def get_rate_limiter_stats():
    """
    Rate limiter istatistiklerini döndürür
    """
    total_tracked_ips = len(request_cache)
    total_requests = sum(len(times) for times, _ in request_cache.values())
    
    return {
        "tracked_ips": total_tracked_ips,
        "total_requests": total_requests,
        "limit_per_minute": settings.RATE_LIMIT_PER_MINUTE
    } 