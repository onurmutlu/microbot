from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import asyncio
from datetime import timedelta
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.schemas import UserCreate, UserLogin, VerifyCode, Token
from app.models import User
from app.services.auth_service import authenticate_user, create_access_token, get_password_hash
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
        raise HTTPException(status_code=400, detail="Kullanıcı adı zaten kullanılıyor")
    
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
    
    return {"message": "Kullanıcı başarıyla oluşturuldu"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
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
        "access_token": access_token,
        "token_type": "bearer",
        "telegram_login_required": session_result.get("login_required", False)
    }

@router.post("/telegram/auth")
async def telegram_auth(phone: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.create_session(phone=phone)
    return result

@router.post("/telegram/verify")
async def verify_code(data: VerifyCode, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.create_session(code=data.code)
    return result

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
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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
            return {"status": "success", "message": "Telegram oturumu başarıyla oluşturuldu"}
        elif result.get("two_factor_required"):
            return {"status": "2fa_required", "message": "İki faktörlü doğrulama gerekli"}
        else:
            return {"status": "error", "message": result.get("message", "Bir hata oluştu")}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
