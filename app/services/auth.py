from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy.orm import Session
import jwt
import hashlib
import os

class AuthService:
    def __init__(self) -> None:
        self.db: Session = SessionLocal()
        self.secret_key = settings.SECRET_KEY
        self.session_dir = "sessions"
        os.makedirs(self.session_dir, exist_ok=True)
        
    async def register(self, phone: str, api_id: int, api_hash: str) -> Dict[str, Any]:
        """Yeni kullanıcı kaydı"""
        try:
            # Telefon numarası kontrolü
            if self.db.query(User).filter_by(phone=phone).first():
                raise ValueError("Bu telefon numarası zaten kayıtlı")
                
            # Telegram oturumu oluştur
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            # Telefon doğrulama isteği gönder
            await client.send_code_request(phone)
            
            # Kullanıcıyı veritabanına kaydet
            user = User(
                phone=phone,
                api_id=api_id,
                api_hash=api_hash,
                is_active=False,
                created_at=datetime.utcnow()
            )
            self.db.add(user)
            self.db.commit()
            
            return {
                "user_id": user.id,
                "phone_code_hash": client.code_request.phone_code_hash
            }
            
        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            self.db.rollback()
            raise
            
    async def verify_phone(self, user_id: int, code: str) -> bool:
        """Telefon doğrulama"""
        try:
            user = self.db.query(User).filter_by(id=user_id).first()
            if not user:
                raise ValueError("Kullanıcı bulunamadı")
                
            client = TelegramClient(StringSession(), user.api_id, user.api_hash)
            await client.connect()
            
            # Kodu doğrula
            await client.sign_in(user.phone, code)
            
            # Session'ı kaydet
            session_string = client.session.save()
            session_file = os.path.join(self.session_dir, f"{user_id}.session")
            
            with open(session_file, "w") as f:
                f.write(session_string)
                
            # Kullanıcıyı aktif et
            user.is_active = True
            user.session_file = session_file
            user.verified_at = datetime.utcnow()
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Phone verification failed: {str(e)}")
            return False
            
    async def login(self, user_id: int) -> Optional[str]:
        """Kullanıcı girişi"""
        try:
            user = self.db.query(User).filter_by(id=user_id).first()
            if not user or not user.is_active:
                return None
                
            # JWT token oluştur
            token = jwt.encode({
                "user_id": user.id,
                "exp": datetime.utcnow() + timedelta(days=1)
            }, self.secret_key, algorithm="HS256")
            
            return token
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return None
            
    async def get_user(self, user_id: int) -> Optional[User]:
        """Kullanıcı bilgilerini getir"""
        return self.db.query(User).filter_by(id=user_id).first()
        
    async def update_user(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Kullanıcı bilgilerini güncelle"""
        try:
            user = self.db.query(User).filter_by(id=user_id).first()
            if not user:
                return False
                
            for key, value in data.items():
                setattr(user, key, value)
                
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"User update failed: {str(e)}")
            self.db.rollback()
            return False
            
    async def delete_user(self, user_id: int) -> bool:
        """Kullanıcıyı sil"""
        try:
            user = self.db.query(User).filter_by(id=user_id).first()
            if not user:
                return False
                
            # Session dosyasını sil
            if user.session_file and os.path.exists(user.session_file):
                os.remove(user.session_file)
                
            self.db.delete(user)
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"User deletion failed: {str(e)}")
            self.db.rollback()
            return False 