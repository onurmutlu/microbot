from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import logging
from pydantic import BaseModel, Field
import os
import time
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, TelegramSession, SessionStatus
from app.services.telegram_service import TelegramService
from app.services.auth_service import get_current_active_user
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/telegram",
    tags=["telegram-sessions"]
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
    data: Optional[Dict[str, Any]] = None

class TelegramSessionResponse(BaseModel):
    id: int
    phone_number: str
    status: str
    created_at: datetime
    updated_at: datetime

class UserProfileResponse(BaseModel):
    plan: str
    max_sessions: int
    current_session_count: int

class DeleteSessionRequest(BaseModel):
    session_id: int = Field(..., description="Silinecek oturum ID'si")

# Session bilgilerini önbelleğe almak için geçici depolama (TTL mekanizması ile)
# Gerçek uygulamada Redis kullanılabilir
active_sessions = {}
# TTL süresi (saniye) - 15 dakika
SESSION_TTL = 15 * 60

# Zamananaşımına uğramış oturumları temizleme
def clean_expired_sessions():
    current_time = time.time()
    expired_phones = []
    
    for phone, session_data in active_sessions.items():
        expiry_time = session_data.get("expiry_time", 0)
        if current_time > expiry_time:
            expired_phones.append(phone)
    
    for phone in expired_phones:
        logger.info(f"Zamananaşımı: {phone} için aktif oturum temizlendi.")
        if phone in active_sessions:
            del active_sessions[phone]

@router.post("/start-login", response_model=TelegramResponse, operation_id="telegram_start_login")
async def start_telegram_login(
    request: TelegramLoginRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Telegram oturum başlatma işlemi için ilk adım.
    Kullanıcıdan API_ID, API_HASH ve telefon numarası alır ve doğrulama kodu gönderir.
    
    - **api_id**: Telegram API ID
    - **api_hash**: Telegram API Hash
    - **phone**: Telefon numarası (ülke kodu ile)
    """
    try:
        # Önce zamananaşımı kontrolü
        clean_expired_sessions()
        
        # Mevcut oturum sayısını kontrol et
        current_sessions_count = db.query(TelegramSession).filter(
            TelegramSession.user_id == current_user.id,
            TelegramSession.status == SessionStatus.ACTIVE
        ).count()
        
        # Kullanıcının maksimum oturum sınırını kontrol et
        if current_sessions_count >= current_user.max_sessions:
            return TelegramResponse(
                success=False,
                message=f"Hesap ekleme limitine ulaştınız (maksimum {current_user.max_sessions} hesap)."
            )
            
        # Aynı telefon numarasıyla kayıtlı session var mı kontrol et
        existing_session = db.query(TelegramSession).filter(
            TelegramSession.phone_number == request.phone,
            TelegramSession.user_id == current_user.id
        ).first()
        
        if existing_session and existing_session.status == SessionStatus.ACTIVE:
            return TelegramResponse(
                success=False,
                message=f"Bu telefon numarası ({request.phone}) zaten hesabınıza eklenmiş."
            )
            
        # TelegramService oluştur
        telegram_service = TelegramService(db, current_user.id)
        
        # Oturum oluştur ve doğrulama kodu gönder
        result = await telegram_service.create_session(
            api_id=request.api_id,
            api_hash=request.api_hash,
            phone=request.phone
        )
        
        # Telefonun kaydı
        current_time = time.time()
        active_sessions[request.phone] = {
            "telegram_service": telegram_service,
            "api_id": request.api_id,
            "api_hash": request.api_hash,
            "user_id": current_user.id,
            "created_at": current_time,
            "expiry_time": current_time + SESSION_TTL
        }
        
        # Eğer var olan session kaydı varsa status'u güncelle
        if existing_session:
            existing_session.status = SessionStatus.PENDING
            existing_session.api_id = request.api_id
            existing_session.api_hash = request.api_hash
            existing_session.updated_at = datetime.utcnow()
            db.commit()
        
        if result.get("success", True):
            # Başarılı sonuç, doğrulama kodu gönderildi
            logger.info(f"Login başlatıldı: {request.phone} - Doğrulama kodu gönderildi")
            return TelegramResponse(
                success=True,
                message="Doğrulama kodu telefonunuza gönderildi",
                data={}
            )
        else:
            # Hata durumu
            error_msg = result.get("message", "Oturum başlatma sırasında bir hata oluştu")
            logger.error(f"Login hatası: {request.phone} - {error_msg}")
            
            # Hata durumunda TelegramSession tablosuna kaydet
            if not existing_session:
                error_session = TelegramSession(
                    user_id=current_user.id,
                    phone_number=request.phone,
                    api_id=request.api_id,
                    api_hash=request.api_hash,
                    status=SessionStatus.ERROR,
                    last_error=error_msg,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(error_session)
                db.commit()
            
            return TelegramResponse(
                success=False,
                message=error_msg
            )
            
    except Exception as e:
        logger.error(f"Login hatası: {str(e)}")
        return TelegramResponse(
            success=False,
            message=f"Oturum başlatma sırasında bir hata oluştu: {str(e)}"
        )

@router.post("/confirm-code", response_model=TelegramResponse, operation_id="telegram_confirm_code")
async def confirm_telegram_code(
    request: TelegramCodeConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Telegram SMS doğrulama kodunu onaylama.
    
    - **phone**: Telefon numarası (start-login adımında kullanılan)
    - **code**: Gelen SMS doğrulama kodu
    """
    try:
        # Önce zamananaşımı kontrolü
        clean_expired_sessions()
        
        # Telefon numarası için aktif oturum yok mu?
        if request.phone not in active_sessions:
            return TelegramResponse(
                success=False,
                message="Oturum zamananaşımına uğradı veya başlatılmadı. Lütfen tekrar oturum başlatın."
            )
        
        # Kullanıcı doğrulaması
        if active_sessions[request.phone]["user_id"] != current_user.id:
            return TelegramResponse(
                success=False,
                message="Bu oturuma erişim izniniz yok."
            )
        
        # Önceki adımdan TelegramService'i al
        telegram_service = active_sessions[request.phone]["telegram_service"]
        
        # Doğrulama kodunu kontrol et
        result = await telegram_service.verify_session(code=request.code)
        
        if result.get("success", False):
            # Kod doğrulama başarılı, session kaydedildi
            session_string = result.get("session")
            
            # Kullanıcının mevcut session kaydını kontrol et
            existing_session = db.query(TelegramSession).filter(
                TelegramSession.user_id == current_user.id,
                TelegramSession.phone_number == request.phone
            ).first()
            
            if existing_session:
                # Var olan session'ı güncelle
                existing_session.status = SessionStatus.ACTIVE
                existing_session.session_string = session_string
                existing_session.session_name = f"session_{existing_session.id}"
                existing_session.last_error = None
                existing_session.updated_at = datetime.utcnow()
                db.commit()
                
                session_id = existing_session.id
            else:
                # Yeni session kaydı oluştur
                new_session = TelegramSession(
                    user_id=current_user.id,
                    phone_number=request.phone,
                    api_id=active_sessions[request.phone]["api_id"],
                    api_hash=active_sessions[request.phone]["api_hash"],
                    session_string=session_string,
                    status=SessionStatus.ACTIVE,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_session)
                db.commit()
                
                # Session name oluştur ve güncelle
                new_session.session_name = f"session_{new_session.id}"
                db.commit()
                
                session_id = new_session.id
            
            logger.info(f"Oturum başarıyla doğrulandı: {request.phone} (Kullanıcı: {current_user.id})")
            
            # Aktif oturumlardan temizle
            del active_sessions[request.phone]
            
            return TelegramResponse(
                success=True,
                message="Oturum başarıyla başlatıldı",
                data={
                    "session_saved": True,
                    "session_id": session_id
                }
            )
        
        elif result.get("two_factor_required", False):
            # 2FA Şifresi gerekli - oturum süresini yenile
            current_time = time.time()
            active_sessions[request.phone]["expiry_time"] = current_time + SESSION_TTL
            
            logger.info(f"2FA gerekli: {request.phone} (Kullanıcı: {current_user.id})")
            return TelegramResponse(
                success=True,
                message="İki faktörlü doğrulama şifresi gerekli",
                data={
                    "requires_2fa": True
                }
            )
        
        else:
            # Hata durumu
            error_msg = result.get("message", "Doğrulama kodu geçersiz")
            logger.error(f"Kod doğrulama hatası: {request.phone} - {error_msg}")
            
            # Hata durumunda TelegramSession tablosuna kaydet/güncelle
            existing_session = db.query(TelegramSession).filter(
                TelegramSession.user_id == current_user.id,
                TelegramSession.phone_number == request.phone
            ).first()
            
            if existing_session:
                existing_session.status = SessionStatus.ERROR
                existing_session.last_error = error_msg
                existing_session.updated_at = datetime.utcnow()
                db.commit()
            
            return TelegramResponse(
                success=False,
                message=error_msg
            )
            
    except Exception as e:
        logger.error(f"Kod doğrulama hatası: {str(e)}")
        return TelegramResponse(
            success=False,
            message=f"Doğrulama sırasında bir hata oluştu: {str(e)}"
        )

@router.post("/confirm-2fa-password", response_model=TelegramResponse, operation_id="telegram_confirm_2fa_password")
async def confirm_2fa_password(
    request: Telegram2FARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    İki faktörlü doğrulama (2FA) şifresini doğrulama.
    
    - **phone**: Telefon numarası
    - **password**: İki faktörlü doğrulama şifresi
    """
    try:
        # Önce zamananaşımı kontrolü
        clean_expired_sessions()
        
        # Telefon numarası için aktif oturum yok mu?
        if request.phone not in active_sessions:
            return TelegramResponse(
                success=False,
                message="Oturum zamananaşımına uğradı veya başlatılmadı. Lütfen tekrar oturum başlatın."
            )
        
        # Kullanıcı doğrulaması
        if active_sessions[request.phone]["user_id"] != current_user.id:
            return TelegramResponse(
                success=False,
                message="Bu oturuma erişim izniniz yok."
            )
        
        # Önceki adımdan TelegramService'i al
        telegram_service = active_sessions[request.phone]["telegram_service"]
        
        # 2FA şifresini kontrol et
        result = await telegram_service.verify_session(password=request.password)
        
        if result.get("success", False):
            # 2FA doğrulama başarılı, session kaydedildi
            session_string = result.get("session")
            
            # Kullanıcının mevcut session kaydını kontrol et
            existing_session = db.query(TelegramSession).filter(
                TelegramSession.user_id == current_user.id,
                TelegramSession.phone_number == request.phone
            ).first()
            
            if existing_session:
                # Var olan session'ı güncelle
                existing_session.status = SessionStatus.ACTIVE
                existing_session.session_string = session_string
                existing_session.session_name = f"session_{existing_session.id}"
                existing_session.last_error = None
                existing_session.updated_at = datetime.utcnow()
                db.commit()
                
                session_id = existing_session.id
            else:
                # Yeni session kaydı oluştur
                new_session = TelegramSession(
                    user_id=current_user.id,
                    phone_number=request.phone,
                    api_id=active_sessions[request.phone]["api_id"],
                    api_hash=active_sessions[request.phone]["api_hash"],
                    session_string=session_string,
                    status=SessionStatus.ACTIVE,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_session)
                db.commit()
                
                # Session name oluştur ve güncelle
                new_session.session_name = f"session_{new_session.id}"
                db.commit()
                
                session_id = new_session.id
            
            logger.info(f"2FA başarıyla doğrulandı: {request.phone} (Kullanıcı: {current_user.id})")
            
            # Aktif oturumlardan temizle
            del active_sessions[request.phone]
            
            return TelegramResponse(
                success=True,
                message="İki faktörlü doğrulama başarılı, oturum başlatıldı",
                data={
                    "session_saved": True,
                    "session_id": session_id
                }
            )
        else:
            # Hata durumu
            error_msg = result.get("message", "İki faktörlü doğrulama şifresi geçersiz")
            logger.error(f"2FA doğrulama hatası: {request.phone} - {error_msg}")
            
            # Hata durumunda TelegramSession tablosuna kaydet/güncelle
            existing_session = db.query(TelegramSession).filter(
                TelegramSession.user_id == current_user.id,
                TelegramSession.phone_number == request.phone
            ).first()
            
            if existing_session:
                existing_session.status = SessionStatus.ERROR
                existing_session.last_error = error_msg
                existing_session.updated_at = datetime.utcnow()
                db.commit()
            
            return TelegramResponse(
                success=False,
                message=error_msg
            )
            
    except Exception as e:
        logger.error(f"2FA doğrulama hatası: {str(e)}")
        return TelegramResponse(
            success=False,
            message=f"Doğrulama sırasında bir hata oluştu: {str(e)}"
        )

@router.get("/list-sessions", response_model=List[TelegramSessionResponse])
async def list_telegram_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcının bağlı olduğu tüm Telegram hesaplarını listeler.
    """
    try:
        # Kullanıcının tüm oturumlarını getir
        sessions = db.query(TelegramSession).filter(
            TelegramSession.user_id == current_user.id
        ).order_by(TelegramSession.created_at.desc()).all()
        
        session_list = [
            TelegramSessionResponse(
                id=session.id,
                phone_number=session.phone_number,
                status=session.status.value,
                created_at=session.created_at,
                updated_at=session.updated_at
            ) for session in sessions
        ]
        
        return session_list
    except Exception as e:
        logger.error(f"Oturum listeleme hatası: {str(e)}")
        return TelegramResponse(
            success=False,
            message=f"Oturumlar listelenirken bir hata oluştu: {str(e)}"
        )

@router.delete("/delete-session", status_code=status.HTTP_204_NO_CONTENT)
async def delete_telegram_session(
    request: DeleteSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Belirtilen Telegram oturumunu siler.
    
    - **session_id**: Silinecek oturum ID'si
    """
    try:
        # Oturumu bul
        session = db.query(TelegramSession).filter(
            TelegramSession.id == request.session_id,
            TelegramSession.user_id == current_user.id
        ).first()
        
        if not session:
            return TelegramResponse(
                success=False,
                message=f"ID'si {request.session_id} olan oturum bulunamadı."
            )
        
        # Session dosyasını sil (eğer varsa)
        session_path = os.path.join(settings.SESSION_DIR, f"session_{session.id}.session")
        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                logger.info(f"Session dosyası silindi: {session_path}")
            except Exception as e:
                logger.error(f"Session dosyası silinirken hata: {str(e)}")
        
        # Veritabanından oturumu sil
        db.delete(session)
        db.commit()
        
        logger.info(f"Oturum silindi: ID={session.id}, Telefon={session.phone_number}, Kullanıcı={current_user.id}")
        
        return TelegramResponse(
            success=True,
            message="Oturum başarıyla silindi",
            data={}
        )
    except Exception as e:
        logger.error(f"Oturum silme hatası: {str(e)}")
        return TelegramResponse(
            success=False,
            message=f"Oturum silinirken bir hata oluştu: {str(e)}"
        )

@router.get("/user/profile", response_model=UserProfileResponse)
async def get_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcının profil bilgilerini ve abonelik durumunu döndürür.
    """
    try:
        # Aktif oturum sayısını hesapla
        current_session_count = db.query(TelegramSession).filter(
            TelegramSession.user_id == current_user.id,
            TelegramSession.status == SessionStatus.ACTIVE
        ).count()
        
        profile_data = UserProfileResponse(
            plan=current_user.plan.value,
            max_sessions=current_user.max_sessions,
            current_session_count=current_session_count
        )
        
        return profile_data
    except Exception as e:
        logger.error(f"Profil bilgisi getirme hatası: {str(e)}")
        return TelegramResponse(
            success=False,
            message=f"Profil bilgileri alınırken bir hata oluştu: {str(e)}"
        ) 