from typing import Optional, Dict, Any
from fastapi import WebSocket
from datetime import datetime, timedelta
import jwt
from app.core.config import settings
from app.core.logging import logger

class WebSocketSecurity:
    @staticmethod
    async def validate_message_size(message: Dict[str, Any]) -> bool:
        """Mesaj boyutunu kontrol et"""
        message_size = len(str(message).encode('utf-8'))
        return message_size <= settings.WS_MAX_MESSAGE_SIZE

    @staticmethod
    async def sanitize_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """Mesajı temizle ve güvenli hale getir"""
        sanitized = {}
        for key, value in message.items():
            if isinstance(value, str):
                # HTML ve script enjeksiyonlarını temizle
                sanitized[key] = value.replace('<', '&lt;').replace('>', '&gt;')
            else:
                sanitized[key] = value
        return sanitized

class WebSocketRateLimiter:
    def __init__(self) -> None:
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = 300  # 5 dakika

    async def check_rate_limit(self, websocket: WebSocket, user_id: str) -> bool:
        """Rate limiting kontrolü yap"""
        current_time = datetime.now()
        
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = {
                'message_count': 0,
                'last_reset': current_time,
                'blocked_until': None
            }
        
        user_limit = self.rate_limits[user_id]
        
        # Bloke durumunu kontrol et
        if user_limit['blocked_until'] and current_time < user_limit['blocked_until']:
            return False
        
        # Sayaç sıfırlama kontrolü
        if (current_time - user_limit['last_reset']).total_seconds() > 60:
            user_limit['message_count'] = 0
            user_limit['last_reset'] = current_time
        
        # Mesaj sayısını kontrol et
        if user_limit['message_count'] >= settings.WS_RATE_LIMIT:
            user_limit['blocked_until'] = current_time + timedelta(minutes=5)
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False
        
        user_limit['message_count'] += 1
        return True

    def cleanup_old_connections(self) -> None:
        """Eski bağlantıları temizle"""
        current_time = datetime.now()
        expired_users = [
            user_id for user_id, limit in self.rate_limits.items()
            if (current_time - limit['last_reset']).total_seconds() > 3600
        ]
        for user_id in expired_users:
            del self.rate_limits[user_id]

def decode_access_token(token: str) -> Dict[str, Any]:
    """JWT token'ı doğrula ve çöz"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.JWTError:
        raise ValueError("Invalid token")

websocket_rate_limiter = WebSocketRateLimiter() 