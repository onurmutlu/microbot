from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta
import hmac
import hashlib
import json
import urllib.parse
from typing import Dict, Any, Optional
import jwt
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models.user import User
from app.config import settings
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TelegramAuthData(BaseModel):
    auth_date: Optional[int] = None
    hash: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    query_id: Optional[str] = None
    initData: Optional[str] = None  # Telegram Mini App'in raw initData'sı

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: int
    refresh_token: str

class LogoutResponse(BaseModel):
    success: bool
    message: str

def verify_telegram_data(auth_data: Dict[str, Any]) -> bool:
    """Telegram'dan gelen verileri doğrular"""
    try:
        logger = logging.getLogger("auth.telegram")
        
        # Auth verisini kontrol et
        if not auth_data or not auth_data.get('hash'):
            logger.error("Hash bilgisi eksik veya auth_data boş")
            return False
        
        # Telegram init_data string formatında gelirse parse et
        if isinstance(auth_data, dict) and auth_data.get('initData') and isinstance(auth_data.get('initData'), str):
            raw_init_data = auth_data.get('initData')
            
            logger.info(f"Raw initData alındı: {raw_init_data[:100]}...")
            
            # init_data'yı parçalara ayır
            params = dict(urllib.parse.parse_qsl(raw_init_data))
            
            # Temel parametreleri al
            hash_value = params.get('hash')
            if not hash_value:
                logger.error("Hash değeri initData içinde bulunamadı")
                return False
                
            # User bilgisini al ve parse et
            user_data = params.get('user')
            try:
                if user_data:
                    user_data = json.loads(user_data)
            except Exception as e:
                logger.error(f"User verisi parse edilemedi: {str(e)}")
                return False
                
            # Yeni auth_data oluştur
            auth_data = {k: v for k, v in params.items() if k != 'user'}
            if user_data:
                auth_data['user'] = user_data
        
        # Hash değerini al
        received_hash = auth_data.get('hash')
        if not received_hash:
            logger.error("Hash değeri bulunamadı")
            return False
            
        # Gelen veri yapısına göre doğrulama string'i oluştur
        if 'user' in auth_data and isinstance(auth_data['user'], dict):
            # Telegram WebApp formatı: user ayrı bir anahtar
            data_check_string = '\n'.join([
                f"{k}={v}" for k, v in sorted(auth_data.items()) 
                if k != 'hash' and k != 'user'
            ])
            
            if auth_data.get('user'):
                data_check_string += f"\nuser={json.dumps(auth_data['user'])}"
        else:
            # Basit format: tüm anahtarlar aynı seviyede
            data_check_string = '\n'.join([
                f"{k}={v}" for k, v in sorted(auth_data.items()) 
                if k != 'hash'
            ])
        
        # Bot token'dan hash oluştur
        secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
        computed_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        # Hash doğrulama
        is_hash_valid = computed_hash == received_hash
        
        if not is_hash_valid:
            logger.error(f"Hash doğrulama başarısız. Alınan: {received_hash}, Hesaplanan: {computed_hash}")
            return False
            
        # Tarih kontrolü (en fazla 1 gün önce)
        auth_date = auth_data.get('auth_date')
        if not auth_date:
            logger.error("auth_date değeri bulunamadı")
            return False
            
        if isinstance(auth_date, str) and auth_date.isdigit():
            auth_date = int(auth_date)
        elif not isinstance(auth_date, int):
            logger.error(f"auth_date geçersiz format: {auth_date}")
            return False
            
        now = int(datetime.utcnow().timestamp())
        if now - auth_date > 86400:  # 24 saat (saniye)
            logger.error(f"auth_date çok eski: {auth_date}, şu an: {now}")
            return False
            
        logger.info("Telegram doğrulama başarılı ✓")
        return True
        
    except Exception as e:
        logger.error(f"Telegram doğrulama hatası: {str(e)}")
        return False

def create_tokens(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """JWT token oluşturur"""
    now = datetime.utcnow()
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = now + expires_delta
    
    # Access token için veri
    payload = {
        "sub": str(user_data.get("id")),
        "username": user_data.get("username", ""),
        "telegram_id": user_data.get("id"),
        "exp": expires_at,
        "iat": now,
        "type": "access"
    }
    
    # Refresh token için farklı süre
    refresh_expires = now + timedelta(days=30)
    refresh_payload = {
        "sub": str(user_data.get("id")),
        "exp": refresh_expires,
        "iat": now,
        "type": "refresh"
    }
    
    # Token oluştur
    access_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm="HS256")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": int(expires_at.timestamp()),
        "refresh_token": refresh_token
    }

@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(auth_data: TelegramAuthData, request: Request, db: Session = Depends(get_db)):
    """
    Telegram'dan gelen kimlik doğrulama verilerini doğrular ve JWT token üretir.
    
    Bu endpoint, Telegram Mini App'ten gönderilen initData'yı doğrular
    ve başarılı doğrulama durumunda kullanıcı için token oluşturur.
    
    Mini Uygulamadan gelen veriler iki şekilde kabul edilir:
    1. Ayrıştırılmış JSON formatında (auth_date, hash, user, vs.)
    2. Ham initData string olarak (Web App'ten doğrudan alınan query string)
    """
    # Log amaçlı bilgiler
    logger = logging.getLogger("auth.telegram")
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Telegram auth isteği alındı, IP: {client_ip}")
    
    # Auth verilerini dict'e dönüştür
    auth_dict = auth_data.dict(exclude_none=True)
    
    # Doğrulama
    if not verify_telegram_data(auth_dict):
        logger.error(f"Telegram doğrulama başarısız, IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram doğrulama başarısız"
        )
    
    # User bilgisini al
    user_data = None
    
    # initData string formatında mı geldi?
    if auth_dict.get('initData'):
        params = dict(urllib.parse.parse_qsl(auth_dict['initData']))
        user_json = params.get('user')
        if user_json:
            try:
                user_data = json.loads(user_json)
            except Exception as e:
                logger.error(f"User verisi parse edilemedi: {str(e)}")
    else:
        # Normal JSON formatında gelmiş
        user_data = auth_dict.get('user', {})
    
    if not user_data or not user_data.get('id'):
        logger.error("Kullanıcı bilgisi eksik veya geçersiz")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kullanıcı bilgisi eksik veya geçersiz"
        )
    
    telegram_id = user_data.get('id')
    logger.info(f"Telegram kullanıcısı doğrulandı: {telegram_id}")
    
    # Kullanıcı bilgilerini veritabanında kontrol et/güncelle
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        # Yeni kullanıcı oluştur
        user = User(
            telegram_id=telegram_id,
            username=user_data.get("username", ""),
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
            photo_url=user_data.get("photo_url", ""),
            auth_date=auth_dict.get("auth_date"),
            is_active=True,
            last_login=datetime.utcnow()
        )
        db.add(user)
        logger.info(f"Yeni kullanıcı oluşturuldu: {telegram_id}")
    else:
        # Mevcut kullanıcıyı güncelle
        user.last_login = datetime.utcnow()
        user.auth_date = auth_dict.get("auth_date")
        if user_data.get("username"):
            user.username = user_data.get("username")
        if user_data.get("photo_url"):
            user.photo_url = user_data.get("photo_url")
        if user_data.get("first_name"):
            user.first_name = user_data.get("first_name")
        if user_data.get("last_name"):
            user.last_name = user_data.get("last_name")
        logger.info(f"Mevcut kullanıcı güncellendi: {telegram_id}")
    
    db.commit()
    
    # Token oluştur
    tokens = create_tokens(user_data)
    
    # Metrics için giriş sayısını artır
    try:
        from app.services.monitoring.prometheus_metrics import metric_service
        metric_service.increment_login_count(str(user.id))
    except ImportError:
        pass  # Metrics servisi yoksa atla
    
    logger.info(f"Token oluşturuldu: Kullanıcı {telegram_id}")
    return tokens

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Mevcut kimliği doğrulanmış kullanıcının bilgilerini döndürür.
    
    Bu endpoint JWT token ile kimliği doğrulanmış kullanıcının
    ayrıntılı bilgilerini getirmek için kullanılır.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı kimliği doğrulanamadı"
        )
    
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "photo_url": current_user.photo_url,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }

@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    """
    Kullanıcı çıkış işlemini gerçekleştirir.
    
    Bu endpoint, kullanıcı oturumunu sonlandırmak için kullanılır.
    Token geçersiz kılma veya kara listeye alma işlemlerini gerçekleştirir.
    """
    # Token revoke işlemi için kara listeye alma
    # Bu örnekte Redis kullanıyoruz, ancak veritabanında da saklayabilirsiniz
    if settings.CACHE_ENABLED:
        try:
            from app.services.cache_service import cache_service
            
            # Kullanıcıdan token bilgisini al
            auth_header = request.headers.get("Authorization", "")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                
                # Token'ı kara listeye al - tokenin süresi kadar
                try:
                    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                    exp_time = payload.get("exp", 0)
                    current_time = int(datetime.utcnow().timestamp())
                    ttl = max(0, exp_time - current_time)
                    
                    # Redis'e kaydet
                    await cache_service.set(
                        f"blacklist:token:{token}", 
                        {"revoked_at": current_time}, 
                        expire=ttl
                    )
                except jwt.PyJWTError:
                    # Token zaten geçersiz, bir şey yapmaya gerek yok
                    pass
        except ImportError:
            pass  # Cache servisi yoksa atla
    
    return {"success": True, "message": "Çıkış işlemi başarılı"}

@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_access_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Yeni bir access token almak için refresh token kullanır.
    
    Bu endpoint, geçerli bir refresh token ile yeni bir access token oluşturur.
    """
    try:
        # Refresh token'ı doğrula
        payload = jwt.decode(
            refresh_token, 
            settings.SECRET_KEY, 
            algorithms=["HS256"]
        )
        
        # Doğru tip mi kontrol et
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz token tipi"
            )
        
        # Token'ın kara listede olup olmadığını kontrol et
        if settings.CACHE_ENABLED:
            try:
                from app.services.cache_service import cache_service
                blacklisted = await cache_service.get(f"blacklist:token:{refresh_token}")
                if blacklisted:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token geçersiz kılındı"
                    )
            except ImportError:
                pass  # Cache servisi yoksa atla
        
        # Kullanıcı ID'sini al
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kullanıcı bulunamadı"
            )
        
        # Kullanıcıyı kontrol et
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kullanıcı bulunamadı veya aktif değil"
            )
        
        # Yeni tokenlar oluştur
        user_data = {
            "id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
        # Token oluştur
        tokens = create_tokens(user_data)
        
        return tokens
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token süresi doldu"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token"
        ) 