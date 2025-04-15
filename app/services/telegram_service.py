import os
import asyncio
from typing import Optional, List, Dict, Any, Union
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, UnauthorizedError, FloodWaitError, ChatAdminRequiredError
from telethon.tl.types import PeerUser, PeerChannel, PeerChat
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models import User, Group, MessageTemplate, MessageLog, TargetUser
from app.config import settings
from app.services.auto_reply_service import get_matching_reply
from app.crud import message_template as template_crud

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

    async def start_event_handlers(self):
        """Event handler'ları başlatır"""
        client = await self.get_client()
        
        # Handler'lar zaten başlatılmış mı kontrol et
        if hasattr(self, 'handlers_started') and self.handlers_started:
            return {"message": "Event handler'lar zaten çalışıyor"}
        
        # Özel mesajları dinle
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handle_dm_event(event):
            """Özel mesajları dinler ve otomatik yanıt gönderir"""
            try:
                # Mesaj içeriğini al
                message_text = event.message.text or event.message.message
                if not message_text:
                    return
                    
                # Gönderen kullanıcı bilgilerini al
                sender = await event.get_sender()
                sender_id = sender.id
                
                logger.info(f"DM alındı: {message_text[:30]}... Kimden: {sender_id}")
                
                # Otomatik yanıt kurallarını kontrol et
                reply_text = get_matching_reply(self.db, self.user_id, message_text)
                
                if reply_text:
                    # Yanıt gönder
                    await event.respond(reply_text)
                    logger.info(f"Otomatik DM yanıtı gönderildi: {reply_text[:30]}...")
                    
                    # Hedef kullanıcı kaydı varsa dm_sent olarak işaretle
                    targets = self.db.query(TargetUser).filter(
                        TargetUser.telegram_user_id == str(sender_id),
                        TargetUser.owner_id == self.user_id
                    ).all()
                    
                    for target in targets:
                        target.is_dm_sent = True
                    
                    if targets:
                        self.db.commit()
            except Exception as e:
                logger.error(f"DM işleme hatası: {str(e)}")
        
        # Gruplardaki yanıtları dinle
        @client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_private and e.message.reply_to))
        async def handle_group_reply_event(event):
            """Grup içindeki yanıtları dinler"""
            try:
                # Grup mesajını al
                message_text = event.message.text or event.message.message
                if not message_text:
                    return
                
                # Yanıt verilen mesajı al
                replied_to = await event.get_reply_message()
                if not replied_to:
                    return
                    
                # Mesaj kullanıcıya mı yanıt?
                me = await client.get_me()
                if replied_to.sender_id != me.id:
                    return
                
                # Gönderen kullanıcı bilgilerini al
                sender = await event.get_sender()
                sender_id = sender.id
                sender_username = sender.username if hasattr(sender, 'username') else None
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                
                # Grup bilgilerini al
                chat = await event.get_chat()
                chat_id = event.chat_id
                chat_title = chat.title if hasattr(chat, 'title') else "Grup"
                
                logger.info(f"Grup yanıtı alındı: {message_text[:30]}... Kimden: {sender_name}, Grup: {chat_title}")
                
                # Otomatik yanıt kurallarını kontrol et
                reply_text = get_matching_reply(self.db, self.user_id, message_text)
                
                if reply_text:
                    # Yanıt gönder
                    await event.respond(reply_text, reply_to=event.message)
                    logger.info(f"Otomatik grup yanıtı gönderildi: {reply_text[:30]}...")
                
                # Kullanıcıyı hedef olarak kaydet
                self._save_target_user(
                    sender_id, 
                    str(chat_id),
                    username=sender_username,
                    full_name=sender_name
                )
            except Exception as e:
                logger.error(f"Grup yanıtı işleme hatası: {str(e)}")
                
        # Gruplardaki etiketlemeleri dinle
        @client.on(events.NewMessage(incoming=True, func=lambda e: not e.is_private))
        async def handle_group_mention_event(event):
            """Gruptaki etiketlemeleri (@kullanıcı) dinler"""
            try:
                # Mesaj içeriğini al
                message_text = event.message.text or event.message.message
                if not message_text:
                    return
                
                # Kullanıcı bilgilerini al
                me = await client.get_me()
                my_username = me.username
                
                # Etiketleme var mı kontrol et
                if not my_username or f"@{my_username}" not in message_text:
                    return
                    
                # Gönderen kullanıcı bilgilerini al
                sender = await event.get_sender()
                sender_id = sender.id
                sender_username = sender.username if hasattr(sender, 'username') else None
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                
                # Grup bilgilerini al
                chat = await event.get_chat()
                chat_id = event.chat_id
                chat_title = chat.title if hasattr(chat, 'title') else "Grup"
                
                logger.info(f"Grup etiketi alındı: {message_text[:30]}... Kimden: {sender_name}, Grup: {chat_title}")
                
                # Otomatik yanıt kurallarını kontrol et
                reply_text = get_matching_reply(self.db, self.user_id, message_text)
                
                if reply_text:
                    # Yanıt gönder
                    await event.respond(reply_text, reply_to=event.message)
                    logger.info(f"Otomatik etiket yanıtı gönderildi: {reply_text[:30]}...")
                
                # Kullanıcıyı hedef olarak kaydet
                self._save_target_user(
                    sender_id, 
                    str(chat_id),
                    username=sender_username,
                    full_name=sender_name
                )
            except Exception as e:
                logger.error(f"Grup etiketi işleme hatası: {str(e)}")
        
        # Handler'ları işaretle
        self.handlers_started = True
        self.dm_handler = handle_dm_event
        self.reply_handler = handle_group_reply_event
        self.mention_handler = handle_group_mention_event
        
        return {"message": "Event handler'lar başlatıldı"}
    
    def _save_target_user(self, telegram_user_id, group_id, username=None, full_name=None):
        """Hedef kullanıcıyı veritabanına kaydeder"""
        try:
            # Kullanıcı daha önce kaydedilmiş mi kontrol et
            existing_target = self.db.query(TargetUser).filter(
                TargetUser.telegram_user_id == str(telegram_user_id),
                TargetUser.group_id == group_id,
                TargetUser.owner_id == self.user_id
            ).first()
            
            if existing_target:
                # Bilgileri güncelle
                if username:
                    existing_target.username = username
                if full_name:
                    existing_target.full_name = full_name
            else:
                # Yeni hedef kullanıcı oluştur
                new_target = TargetUser(
                    owner_id=self.user_id,
                    telegram_user_id=str(telegram_user_id),
                    group_id=group_id,
                    username=username,
                    full_name=full_name,
                    is_dm_sent=False,
                    created_at=datetime.utcnow()
                )
                self.db.add(new_target)
                
            self.db.commit()
            logger.info(f"Hedef kullanıcı kaydedildi: {telegram_user_id}")
        except Exception as e:
            logger.error(f"Hedef kullanıcı kaydetme hatası: {str(e)}")
            
    async def stop_event_handlers(self):
        """Event handler'ları durdurur"""
        client = await self.get_client()
        
        if hasattr(self, 'handlers_started') and self.handlers_started:
            # Handler'ları kaldır
            client.remove_event_handler(self.dm_handler)
            client.remove_event_handler(self.reply_handler)
            client.remove_event_handler(self.mention_handler)
            
            self.handlers_started = False
            return {"message": "Event handler'lar durduruldu"}
        
        return {"message": "Event handler'lar zaten çalışmıyor"}
        
    async def start_scheduled_sender(self):
        """
        Zamanlanmış mesaj gönderici başlatır.
        Bu fonksiyon, kullanıcının seçili gruplarına aktif broadcast mesajlarını
        belirlenen aralıklarla otomatik olarak gönderir.
        """
        # Zaten çalışıyor mu kontrol et
        if hasattr(self, 'scheduled_sender_running') and self.scheduled_sender_running:
            return {"message": "Zamanlanmış gönderici zaten çalışıyor"}
        
        self.scheduled_sender_running = True
        self.stop_scheduled_sender = False
        
        logger.info(f"Kullanıcı {self.user_id} için zamanlanmış gönderici başlatılıyor")
        
        try:
            # Ana döngü
            while not self.stop_scheduled_sender:
                try:
                    # Telegram client'ı hazırla
                    client = await self.get_client()
                    
                    # Kullanıcının seçili gruplarını al
                    selected_groups = self.db.query(Group).filter(
                        Group.user_id == self.user_id,
                        Group.is_selected == True,
                        Group.is_active == True
                    ).all()
                    
                    if not selected_groups:
                        logger.info(f"Kullanıcı {self.user_id} için seçili grup bulunamadı")
                        await asyncio.sleep(60)  # 1 dakika bekleyip tekrar dene
                        continue
                    
                    # Broadcast tipindeki aktif mesaj şablonlarını al
                    active_templates = self.db.query(MessageTemplate).filter(
                        MessageTemplate.user_id == self.user_id,
                        MessageTemplate.is_active == True,
                        MessageTemplate.message_type == "broadcast"
                    ).all()
                    
                    if not active_templates:
                        logger.info(f"Kullanıcı {self.user_id} için aktif broadcast şablonu bulunamadı")
                        await asyncio.sleep(60)  # 1 dakika bekleyip tekrar dene
                        continue
                    
                    # Her şablon için kontrol yap
                    for template in active_templates:
                        # Son gönderim zamanını kontrol et
                        last_log = self.db.query(MessageLog).filter(
                            MessageLog.user_id == self.user_id,
                            MessageLog.message_template_id == template.id,
                            MessageLog.status == "success"
                        ).order_by(MessageLog.sent_at.desc()).first()
                        
                        current_time = datetime.utcnow()
                        
                        # Son gönderim zamanı + interval_minutes sonrası şimdi veya geçmişte mi?
                        if last_log:
                            next_send_time = last_log.sent_at + timedelta(minutes=template.interval_minutes)
                            if next_send_time > current_time:
                                logger.info(f"Şablon {template.id} için gönderim zamanı gelmedi. Bekliyor... Sonraki gönderim: {next_send_time}")
                                continue
                        
                        # Gruplara mesaj gönder
                        for group in selected_groups:
                            try:
                                # Rate limiting için bekle
                                await asyncio.sleep(3)  # Minimum bekleme süresi
                                
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
                                    user_id=self.user_id,
                                    sent_at=current_time
                                )
                                self.db.add(log)
                                
                                # Grup bilgilerini güncelle
                                group.last_message = current_time
                                group.message_count += 1
                                
                                logger.info(f"Zamanlanmış mesaj gönderildi: Şablon {template.id}, Grup: {group.title}")
                                
                            except Exception as e:
                                # Hata durumunu logla
                                log = MessageLog(
                                    group_id=group.group_id,
                                    group_title=group.title,
                                    message_template_id=template.id,
                                    status="error",
                                    error_message=str(e)[:100],
                                    user_id=self.user_id,
                                    sent_at=current_time
                                )
                                self.db.add(log)
                                logger.error(f"Zamanlanmış mesaj hatası: {str(e)}, Şablon: {template.id}, Grup: {group.title}")
                        
                        # Değişiklikleri kaydet
                        self.db.commit()
                    
                    # Bir sonraki kontrol için bekle (5 dakika)
                    await asyncio.sleep(300)
                    
                except Exception as e:
                    logger.error(f"Zamanlanmış gönderici ana döngü hatası: {str(e)}")
                    await asyncio.sleep(60)  # Hata durumunda 1 dakika bekleyip tekrar dene
        
        except Exception as e:
            logger.error(f"Zamanlanmış gönderici kritik hata: {str(e)}")
        finally:
            self.scheduled_sender_running = False
            logger.info(f"Kullanıcı {self.user_id} için zamanlanmış gönderici durduruldu")
            
        return {"message": "Zamanlanmış gönderici durduruldu"}
    
    async def stop_scheduled_sender(self):
        """Zamanlanmış gönderiyi durdurur"""
        if hasattr(self, 'scheduled_sender_running') and self.scheduled_sender_running:
            self.stop_scheduled_sender = True
            # Durdurmanın etkili olması için bekle
            for _ in range(10):  # 5 saniye bekle
                if not self.scheduled_sender_running:
                    break
                await asyncio.sleep(0.5)
            return {"message": "Zamanlanmış gönderici durdurma talebi gönderildi"}
        
        return {"message": "Zamanlanmış gönderici zaten çalışmıyor"}
