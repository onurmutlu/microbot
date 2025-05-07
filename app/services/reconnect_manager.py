"""
Yeniden bağlanma stratejilerini yöneten servis modülü.

Bu modül, bağlantı kesilmesi durumunda otomatik yeniden bağlanma için
gelişmiş stratejileri uygular ve istatistikleri tutar.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

import logging
import asyncio
import time
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Awaitable
from enum import Enum
from pydantic import BaseModel

from app.services.error_reporter import (
    report_websocket_error, ErrorSeverity, 
    ErrorCategory, error_reporter
)

logger = logging.getLogger(__name__)

class ReconnectStrategy(str, Enum):
    """Yeniden bağlanma stratejileri"""
    EXPONENTIAL = "exponential"  # Üstel geri çekilme
    FIBONACCI = "fibonacci"      # Fibonacci dizisi
    LINEAR = "linear"            # Doğrusal artış
    RANDOM = "random"            # Rastgele aralık
    CONSTANT = "constant"        # Sabit aralık
    NONE = "none"                # Yeniden bağlanma yok

class ReconnectState(str, Enum):
    """Yeniden bağlanma durumları"""
    CONNECTED = "connected"          # Bağlı
    DISCONNECTED = "disconnected"    # Bağlantı kesildi
    CONNECTING = "connecting"        # Bağlanıyor
    BACKOFF = "backoff"              # Geri çekilme
    FAILED = "failed"                # Başarısız
    MAX_ATTEMPTS = "max_attempts"    # Maksimum deneme sayısına ulaşıldı

class ReconnectStats(BaseModel):
    """Yeniden bağlanma istatistikleri"""
    connection_attempts: int = 0
    successful_reconnects: int = 0
    failed_reconnects: int = 0
    last_reconnect_time: Optional[float] = None
    last_disconnect_time: Optional[float] = None
    total_downtime: float = 0
    avg_reconnect_time: Optional[float] = None
    current_backoff_seconds: float = 0
    current_strategy: ReconnectStrategy = ReconnectStrategy.EXPONENTIAL
    current_state: ReconnectState = ReconnectState.CONNECTED
    
    # Son durum değişiklikleri
    state_changes: List[Dict[str, Any]] = []
    # Son bağlantı kaybı nedenleri
    disconnection_reasons: Dict[str, int] = {}
    
    def add_state_change(self, 
                        from_state: ReconnectState, 
                        to_state: ReconnectState, 
                        timestamp: Optional[float] = None,
                        reason: Optional[str] = None) -> None:
        """Durum değişikliğini kaydeder"""
        if timestamp is None:
            timestamp = time.time()
        
        self.state_changes.append({
            "from": from_state,
            "to": to_state,
            "timestamp": timestamp,
            "reason": reason
        })
        
        # Sadece son 10 durum değişikliğini tut
        if len(self.state_changes) > 10:
            self.state_changes = self.state_changes[-10:]
    
    def add_disconnection_reason(self, reason: str) -> None:
        """Bağlantı kaybı nedenini kaydeder"""
        if not reason:
            reason = "unknown"
        
        self.disconnection_reasons[reason] = self.disconnection_reasons.get(reason, 0) + 1

class ReconnectManager:
    """
    Gelişmiş yeniden bağlanma yöneticisi.
    Farklı bağlanma stratejileri ve durum izleme desteği.
    """
    def __init__(self,
                strategy: ReconnectStrategy = ReconnectStrategy.EXPONENTIAL,
                max_attempts: int = 0,  # 0 = sınırsız deneme
                base_delay: float = 1.0,
                max_delay: float = 60.0,
                jitter: float = 0.1,
                connection_timeout: float = 10.0):
        """Yeniden bağlanma yöneticisini başlatır"""
        self.strategy = strategy
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.connection_timeout = connection_timeout
        
        self.stats = ReconnectStats(current_strategy=strategy)
        self.attempt_count = 0
        self._state = ReconnectState.CONNECTED
        self._last_connection_time = time.time()
        self._connection_history: List[Dict[str, Any]] = []
        self._fibonacci_cache: Dict[int, int] = {0: 0, 1: 1}  # Fibonacci hesaplamaları için önbellek
        
        # Bağlantı geri çağrı fonksiyonu
        self._connect_callback: Optional[Callable[[], Awaitable[bool]]] = None
        self._disconnect_callback: Optional[Callable[[], Awaitable[None]]] = None

    @property
    def state(self) -> ReconnectState:
        """Güncel yeniden bağlanma durumunu döndürür"""
        return self._state
    
    @state.setter
    def state(self, new_state: ReconnectState) -> None:
        """Yeniden bağlanma durumunu ayarlar ve değişiklikleri izler"""
        if new_state != self._state:
            # Durum geçişlerini izleme istatistiklerine ekle
            self.stats.add_state_change(self._state, new_state)
            
            # Özel durum değişikliği işlemleri
            if new_state == ReconnectState.CONNECTED:
                # Bağlantı başarılı olduğunda
                if self._state in (ReconnectState.CONNECTING, ReconnectState.BACKOFF):
                    self.stats.successful_reconnects += 1
                    self.stats.last_reconnect_time = time.time()
                    
                    # Ortalama yeniden bağlanma süresini güncelle
                    if self.stats.last_disconnect_time is not None:
                        reconnect_time = time.time() - self.stats.last_disconnect_time
                        self.stats.total_downtime += reconnect_time
                        
                        if self.stats.successful_reconnects > 0:
                            self.stats.avg_reconnect_time = (
                                self.stats.total_downtime / self.stats.successful_reconnects
                            )
                
                self._last_connection_time = time.time()
                self.attempt_count = 0
            
            elif new_state == ReconnectState.DISCONNECTED:
                # Bağlantı kesildiğinde
                self.stats.last_disconnect_time = time.time()
            
            elif new_state == ReconnectState.CONNECTING:
                # Bağlanma denemesi başladığında
                self.stats.connection_attempts += 1
                self.attempt_count += 1
            
            elif new_state == ReconnectState.FAILED:
                # Bağlanma denemesi başarısız olduğunda
                self.stats.failed_reconnects += 1
            
            # Durumu güncelle
            self._state = new_state
            self.stats.current_state = new_state
            
            # Durumu logla
            logger.info(f"Yeniden bağlanma durumu değişti: {self._state}")
    
    def set_callbacks(self, 
                     connect_callback: Callable[[], Awaitable[bool]], 
                     disconnect_callback: Optional[Callable[[], Awaitable[None]]] = None) -> None:
        """Bağlantı geri çağrı fonksiyonlarını ayarlar"""
        self._connect_callback = connect_callback
        self._disconnect_callback = disconnect_callback
    
    def update_strategy(self, strategy: ReconnectStrategy) -> None:
        """Yeniden bağlanma stratejisini günceller"""
        self.strategy = strategy
        self.stats.current_strategy = strategy
        self.attempt_count = 0  # Strateji değişince sayacı sıfırla
        logger.info(f"Yeniden bağlanma stratejisi güncellendi: {strategy}")
    
    def record_disconnection(self, reason: Optional[str] = None) -> None:
        """Bağlantı kaybını kaydeder"""
        if self.state != ReconnectState.DISCONNECTED:
            self.state = ReconnectState.DISCONNECTED
            self.stats.add_disconnection_reason(reason or "unknown")
            
            # Bağlantı geçmişine ekle
            self._connection_history.append({
                "event": "disconnect",
                "timestamp": time.time(),
                "reason": reason,
                "attempt": self.attempt_count
            })
            
            # Son 50 bağlantı olayını tut
            if len(self._connection_history) > 50:
                self._connection_history = self._connection_history[-50:]
            
            logger.info(f"Bağlantı kesildi, neden: {reason or 'bilinmiyor'}")
    
    async def try_reconnect(self) -> bool:
        """
        Bağlantı kesildikten sonra yeniden bağlanmayı dener.
        Seçilen stratejiye göre bekleme sürelerini hesaplar.
        """
        # Bağlantı geri çağrı fonksiyonu yoksa bağlanamaz
        if not self._connect_callback:
            logger.error("Bağlantı geri çağrı fonksiyonu ayarlanmamış.")
            self.state = ReconnectState.FAILED
            return False
        
        # Stratejik yeniden bağlanma yok ise hemen çık
        if self.strategy == ReconnectStrategy.NONE:
            logger.info("Yeniden bağlanma stratejisi NONE - bağlanma denenmiyor.")
            self.state = ReconnectState.FAILED
            return False
        
        # Maksimum deneme sayısı kontrolü
        if self.max_attempts > 0 and self.attempt_count >= self.max_attempts:
            logger.warning(f"Maksimum deneme sayısına ulaşıldı ({self.max_attempts}). Bağlantı kesildi.")
            self.state = ReconnectState.MAX_ATTEMPTS
            return False
        
        # Bekleme süresini hesapla
        backoff_time = self._calculate_backoff_time()
        self.stats.current_backoff_seconds = backoff_time
        
        # Durumu geri çekilme olarak ayarla ve bekle
        self.state = ReconnectState.BACKOFF
        logger.info(f"Yeniden bağlanma için bekleniyor: {backoff_time:.2f} saniye (deneme {self.attempt_count})")
        
        try:
            await asyncio.sleep(backoff_time)
        except asyncio.CancelledError:
            logger.info("Yeniden bağlanma işlemi iptal edildi.")
            return False
        
        # Bağlanmayı dene
        self.state = ReconnectState.CONNECTING
        
        # Bağlantı geçmişine ekle
        self._connection_history.append({
            "event": "reconnect_attempt",
            "timestamp": time.time(),
            "attempt": self.attempt_count,
            "strategy": self.strategy,
            "backoff_time": backoff_time
        })
        
        logger.info(f"Yeniden bağlanma deneniyor (Deneme {self.attempt_count})...")
        
        try:
            # Bağlantı zaman aşımı ile try_connect fonksiyonunu çağır
            success = await asyncio.wait_for(
                self._connect_callback(),
                timeout=self.connection_timeout
            )
            
            if success:
                self.state = ReconnectState.CONNECTED
                logger.info(f"Yeniden bağlantı başarılı (Deneme {self.attempt_count})")
                
                # Bağlantı geçmişine ekle
                self._connection_history.append({
                    "event": "reconnect_success",
                    "timestamp": time.time(),
                    "attempt": self.attempt_count,
                    "total_attempts": self.stats.connection_attempts
                })
                
                return True
            else:
                self.state = ReconnectState.FAILED
                logger.warning(f"Yeniden bağlantı başarısız (Deneme {self.attempt_count})")
                
                # Bağlantı geçmişine ekle
                self._connection_history.append({
                    "event": "reconnect_failed",
                    "timestamp": time.time(),
                    "attempt": self.attempt_count,
                    "reason": "connection_callback_returned_false"
                })
                
                return False
        except asyncio.TimeoutError:
            self.state = ReconnectState.FAILED
            logger.warning(f"Yeniden bağlantı zaman aşımı (Deneme {self.attempt_count})")
            
            # Bağlantı geçmişine ekle
            self._connection_history.append({
                "event": "reconnect_failed",
                "timestamp": time.time(),
                "attempt": self.attempt_count,
                "reason": "timeout"
            })
            
            return False
        except Exception as e:
            self.state = ReconnectState.FAILED
            logger.error(f"Yeniden bağlantı hatası: {str(e)} (Deneme {self.attempt_count})")
            
            # Bağlantı geçmişine ekle
            self._connection_history.append({
                "event": "reconnect_failed",
                "timestamp": time.time(),
                "attempt": self.attempt_count,
                "reason": str(e)
            })
            
            return False
    
    async def disconnect(self) -> None:
        """Bağlantıyı kapatır"""
        if self._disconnect_callback:
            try:
                await self._disconnect_callback()
            except Exception as e:
                logger.error(f"Bağlantı kapatma hatası: {str(e)}")
        
        if self.state != ReconnectState.DISCONNECTED:
            self.state = ReconnectState.DISCONNECTED
    
    async def auto_reconnect_loop(self) -> None:
        """
        Otomatik yeniden bağlanma döngüsü.
        Bağlantı kesilinceye kadar çalışır.
        """
        while self.state != ReconnectState.MAX_ATTEMPTS:
            if self.state in (ReconnectState.DISCONNECTED, ReconnectState.FAILED):
                success = await self.try_reconnect()
                
                # Başarısız ise ve stratejimiz varsa tekrar dene
                if not success and self.strategy != ReconnectStrategy.NONE:
                    # Max deneme sayısı kontrolü
                    if self.max_attempts > 0 and self.attempt_count >= self.max_attempts:
                        self.state = ReconnectState.MAX_ATTEMPTS
                        break
                    
                    # Strateji türüne göre tekrar
                    if self.strategy in (ReconnectStrategy.EXPONENTIAL, ReconnectStrategy.FIBONACCI):
                        continue  # Bu stratejiler zaten gittikçe artan bekleme süreleri kullanır
            
            # Bağlı veya bağlanma durumunda ise beklemeye devam et
            await asyncio.sleep(1.0)
    
    def reset(self) -> None:
        """Yeniden bağlanma durumunu ve sayaçları sıfırlar"""
        self.attempt_count = 0
        self.state = ReconnectState.CONNECTED
        self._last_connection_time = time.time()
    
    def get_stats(self, client_id: Optional[str] = None) -> ReconnectStats:
        """Yeniden bağlanma istatistiklerini döndürür"""
        # client_id kullanmıyoruz, ama ileride özelleştirilebilir
        return self.stats
    
    def get_connection_history(self) -> List[Dict[str, Any]]:
        """Bağlantı geçmişini döndürür"""
        return self._connection_history
    
    def reset_connection(self, client_id: str) -> None:
        """Belirli bir bağlantının durumunu sıfırlar"""
        # Burada bir client_id parametresi aldık, ancak şu an için tek bir örnek yönetiyoruz
        # Bu fonksiyon gelecekte birden fazla bağlantı yönetimi için genişletilebilir
        self.reset()
    
    def get_connection_info(self, client_id: str) -> Dict[str, Any]:
        """Belirli bir bağlantının bilgilerini döndürür"""
        # Bu da ileride genişletilebilir
        return {
            "client_id": client_id,
            "state": self.state,
            "attempt_count": self.attempt_count,
            "last_connection_time": self._last_connection_time,
            "strategy": self.strategy,
        }
    
    def _calculate_backoff_time(self) -> float:
        """Seçilen stratejiye göre bekleme süresini hesaplar"""
        delay = self.base_delay
        
        if self.strategy == ReconnectStrategy.EXPONENTIAL:
            # Üstel geri çekilme: base_delay * 2^attempt
            delay = self.base_delay * (2 ** (self.attempt_count - 1))
        
        elif self.strategy == ReconnectStrategy.FIBONACCI:
            # Fibonacci dizisi: base_delay * fib(attempt)
            fib_value = self._fibonacci(self.attempt_count)
            delay = self.base_delay * fib_value
        
        elif self.strategy == ReconnectStrategy.LINEAR:
            # Doğrusal artış: base_delay * attempt
            delay = self.base_delay * self.attempt_count
        
        elif self.strategy == ReconnectStrategy.RANDOM:
            # Rastgele aralık: base_delay ile max_delay arasında
            min_val = self.base_delay
            max_val = min(self.base_delay * (2 ** self.attempt_count), self.max_delay)
            delay = random.uniform(min_val, max_val)
        
        # Sabit strateji için base_delay kullanılır (zaten varsayılan)
        
        # Maksimum gecikme sınırı
        delay = min(delay, self.max_delay)
        
        # Rastgele jitter ekle
        if self.jitter > 0:
            jitter_amount = delay * self.jitter
            delay = max(0, delay + random.uniform(-jitter_amount, jitter_amount))
        
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Fibonacci sayısını hesaplar (önbellekli)"""
        if n in self._fibonacci_cache:
            return self._fibonacci_cache[n]
        
        # Büyük sayılar için iteratif hesaplama
        if n > 40:
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return a
        
        # Rekürsif hesaplama ve önbellekleme
        result = self._fibonacci(n-1) + self._fibonacci(n-2)
        self._fibonacci_cache[n] = result
        return result

# Singleton instance
reconnect_manager = ReconnectManager()

# Örnek kullanım için yardımcı fonksiyon
async def create_reconnect_manager(
    strategy: ReconnectStrategy = ReconnectStrategy.EXPONENTIAL,
    max_attempts: int = 0,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    connect_callback: Optional[Callable[[], Awaitable[bool]]] = None,
    disconnect_callback: Optional[Callable[[], Awaitable[None]]] = None
) -> ReconnectManager:
    """Yeni bir yeniden bağlanma yöneticisi oluşturur"""
    manager = ReconnectManager(
        strategy=strategy,
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay
    )
    
    if connect_callback:
        manager.set_callbacks(connect_callback, disconnect_callback)
    
    return manager