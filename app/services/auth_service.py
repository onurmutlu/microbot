from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError

from app.database import get_db
from app.models import User
from app.config import settings
from app.core.logging import logger
from app.services.cache_service import cache_service

# OAuth2 şeması oluşturulurken auto_error=False ayarı ile token yoksa hata vermemesini sağlıyoruz
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False
)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password)

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        if not AuthService.verify_password(password, user.password_hash):
            return False
        return user

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
        return encoded_jwt

    @staticmethod
    def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
        return user

    @staticmethod
    def get_current_active_user(current_user: User = Depends(get_current_user)):
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Pasif kullanıcı")
        return current_user

# Keep original functions for backward compatibility
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Pasif kullanıcı")
    return current_user

def get_current_user_optional(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme_optional)):
    """
    Kullanıcı kimlik doğrulamasını opsiyonel yapar.
    Token geçerli değilse None döndürür.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        return user
    except JWTError:
        return None
    except Exception:
        return None

# GraphQL API için isim uyumluluğu
get_optional_user = get_current_user_optional

class TokenPayload:
    def __init__(self, sub: str, exp: int, iat: Optional[int] = None, 
                 telegram_id: Optional[int] = None, username: Optional[str] = None,
                 token_type: Optional[str] = None):
        self.sub = sub  # subject (user_id)
        self.exp = exp  # expiration time
        self.iat = iat  # issued at time
        self.telegram_id = telegram_id  # Telegram user ID
        self.username = username  # Username
        self.token_type = token_type  # Token type (access/refresh)

async def verify_token_not_blacklisted(token: str) -> bool:
    """Token'ın kara listede olmadığını doğrular"""
    if settings.CACHE_ENABLED and cache_service._redis:
        blacklisted = await cache_service.get(f"blacklist:token:{token}")
        return not blacklisted
    return True  # Redis yoksa doğrulamayı atla

async def get_token_data(token: str) -> Optional[TokenPayload]:
    """Token verilerini doğrular ve içindeki verileri döndürür"""
    try:
        # Token doğrulama
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        
        # Payload doğrulama
        token_data = TokenPayload(
            sub=payload.get("sub"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            telegram_id=payload.get("telegram_id"),
            username=payload.get("username"),
            token_type=payload.get("type")
        )
        
        # Token tipini ve son kullanma tarihini kontrol et
        if token_data.token_type != "access":
            logger.warning(f"Geçersiz token tipi: {token_data.token_type}")
            return None
        
        # Token'ın kara listede olup olmadığını kontrol et
        if not await verify_token_not_blacklisted(token):
            logger.warning(f"Token kara listede bulundu: {token[:10]}...")
            return None
        
        return token_data
    except jwt.ExpiredSignatureError:
        logger.warning("Token süresi dolmuş")
        return None
    except Exception as e:  # JWTError ve ValidationError hatalarını kapsar
        logger.warning(f"Geçersiz token: {str(e)}")
        return None

async def get_current_user(
    request: Request, 
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """JWT token ile kimliği doğrulanmış mevcut kullanıcıyı döndürür"""
    try:
        # Token yoksa HTTP isteğinin header'ından almaya çalış
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                # Cookie'den token almayı dene
                token = request.cookies.get("access_token")
                if not token:
                    logger.debug("Token bulunamadı (header, cookie)")
                    return None
        
        # Token verilerini doğrula
        token_data = await get_token_data(token)
        if not token_data:
            logger.debug("Token doğrulama başarısız")
            return None
        
        # Kullanıcıyı veritabanından al - Önce user_id ile dene
        user = None
        if token_data.sub:
            user = db.query(User).filter(User.id == token_data.sub).first()
        
        # Eğer bulunamazsa telegram_id ile kontrol et
        if not user and token_data.telegram_id:
            user = db.query(User).filter(User.telegram_id == token_data.telegram_id).first()
            if user:
                logger.info(f"Kullanıcı telegram_id ile bulundu: {token_data.telegram_id}")
                
        if not user:
            logger.warning(f"Token'da bulunan kullanıcı bulunamadı. ID: {token_data.sub}, Telegram ID: {token_data.telegram_id}")
            return None
            
        # Kullanıcı aktif mi kontrol et
        if not user.is_active:
            logger.warning(f"Kullanıcı aktif değil: {user.id}")
            return None
            
        return user
    except Exception as e:
        logger.error(f"Kimlik doğrulama hatası: {str(e)}")
        return None

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Kimliği doğrulanmış ve aktif kullanıcıyı döndürür, yoksa hata fırlatır"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama başarısız",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı devre dışı bırakılmış"
        )
    return current_user

def require_auth(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """
    Endpoint'lerde kimlik doğrulama gerektiren bir decorator olarak kullanılır.
    Kimlik doğrulanmazsa 401 hatası fırlatır.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
    
async def validate_telegram_login(auth_data: Dict[str, Any]) -> bool:
    """
    Telegram'dan gelen login verilerini doğrular.
    
    Telegram Mini App'in initData hash'ini doğrular.
    Detaylar: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    import hashlib
    import hmac
    
    # Hash değerini al
    received_hash = auth_data.get("hash")
    if not received_hash:
        return False
        
    # Hash dışındaki tüm verileri al
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(auth_data.items())
        if key != "hash"
    )
    
    # HMAC-SHA-256 doğrulaması
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    computed_hash = hmac.new(
        secret_key, 
        data_check_string.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    # Hash doğrulama
    is_hash_valid = computed_hash == received_hash
    
    # Tarih kontrolü (1 gün)
    auth_date = auth_data.get("auth_date", 0)
    if isinstance(auth_date, str) and auth_date.isdigit():
        auth_date = int(auth_date)
    current_timestamp = int(datetime.utcnow().timestamp())
    is_date_valid = current_timestamp - auth_date < 86400  # 24 saat (saniye cinsinden)
    
    return is_hash_valid and is_date_valid
