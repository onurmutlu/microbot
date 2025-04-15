import os
import asyncio
from typing import Optional, List, Dict, Any, Union
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, UnauthorizedError, FloodWaitError, ChatAdminRequiredError
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import User, Group, MessageTemplate, MessageLog
from app.config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.client = None
        self.user = self.db.query(User).filter(User.id == user_id).first()
        
    async def create_session(self, api_id=None, api_hash=None, phone=None, code=None, password=None):
        """Telegram oturumu oluşturur veya var olan oturumu kullanır"""
        # API bilgilerini kontrol et
        if api_id and api_hash and phone:
            # Yeni oturum başlat
            self.temp_api_id = api_id
            self.temp_api_hash = api_hash
            self.temp_phone = phone
            
            # Oturum oluştur
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            try:
                # Telefon numarasıyla doğrulama kodu gönder
                await client.send_code_request(phone)
                self.temp_client = client
                return {"message": "Doğrulama kodu telefonunuza gönderildi"}
            except Exception as e:
                await client.disconnect()
                return {"success": False, "message": f"Hata: {str(e)}"}
            
        return {"success": False, "message": "API ID, API Hash ve telefon numarası gerekli"}
        
    async def verify_session(self, code=None, password=None):
        """Doğrulama kodu veya şifre ile oturumu doğrular"""
        if not hasattr(self, 'temp_client') or not self.temp_client:
            return {"success": False, "message": "Önce auth endpoint'ini çağırmalısınız"}
        
        if not code:
            return {"success": False, "message": "Doğrulama kodu gerekli"}
        
        client = self.temp_client
        
        try:
            # Kodu kullanarak oturum aç
            await client.sign_in(self.temp_phone, code)
            # Oturum başarılı
            session_string = client.session.save()
            return {"success": True, "session": session_string}
        except SessionPasswordNeededError:
            # İki faktörlü doğrulama etkinse şifre iste
            if not password:
                return {"two_factor_required": True, "message": "İki faktörlü doğrulama etkin, şifre gerekli"}
            
            try:
                # Şifre ile giriş yap
                await client.sign_in(password=password)
                # Oturum başarılı
                session_string = client.session.save()
                return {"success": True, "session": session_string}
            except Exception as e:
                return {"success": False, "message": f"Şifre hatası: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": f"Doğrulama hatası: {str(e)}"}
        
    async def get_client(self) -> TelegramClient:
        """Aktif bir TelegramClient döner veya oluşturur"""
        if self.client and self.client.is_connected():
            if await self.client.is_user_authorized():
                return self.client
                
        if not self.user.session_string:
            raise ValueError("Oturum bulunamadı, giriş yapmalısınız")
            
        client = TelegramClient(StringSession(self.user.session_string), 
                              self.user.api_id, 
                              self.user.api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            raise ValueError("Oturum geçersiz, yeniden giriş yapmalısınız")
            
        self.client = client
        return client
    
    async def discover_groups(self) -> List[Dict[str, Any]]:
        """Kullanıcının üye olduğu grupları keşfeder ve veritabanına kaydeder"""
        client = await self.get_client()
        
        # Mevcut diyalogları al
        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                entity = dialog.entity
                
                # Grup bilgilerini al
                group_id = str(dialog.id)
                title = entity.title if hasattr(entity, 'title') else "Başlıksız Grup"
                username = entity.username if hasattr(entity, 'username') else None
                
                # Üye sayısını al (mümkünse)
                try:
                    member_count = entity.participants_count if hasattr(entity, 'participants_count') else None
                except:
                    member_count = None
                
                # Veritabanına ekle veya güncelle
                existing_group = self.db.query(Group).filter(
                    Group.group_id == group_id,
                    Group.user_id == self.user_id
                ).first()
                
                if existing_group:
                    existing_group.title = title
                    existing_group.username = username
                    existing_group.member_count = member_count
                    existing_group.is_active = True
                else:
                    new_group = Group(
                        group_id=group_id,
                        title=title,
                        username=username,
                        member_count=member_count,
                        is_active=True,
                        user_id=self.user_id
                    )
                    self.db.add(new_group)
                
                groups.append({
                    "group_id": group_id,
                    "title": title,
                    "username": username,
                    "member_count": member_count
                })
        
        self.db.commit()
        return groups
    
    async def select_groups(self, group_ids: List[str]) -> Dict[str, Any]:
        """Belirtilen grupları mesaj gönderimi için seçer"""
        # Önce tüm grupları seçimsiz yap
        self.db.query(Group).filter(Group.user_id == self.user_id).update(
            {"is_selected": False}
        )
        
        # Seçilen grupları işaretle
        for group_id in group_ids:
            group = self.db.query(Group).filter(
                Group.group_id == group_id,
                Group.user_id == self.user_id
            ).first()
            
            if group:
                group.is_selected = True
        
        self.db.commit()
        return {"message": f"{len(group_ids)} grup seçildi"}
    
    async def send_message(self, template_id: int, group_ids: List[str] = None) -> Dict[str, Any]:
        """Belirtilen gruplara mesaj gönderir"""
        client = await self.get_client()
        
        # Mesaj şablonunu al
        template = self.db.query(MessageTemplate).filter(
            MessageTemplate.id == template_id,
            MessageTemplate.user_id == self.user_id
        ).first()
        
        if not template:
            raise ValueError("Mesaj şablonu bulunamadı")
        
        # Grupları al
        query = self.db.query(Group).filter(Group.user_id == self.user_id)
        
        if group_ids:
            query = query.filter(Group.group_id.in_(group_ids))
        else:
            query = query.filter(Group.is_selected == True)
            
        groups = query.filter(Group.is_active == True).all()
        
        if not groups:
            return {"message": "Gönderilecek grup bulunamadı", "sent": 0}
        
        # Mesajları gönder
        success_count = 0
        error_count = 0
        
        for group in groups:
            try:
                # Rate limiting için bekle (5-15 saniye arası)
                await asyncio.sleep(5)  # Minimum bekleme süresi
                
                # Mesajı gönder
                await client.send_message(
                    int(group.group_id),
                    template.content
                )
                
                # Başarı durumunu kaydet
                log = MessageLog(
                    group_id=group.group_id,
                    group_title=group.title,
                    message_template_id=template.id,
                    status="success",
                    user_id=self.user_id
                )
                self.db.add(log)
                
                # Grup bilgilerini güncelle
                group.last_message = datetime.utcnow()
                group.message_count += 1
                
                success_count += 1
                
            except ChatAdminRequiredError:
                # Admin yetkisi gerektiğinde
                log = MessageLog(
                    group_id=group.group_id,
                    group_title=group.title,
                    message_template_id=template.id,
                    status="error",
                    error_message="Admin yetkisi gerekli",
                    user_id=self.user_id
                )
                self.db.add(log)
                
                # Grubu devre dışı bırak
                group.is_active = False
                error_count += 1
                
            except FloodWaitError as e:
                # Rate limit aşıldığında
                log = MessageLog(
                    group_id=group.group_id,
                    group_title=group.title,
                    message_template_id=template.id,
                    status="error",
                    error_message=f"Rate limit aşıldı: {e.seconds} saniye bekleyin",
                    user_id=self.user_id
                )
                self.db.add(log)
                
                # FloodWaitError bekleme süresi
                await asyncio.sleep(min(e.seconds, 60))  # Maksimum 60 saniye bekle
                error_count += 1
                
            except Exception as e:
                # Diğer hatalar
                log = MessageLog(
                    group_id=group.group_id,
                    group_title=group.title,
                    message_template_id=template.id,
                    status="error",
                    error_message=str(e)[:100],  # Hata mesajını 100 karakter ile sınırla
                    user_id=self.user_id
                )
                self.db.add(log)
                error_count += 1
        
        self.db.commit()
        return {
            "message": f"{success_count} grup mesajı başarıyla gönderildi, {error_count} hata",
            "success": success_count,
            "errors": error_count
        }
