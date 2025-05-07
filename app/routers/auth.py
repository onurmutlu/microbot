from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import asyncio
from datetime import timedelta, datetime
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import JSONResponse
import hashlib
import hmac
import time

from app.database import get_db
from app.schemas import UserCreate, UserLogin, VerifyCode, Token, TelegramLoginData
from app.models import User
from app.services.auth_service import authenticate_user, create_access_token, get_password_hash, get_current_active_user
from app.services.telegram_service import TelegramService
from app.config import settings

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

# Telethon auth için schema
class TelegramAuthRequest(BaseModel):
    api_id: str
    api_hash: str
    phone: str
    
class TelegramVerifyRequest(BaseModel):
    code: str
    password: Optional[str] = None

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Kullanıcı adı benzersiz olmalı
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Kullanıcı adı zaten kullanılıyor", "data": {}}
        )
    
    # Yeni kullanıcı oluştur
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        password_hash=hashed_password,
        api_id=user.api_id,
        api_hash=user.api_hash,
        phone=user.phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {"success": True, "message": "Kullanıcı başarıyla oluşturuldu", "data": {}}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "message": "Hatalı kullanıcı adı veya şifre", "data": {}},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Telegram oturumunu kontrol et
    telegram_service = TelegramService(db, user.id)
    session_result = await telegram_service.create_session()
    
    # Access token oluştur
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "success": True,
        "message": "Login successful",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "telegram_login_required": session_result.get("login_required", False)
        }
    }

@router.post("/telegram/auth")
async def telegram_auth(phone: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.create_session(phone=phone)
    return {"success": True, "message": "Authentication process started", "data": result}

@router.post("/telegram/verify")
async def verify_code(data: VerifyCode, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.create_session(code=data.code)
    return {"success": True, "message": "Verification completed", "data": result}

@router.post("/telegram/auth", status_code=status.HTTP_200_OK)
async def telegram_auth_new(data: TelegramAuthRequest, db: Session = Depends(get_db)):
    """
    Telegram hesabına giriş yapmak için kod isteği gönderir
    """
    try:
        # Telethon servisini başlat
        telegram_service = TelegramService(db, None)  # Kullanıcı henüz bilinmiyor
        
        # Parametreleri doğrudan servise geçir
        result = await telegram_service.create_session(
            api_id=data.api_id,
            api_hash=data.api_hash,
            phone=data.phone
        )
        
        return {"success": True, "message": "Authentication request sent", "data": result}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": str(e), "data": {}}
        )

@router.post("/telegram/verify", status_code=status.HTTP_200_OK)
async def telegram_verify(data: TelegramVerifyRequest, db: Session = Depends(get_db)):
    """
    Telegram doğrulama kodunu veya 2FA şifresini kontrol eder
    """
    try:
        # Telethon servisini başlat
        telegram_service = TelegramService(db, None)  # Kullanıcı henüz bilinmiyor
        
        # Kod ve şifreyi geçir
        result = await telegram_service.verify_session(
            code=data.code,
            password=data.password
        )
        
        if result.get("success"):
            return {"success": True, "message": "Telegram oturumu başarıyla oluşturuldu", "data": {}}
        elif result.get("two_factor_required"):
            return {"success": True, "message": "İki faktörlü doğrulama gerekli", "data": {"two_factor_required": True}}
        else:
            return {"success": False, "message": result.get("message", "Bir hata oluştu"), "data": {}}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": str(e), "data": {}}
        )

@router.post("/telegram-login", status_code=status.HTTP_200_OK)
async def telegram_login(data: TelegramLoginData, db: Session = Depends(get_db)):
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    
    check_data = data.dict(exclude={"hash"})
    check_string = '\n'.join(f"{k}={check_data[k]}" for k in sorted(check_data))
    
    # Hash doğrulama
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if expected_hash != data.hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz Telegram login hash")
    
    # Kullanıcı var mı kontrolü
    user = db.query(User).filter(User.id == data.id).first()
    
    if not user:
        # Yeni kullanıcı oluştur
        username = data.username or f"telegram_{data.id}"
        user = User(
            id=data.id,
            username=username,
            first_name=data.first_name,
            last_name=data.last_name,
            photo_url=data.photo_url,
            is_active=True,
            last_login=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Kullanıcı bilgilerini güncelle
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.username = data.username or user.username
        user.photo_url = data.photo_url or user.photo_url
        user.last_login = datetime.utcnow()
        user.is_active = True
        db.commit()
    
    # Token oluştur
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"token": access_token}
