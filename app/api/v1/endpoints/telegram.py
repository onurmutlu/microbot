from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import os
import logging
import json

from app.database import get_db
from app.models import TelegramSession, User, SessionStatus, License
from app.config import settings
from app.services.auth_service import get_current_user, require_auth

router = APIRouter(prefix="/telegram", tags=["Telegram Sessions"])

# Pydantic modelleri
class TelegramSessionResponse(BaseModel):
    id: int
    phone: str
    api_id: str
    api_hash: str
    status: str
    license_key: str
    created_at: datetime
    telegram_user_id: Optional[str] = None

class TelegramLoginRequest(BaseModel):
    phone: str
    api_id: str
    api_hash: str
    license_key: str

class TelegramLoginResponse(BaseModel):
    success: bool
    message: str
    session_id: Optional[int] = None
    code_required: bool = False

class TelegramProfileResponse(BaseModel):
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    photo_url: Optional[str]
    telegram_id: Optional[str]

class SetActiveSessionResponse(BaseModel):
    success: bool
    message: str
    session_id: int

logger = logging.getLogger("telegram_api")

@router.get("/sessions", response_model=List[TelegramSessionResponse])
async def get_user_sessions(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Kullanıcının Telegram oturumlarını getirir.
    """
    # Kullanıcıya ait oturumları bul
    sessions = db.query(TelegramSession).filter(TelegramSession.user_id == current_user.id).all()
    
    return [
        {
            "id": session.id,
            "phone": session.phone,
            "api_id": session.api_id,
            "api_hash": session.api_hash,
            "status": session.status.value,
            "license_key": session.license_key,
            "created_at": session.created_at,
            "telegram_user_id": session.telegram_user_id
        }
        for session in sessions
    ]

@router.post("/start-login", response_model=TelegramLoginResponse)
async def start_telegram_login(
    login_data: TelegramLoginRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Telegram girişi başlatır.
    
    Verilen lisans anahtarını doğrular ve yeni bir oturum oluşturur.
    """
    try:
        # Lisans kontrolü
        license = db.query(License).filter(License.key == login_data.license_key).first()
        
        if not license:
            return {
                "success": False,
                "message": "Geçersiz lisans anahtarı",
                "code_required": False
            }
        
        # Lisans aktif değil
        if not license.is_active:
            return {
                "success": False,
                "message": "Lisans aktif değil",
                "code_required": False
            }
        
        # Lisans süresi dolmuş
        if license.expiry_date < datetime.utcnow():
            # Süresi dolan lisansı otomatik devre dışı bırak
            license.is_active = False
            db.commit()
            
            return {
                "success": False,
                "message": "Lisans süresi dolmuş",
                "code_required": False
            }
        
        # Lisans zaten başka bir kullanıcı tarafından kullanılıyor mu?
        if license.user_id and license.user_id != current_user.id:
            return {
                "success": False,
                "message": "Bu lisans başka bir kullanıcı tarafından kullanılıyor",
                "code_required": False
            }
        
        # Lisansı kullanıcıya ata (eğer atanmamışsa)
        if not license.user_id:
            license.user_id = current_user.id
            license.used_by = current_user.phone or current_user.username
            db.commit()
        
        # Kullanıcının izin verilen maksimum oturum sayısı sınırına gelip gelmediğini kontrol et
        session_count = db.query(TelegramSession).filter(TelegramSession.user_id == current_user.id).count()
        if session_count >= current_user.max_sessions:
            return {
                "success": False,
                "message": f"Maksimum oturum sayısına ({current_user.max_sessions}) ulaştınız. Devam etmek için bir oturumu silin.",
                "code_required": False
            }
        
        # Telethon ile giriş işlemini başlat
        try:
            from telethon import TelegramClient
            from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError
            
            # Geçici bir client oluştur
            client = TelegramClient(
                f"sessions/temp_{login_data.phone}_{datetime.utcnow().timestamp()}",
                int(login_data.api_id),
                login_data.api_hash
            )
            
            await client.connect()
            
            # Telefon numarası kontrolü
            if not await client.is_user_authorized():
                await client.send_code_request(login_data.phone)
                await client.disconnect()
                
                # Oturumu veritabanında kaydet
                new_session = TelegramSession(
                    user_id=current_user.id,
                    phone=login_data.phone,
                    api_id=login_data.api_id,
                    api_hash=login_data.api_hash,
                    status=SessionStatus.INACTIVE,
                    license_key=login_data.license_key,
                    created_at=datetime.utcnow()
                )
                
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                
                return {
                    "success": True,
                    "message": "Doğrulama kodu gönderildi",
                    "session_id": new_session.id,
                    "code_required": True
                }
            else:
                # Oturum zaten yetkilendirilmiş
                await client.disconnect()
                
                return {
                    "success": False,
                    "message": "Bu telefon numarası zaten yetkilendirilmiş",
                    "code_required": False
                }
                
        except PhoneNumberInvalidError:
            return {
                "success": False,
                "message": "Geçersiz telefon numarası",
                "code_required": False
            }
        except Exception as e:
            logger.error(f"Telegram giriş hatası: {str(e)}")
            return {
                "success": False,
                "message": f"Giriş başlatılırken bir hata oluştu: {str(e)}",
                "code_required": False
            }
    
    except Exception as e:
        logger.error(f"Telegram giriş hatası: {str(e)}")
        return {
            "success": False,
            "message": f"İşlem sırasında bir hata oluştu: {str(e)}",
            "code_required": False
        }

@router.delete("/delete-session/{session_id}", status_code=status.HTTP_200_OK)
async def delete_telegram_session(
    session_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Telegram oturumunu siler.
    """
    # Oturumu bul
    session = db.query(TelegramSession).filter(
        TelegramSession.id == session_id,
        TelegramSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {session_id} olan oturum bulunamadı veya size ait değil"
        )
    
    try:
        # Oturuma bağlı dosyaları temizle
        if session.session_string:
            # Telethon session dosyasını sil (varsa)
            session_file = f"sessions/{session.phone}.session"
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception as e:
                    logger.error(f"Session dosyası silinirken hata: {str(e)}")
        
        # Veritabanından sil
        db.delete(session)
        db.commit()
        
        return {"success": True, "message": "Oturum başarıyla silindi"}
    
    except Exception as e:
        logger.error(f"Oturum silme hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Oturum silinirken bir hata oluştu: {str(e)}"
        )

@router.post("/set-active-session/{session_id}", response_model=SetActiveSessionResponse)
async def set_active_telegram_session(
    session_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Aktif Telegram oturumunu ayarlar.
    """
    # Oturumu bul
    session = db.query(TelegramSession).filter(
        TelegramSession.id == session_id,
        TelegramSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {session_id} olan oturum bulunamadı veya size ait değil"
        )
    
    # Oturum etkin durumda mı kontrol et
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yalnızca etkin oturumlar aktif olarak ayarlanabilir"
        )
    
    try:
        # Önce tüm oturumları inaktif yap
        db.query(TelegramSession).filter(
            TelegramSession.user_id == current_user.id,
            TelegramSession.id != session_id
        ).update({TelegramSession.status: SessionStatus.INACTIVE})
        
        # Bu oturumu aktif olarak işaretle
        session.status = SessionStatus.ACTIVE
        db.commit()
        
        return {
            "success": True,
            "message": "Oturum aktif olarak ayarlandı",
            "session_id": session.id
        }
    
    except Exception as e:
        logger.error(f"Oturum aktifleştirme hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Oturum aktifleştirilirken bir hata oluştu: {str(e)}"
        )

@router.get("/user/profile", response_model=TelegramProfileResponse)
async def get_telegram_user_profile(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Kullanıcının Telegram profil bilgilerini getirir.
    """
    # Kullanıcının aktif oturumunu bul
    session = db.query(TelegramSession).filter(
        TelegramSession.user_id == current_user.id,
        TelegramSession.status == SessionStatus.ACTIVE
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aktif Telegram oturumu bulunamadı"
        )
    
    try:
        from telethon import TelegramClient
        
        # Oturum stringi boşsa eski yöntemi kullan
        if not session.session_string:
            session_file = f"sessions/{session.phone}.session"
            
            if not os.path.exists(session_file):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Oturum dosyası bulunamadı"
                )
            
            client = TelegramClient(
                f"sessions/{session.phone}",
                int(session.api_id),
                session.api_hash
            )
        else:
            # String session kullan
            from telethon.sessions import StringSession
            client = TelegramClient(
                StringSession(session.session_string),
                int(session.api_id),
                session.api_hash
            )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Telegram oturumu yetkilendirilmemiş"
            )
        
        # Kullanıcı bilgilerini al
        me = await client.get_me()
        await client.disconnect()
        
        return {
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "phone": me.phone,
            "photo_url": None,  # Profil fotoğrafı almak için ekstra kod gerekli
            "telegram_id": str(me.id)
        }
    
    except Exception as e:
        logger.error(f"Profil bilgileri alma hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profil bilgileri alınırken bir hata oluştu: {str(e)}"
        ) 