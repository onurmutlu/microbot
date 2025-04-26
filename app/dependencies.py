from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time
import secrets
import hashlib
from redis import Redis

from app.database import SessionLocal
from app.services.auth_service import AuthService
from app.models import User
from app.config import settings

# Redis bağlantısı
redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=0,
    decode_responses=True
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Veritabanı bağlantısı
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Mevcut kullanıcıyı getir
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    user = auth_service.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Hesap devre dışı")
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Yeterli izne sahip değilsiniz")
    return current_user

# Rate limiting - IP bazlı
def rate_limit_ip(
    request: Request,
    limit: int = settings.RATE_LIMIT_PER_MINUTE,
    window: int = 60
):
    ip = request.client.host
    key = f"ratelimit:{ip}"
    
    current = redis_client.get(key)
    
    if current is not None and int(current) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla istek gönderdiniz. Lütfen daha sonra tekrar deneyin."
        )
    
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()

# Rate limiting - User bazlı
def rate_limit_user(
    current_user: User = Depends(get_current_user),
    limit: int = settings.RATE_LIMIT_PER_MINUTE,
    window: int = 60
):
    key = f"ratelimit:user:{current_user.id}"
    
    current = redis_client.get(key)
    
    if current is not None and int(current) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla istek gönderdiniz. Lütfen daha sonra tekrar deneyin."
        )
    
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()

# Güvenlik kontrolleri
def security_headers(request: Request, call_next):
    response = call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# CSRF koruma
def verify_csrf_token(request: Request, csrf_token: str):
    token_session = request.session.get("csrf_token")
    if not token_session or not csrf_token or token_session != csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF doğrulama hatası"
        )
    
    # Tek kullanımlık token yenileme
    new_token = secrets.token_hex(32)
    request.session["csrf_token"] = new_token
    return new_token

# API Anahtar doğrulama
def verify_api_key(api_key: str, db: Session = Depends(get_db)):
    # API anahtarını veritabanında ara
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
    api_key_record = db.query(ApiKey).filter(ApiKey.hashed_key == hashed_key).first()
    
    if not api_key_record or not api_key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geçersiz API anahtarı"
        )
    
    # Son kullanım kontrol
    if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API anahtarı süresi dolmuş"
        )
    
    # Kullanım sayısını güncelle
    api_key_record.usage_count += 1
    api_key_record.last_used_at = datetime.utcnow()
    db.commit()
    
    return api_key_record.user_id 