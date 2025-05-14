from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging
import json
import urllib.parse
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.api.v1.endpoints.auth import verify_telegram_data, create_tokens, TelegramInitData

router = APIRouter(prefix="/miniapp", tags=["MiniApp"])

# MiniApp kullanıcı modeli
class MiniAppUserModel(BaseModel):
    id: int
    first_name: str
    auth_date: Optional[int] = None
    hash: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: Optional[bool] = None
    allows_write_to_pm: Optional[bool] = None

# MiniApp yanıt modeli
class MiniAppResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@router.post("/auth", response_model=MiniAppResponse)
async def miniapp_auth(data: TelegramInitData, request: Request, db: Session = Depends(get_db)):
    """
    Telegram MiniApp için özel kimlik doğrulama endpointi.
    TelegramInitData modelini doğrudan kullanır ve daha esnek bir yanıt formatı sağlar.
    """
    logger = logging.getLogger("miniapp.auth")
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"MiniApp auth isteği alındı, IP: {client_ip}")
    
    try:
        # initData'yı işle
        init_data = data.initData
        
        # İşlenmiş veriyi çıkart
        params = dict(urllib.parse.parse_qsl(init_data))
        user_json = params.get('user')
        user_data = {}
        
        if user_json:
            try:
                user_data = json.loads(user_json)
            except json.JSONDecodeError as e:
                logger.error(f"User JSON parse hatası: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Geçersiz user verisi"
                )
        
        # initDataUnsafe'ten user bilgisine bak
        if not user_data and data.initDataUnsafe and data.initDataUnsafe.get("user"):
            user_data = data.initDataUnsafe.get("user")
        
        # Doğrudan user alanından bilgiye bak
        if not user_data and data.user:
            user_data = data.user
        
        if not user_data or not user_data.get("id"):
            logger.error(f"Kullanıcı bilgisi bulunamadı, IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kullanıcı bilgisi bulunamadı"
            )
        
        # Doğrulama
        auth_dict = {
            "hash": params.get("hash"),
            "auth_date": params.get("auth_date"),
            "user": user_data
        }
        
        if not verify_telegram_data(auth_dict):
            # Alternatif doğrulama - initData doğrudan kendi metodu ile
            alt_auth = {"initData": init_data}
            if not verify_telegram_data(alt_auth):
                logger.error(f"Telegram doğrulama başarısız, IP: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Telegram doğrulama başarısız"
                )
        
        # Kullanıcıyı veritabanında bul veya oluştur
        telegram_id = str(user_data.get("id"))
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            # Yeni kullanıcı oluştur
            user = User(
                telegram_id=telegram_id,
                username=user_data.get("username", ""),
                first_name=user_data.get("first_name", ""),
                last_name=user_data.get("last_name", ""),
                photo_url=user_data.get("photo_url", ""),
                is_premium=user_data.get("is_premium", False),
                is_active=True,
                last_login=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Yeni kullanıcı oluşturuldu: {telegram_id}")
        else:
            # Kullanıcıyı güncelle
            user.last_login = datetime.utcnow()
            user.username = user_data.get("username", user.username)
            user.first_name = user_data.get("first_name", user.first_name)
            user.last_name = user_data.get("last_name", user.last_name)
            user.photo_url = user_data.get("photo_url", user.photo_url)
            user.is_premium = user_data.get("is_premium", user.is_premium)
            db.commit()
            logger.info(f"Kullanıcı güncellendi: {telegram_id}")
        
        # Token oluştur
        tokens = create_tokens(user_data)
        
        # Yanıtı oluştur
        return {
            "success": True,
            "message": "Kimlik doğrulama başarılı",
            "data": {
                "user": {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name
                },
                "tokens": tokens
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MiniApp auth hatası: {str(e)}")
        return {
            "success": False,
            "message": f"Kimlik doğrulama hatası: {str(e)}",
            "data": None
        }

@router.get("/user", response_model=MiniAppResponse)
async def get_miniapp_user(
    current_user: User = Depends(get_current_user)
):
    """
    Şu anki kimliği doğrulanmış MiniApp kullanıcısının bilgilerini döndürür
    """
    return {
        "success": True,
        "message": "Kullanıcı bilgileri alındı",
        "data": {
            "user": {
                "id": current_user.id,
                "telegram_id": current_user.telegram_id,
                "username": current_user.username,
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
                "photo_url": current_user.photo_url,
                "is_premium": current_user.is_premium,
                "is_active": current_user.is_active,
                "last_login": current_user.last_login.isoformat() if current_user.last_login else None
            }
        }
    }

@router.post("/validate", response_model=MiniAppResponse)
async def validate_miniapp_token(
    auth_header: Optional[str] = Query(None, alias="Authorization"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    MiniApp token'ını doğrular ve kullanıcı bilgilerini döndürür.
    Bu endpoint, frontend'ten gelen token'ın geçerli olup olmadığını kontrol etmek için kullanılır.
    """
    if not current_user:
        return {
            "success": False,
            "message": "Geçersiz token",
            "data": None
        }
    
    return {
        "success": True,
        "message": "Token geçerli",
        "data": {
            "user": {
                "id": current_user.id,
                "telegram_id": current_user.telegram_id,
                "username": current_user.username
            }
        }
    } 