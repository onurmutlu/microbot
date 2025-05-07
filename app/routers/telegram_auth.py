from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
from pydantic import BaseModel, Field
import os

from app.database import get_db
from app.models import User
from app.services.telegram_service import TelegramService
from app.services.auth_service import get_current_active_user, get_current_user_optional
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/telegram",
    tags=["telegram-auth"]
)

# Pydantic modelleri
class TelegramLoginRequest(BaseModel):
    api_id: str = Field(..., description="Telegram API ID")
    api_hash: str = Field(..., description="Telegram API Hash")
    phone: str = Field(..., description="Telefon numarası (ülke kodu ile)")

class TelegramCodeConfirmRequest(BaseModel):
    phone: str = Field(..., description="Telefon numarası (ülke kodu ile)")
    code: str = Field(..., description="SMS doğrulama kodu")

class Telegram2FARequest(BaseModel):
    phone: str = Field(..., description="Telefon numarası (ülke kodu ile)")
    password: str = Field(..., description="2FA şifresi")

class TelegramResponse(BaseModel):
    success: bool
    message: str
    requires_2fa: Optional[bool] = False
    session_saved: Optional[bool] = False

class ActiveSessionResponse(BaseModel):
    success: bool
    message: str
    has_active_session: bool
    phone: Optional[str] = None
    api_id: Optional[str] = None
    api_hash: Optional[str] = None

# Session bilgilerini önbelleğe almak için geçici depolama
# Gerçek uygulamada Redis veya veritabanı kullanılabilir
active_sessions = {}

@router.get("/active-session", response_model=ActiveSessionResponse)
async def get_active_session(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Kullanıcının aktif Telegram oturumunu kontrol eder.
    Token yoksa veya geçersizse boş bilgilerle cevap verilir.
    """
    try:
        # Kullanıcı oturum açmamışsa
        if not current_user:
            return ActiveSessionResponse(
                success=True,
                message="Oturum açılmamış",
                has_active_session=False
            )
            
        # Kullanıcının kayıtlı bir oturumu var mı?
        if current_user.session_string and current_user.api_id and current_user.api_hash and current_user.phone:
            return ActiveSessionResponse(
                success=True,
                message="Aktif oturum bulundu",
                has_active_session=True,
                phone=current_user.phone,
                api_id=current_user.api_id,
                api_hash=current_user.api_hash
            )
        
        return ActiveSessionResponse(
            success=True,
            message="Aktif oturum bulunamadı",
            has_active_session=False
        )
        
    except Exception as e:
        logger.error(f"Aktif oturum kontrolü hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Oturum kontrolü sırasında bir hata oluştu: {str(e)}"
        )

@router.post("/start-login", response_model=TelegramResponse)
async def start_telegram_login(
    request: TelegramLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Telegram oturum başlatma işlemi için ilk adım.
    Kullanıcıdan API_ID, API_HASH ve telefon numarası alır ve doğrulama kodu gönderir.
    
    - **api_id**: Telegram API ID
    - **api_hash**: Telegram API Hash
    - **phone**: Telefon numarası (ülke kodu ile)
    """
    try:
        # Eğer kullanıcı veritabanında varsa, onun ID'sini kullan
        user = db.query(User).filter(User.phone == request.phone).first()
        
        if user:
            user_id = user.id
        else:
            # Test için geçici kullanıcı ID'si (veritabanında yoksa)
            user_id = 0
        
        # TelegramService oluştur
        telegram_service = TelegramService(db, user_id)
        
        # Oturum oluştur ve doğrulama kodu gönder
        result = await telegram_service.create_session(
            api_id=request.api_id,
            api_hash=request.api_hash,
            phone=request.phone
        )
        
        # Telefonun kaydı
        active_sessions[request.phone] = {
            "telegram_service": telegram_service,
            "api_id": request.api_id,
            "api_hash": request.api_hash
        }
        
        if result.get("success", True):
            # Başarılı sonuç, doğrulama kodu gönderildi
            logger.info(f"Login başlatıldı: {request.phone} - Doğrulama kodu gönderildi")
            return TelegramResponse(
                success=True,
                message="Doğrulama kodu telefonunuza gönderildi"
            )
        else:
            # Hata durumu
            logger.error(f"Login hatası: {request.phone} - {result.get('message', 'Bilinmeyen hata')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Oturum başlatma sırasında bir hata oluştu")
            )
            
    except Exception as e:
        logger.error(f"Login hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Oturum başlatma sırasında bir hata oluştu: {str(e)}"
        )

@router.post("/confirm-code", response_model=TelegramResponse)
async def confirm_telegram_code(
    request: TelegramCodeConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Telegram SMS doğrulama kodunu onaylama.
    
    - **phone**: Telefon numarası (start-login adımında kullanılan)
    - **code**: Gelen SMS doğrulama kodu
    """
    try:
        # Telefon numarası için aktif oturum yok mu?
        if request.phone not in active_sessions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Önce oturum başlatmalısınız"
            )
        
        # Önceki adımdan TelegramService'i al
        telegram_service = active_sessions[request.phone]["telegram_service"]
        
        # Doğrulama kodunu kontrol et
        result = await telegram_service.verify_session(code=request.code)
        
        if result.get("success", False):
            # Kod doğrulama başarılı, session kaydedildi
            session_string = result.get("session")
            
            # Kullanıcı kaydı veya güncelleme
            user = db.query(User).filter(User.phone == request.phone).first()
            
            if user:
                # Kullanıcı var, session_string güncelle
                user.session_string = session_string
                user.is_active = True
            else:
                # Yeni kullanıcı oluştur
                new_user = User(
                    phone=request.phone,
                    api_id=active_sessions[request.phone]["api_id"],
                    api_hash=active_sessions[request.phone]["api_hash"],
                    session_string=session_string,
                    is_active=True
                )
                db.add(new_user)
            
            db.commit()
            logger.info(f"Oturum başarıyla doğrulandı: {request.phone}")
            
            # Aktif oturumlardan temizle
            del active_sessions[request.phone]
            
            return TelegramResponse(
                success=True,
                message="Oturum başarıyla başlatıldı",
                session_saved=True
            )
        
        elif result.get("two_factor_required", False):
            # 2FA Şifresi gerekli
            logger.info(f"2FA gerekli: {request.phone}")
            return TelegramResponse(
                success=True,
                message="İki faktörlü doğrulama şifresi gerekli",
                requires_2fa=True
            )
        
        else:
            # Hata durumu
            logger.error(f"Kod doğrulama hatası: {request.phone} - {result.get('message', 'Bilinmeyen hata')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Doğrulama kodu geçersiz")
            )
            
    except Exception as e:
        logger.error(f"Kod doğrulama hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doğrulama sırasında bir hata oluştu: {str(e)}"
        )

@router.post("/confirm-2fa-password", response_model=TelegramResponse)
async def confirm_2fa_password(
    request: Telegram2FARequest,
    db: Session = Depends(get_db)
):
    """
    İki faktörlü doğrulama (2FA) şifresini doğrulama.
    
    - **phone**: Telefon numarası
    - **password**: İki faktörlü doğrulama şifresi
    """
    try:
        # Telefon numarası için aktif oturum yok mu?
        if request.phone not in active_sessions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Önce oturum başlatmalısınız"
            )
        
        # Önceki adımdan TelegramService'i al
        telegram_service = active_sessions[request.phone]["telegram_service"]
        
        # 2FA şifresini kontrol et
        result = await telegram_service.verify_session(password=request.password)
        
        if result.get("success", False):
            # 2FA doğrulama başarılı, session kaydedildi
            session_string = result.get("session")
            
            # Kullanıcı kaydı veya güncelleme
            user = db.query(User).filter(User.phone == request.phone).first()
            
            if user:
                # Kullanıcı var, session_string güncelle
                user.session_string = session_string
                user.is_active = True
            else:
                # Yeni kullanıcı oluştur
                new_user = User(
                    phone=request.phone,
                    api_id=active_sessions[request.phone]["api_id"],
                    api_hash=active_sessions[request.phone]["api_hash"],
                    session_string=session_string,
                    is_active=True
                )
                db.add(new_user)
            
            db.commit()
            logger.info(f"2FA başarıyla doğrulandı: {request.phone}")
            
            # Aktif oturumlardan temizle
            del active_sessions[request.phone]
            
            return TelegramResponse(
                success=True,
                message="İki faktörlü doğrulama başarılı, oturum başlatıldı",
                session_saved=True
            )
        else:
            # Hata durumu
            logger.error(f"2FA doğrulama hatası: {request.phone} - {result.get('message', 'Bilinmeyen hata')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "İki faktörlü doğrulama şifresi geçersiz")
            )
            
    except Exception as e:
        logger.error(f"2FA doğrulama hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doğrulama sırasında bir hata oluştu: {str(e)}"
        ) 