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
from app.services.auto_reply_service import get_matching_reply, get_best_reply
from app.crud import message_template as template_crud

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.client = None
        self.user = self.db.query(User).filter(User.id == user_id).first()
        
        # Session klasörü yoksa oluştur
        os.makedirs(settings.SESSION_DIR, exist_ok=True)
        
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
        """
        Telethon client instance'ı oluşturur veya mevcut bir instance döndürür
        """
        if self.client and self.client.is_connected():
                return self.client
            
        # Session dosya yolu
        session_path = os.path.join(settings.SESSION_DIR, f"user_{self.user_id}")
        
        # Client oluştur
        self.client = TelegramClient(
            session_path,
            api_id=self.user.api_id,
            api_hash=self.user.api_hash
        )
        
        # Bağlantı kur
        await self.client.connect()
        
        # Oturum kontrolü
        if not await self.client.is_user_authorized():
            # Kayıtlı session string'i varsa kullan
            if self.user.session_string:
                try:
                    await self.client.session.set_dc(
                        self.user.session_string.split("__")[0],
                        self.user.session_string.split("__")[1],
                        self.user.session_string.split("__")[2]
                    )
                    logger.info(f"User {self.user_id} session string kullanılarak bağlanıldı")
                except Exception as e:
                    logger.error(f"Session string ile bağlantı hatası: {str(e)}")
                    
            # Session string yoksa yeni oturum aç
            if not await self.client.is_user_authorized():
                logger.info(f"User {self.user_id} için yeni oturum gerekiyor")
                raise Exception("Unauthorized: Send code first")
        
        return self.client
    
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
                    Group.telegram_id == group_id,
                    Group.user_id == self.user_id
                ).first()
                
                if existing_group:
                    existing_group.title = title
                    existing_group.username = username
                    existing_group.member_count = member_count
                    existing_group.is_active = True
                else:
                    new_group = Group(
                        telegram_id=group_id,
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
                Group.telegram_id == group_id,
                Group.user_id == self.user_id
            ).first()
            
            if group:
                group.is_selected = True
        
        self.db.commit()
        return {"message": f"{len(group_ids)} grup seçildi"}
    
    async def send_message(self, template_id: int, group_ids: List[str] = None) -> Dict[str, Any]:
        """
        Belirtilen gruplara mesaj gönderir
        
        Args:
            template_id: Gönderilecek mesaj şablonu ID'si
            group_ids: Hedef grup ID'leri (boş ise seçili gruplara gönderilir)
            
        Returns:
            Gönderim sonuçları
        """
        # Client'ı al
        client = await self.get_client()
        
        # Şablonu kontrol et
        template = template_crud.get_template_by_id(self.db, template_id)
        if not template or template.user_id != self.user_id:
            return {"error": "Mesaj şablonu bulunamadı"}
        
        # Grupları al
        if group_ids:
            groups = self.db.query(Group).filter(
                Group.user_id == self.user_id,
                Group.telegram_id.in_(group_ids),
                Group.is_active == True
            ).all()
        else:
            groups = self.db.query(Group).filter(
                Group.user_id == self.user_id,
                Group.is_selected == True,
                Group.is_active == True
            ).all()
        
        if not groups:
            return {"error": "Gönderilecek grup bulunamadı"}
        
        # Sonuçları tutacak liste
        results = []
        
        # Her gruba gönder
        for group in groups:
            try:
                # Mesajı gönder
                message = await client.send_message(
                    group.telegram_id,
                    template.content
                )
                
                # Log kaydet
                log = MessageLog(
                    user_id=self.user_id,
                    telegram_id=group.telegram_id,
                    target_user_id=None,
                    message_template_id=template.id,
                    message_content=message,
                    status="success",
                    error_message=None
                )
                self.db.add(log)
                self.db.commit()
                
                # Grup son mesaj zamanını güncelle
                group.last_message = datetime.utcnow()
                group.message_count += 1
                
                results.append({
                    "group_id": group.telegram_id,
                    "group_title": group.title,
                    "status": "success",
                    "message_id": message.id
                })
                
            except Exception as e:
                # Hata log'u
                log = MessageLog(
                    user_id=self.user_id,
                    telegram_id=group.telegram_id,
                    target_user_id=None,
                    message_template_id=template.id,
                    message_content=None,
                    status="error",
                    error_message=str(e)[:100],
                    sent_at=datetime.utcnow()
                )
                self.db.add(log)
                self.db.commit()
                
                results.append({
                    "group_id": group.telegram_id,
                    "group_title": group.title,
                    "status": "error",
                    "error": str(e)[:100]
                })
                
                logger.error(f"Mesaj gönderme hatası: {str(e)}")
        
        # Değişiklikleri kaydet
        self.db.commit()
        
        return {
            "template_id": template_id,
            "template_name": template.name,
            "group_count": len(groups),
            "success_count": len([r for r in results if r["status"] == "success"]),
            "error_count": len([r for r in results if r["status"] == "error"]),
            "results": results
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
                sender_username = sender.username if hasattr(sender, 'username') else None
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                
                logger.info(f"DM alındı: {message_text[:30]}... Kimden: {sender_id}")
                
                # Gelişmiş otomatik yanıt kurallarını kontrol et
                reply_text, meta = get_best_reply(self.db, self.user_id, message_text)
                
                if reply_text:
                    # Yanıt gönder
                    await event.respond(reply_text)
                    logger.info(f"Otomatik DM yanıtı gönderildi: {reply_text[:30]}... (Eşleşme tipi: {meta.get('match_type', 'bilinmiyor')})")
                    
                    # Hedef kullanıcı kaydı varsa dm_sent olarak işaretle
                    targets = self.db.query(TargetUser).filter(
                        TargetUser.telegram_user_id == str(sender_id),
                        TargetUser.owner_id == self.user_id
                    ).all()
                    
                    for target in targets:
                        target.is_dm_sent = True
                    
                    if targets:
                        self.db.commit()
                else:
                    logger.info(f"DM yanıtı bulunamadı: {message_text[:30]}...")
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
                
                # Gelişmiş otomatik yanıt kurallarını kontrol et
                reply_text, meta = get_best_reply(self.db, self.user_id, message_text)
                
                if reply_text:
                    # Yanıt içindeki dinamik alanları doldur
                    reply_vars = {
                        "name": sender_name,
                        "username": sender_username or "",
                        "group": chat_title
                    }
                    
                    # Metadatadaki değişkenleri ekle
                    if meta.get("match_type") == "regex" and meta.get("named_captures"):
                        reply_vars.update(meta["named_captures"])
                    
                    # Yanıt gönder
                    await event.respond(reply_text, reply_to=event.message)
                    logger.info(f"Otomatik grup yanıtı gönderildi: {reply_text[:30]}... (Eşleşme tipi: {meta.get('match_type', 'bilinmiyor')})")
                
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
                
                # Gelişmiş otomatik yanıt kurallarını kontrol et
                reply_text, meta = get_best_reply(self.db, self.user_id, message_text)
                
                if reply_text:
                    # Yanıt içindeki dinamik alanları doldur
                    reply_vars = {
                        "name": sender_name,
                        "username": sender_username or "",
                        "group": chat_title
                    }
                    
                    # Metadatadaki değişkenleri ekle
                    if meta.get("match_type") == "regex" and meta.get("named_captures"):
                        reply_vars.update(meta["named_captures"])
                    
                    # Yanıt gönder
                    await event.respond(reply_text, reply_to=event.message)
                    logger.info(f"Otomatik etiket yanıtı gönderildi: {reply_text[:30]}... (Eşleşme tipi: {meta.get('match_type', 'bilinmiyor')})")
                
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
    
    def _save_target_user(self, user_id, group_id, username=None, full_name=None):
        """
        Hedef kullanıcıyı veritabanına kaydeder (yoksa oluşturur)
        """
        target = self.db.query(TargetUser).filter(
            TargetUser.telegram_user_id == str(user_id),
            TargetUser.group_id == group_id,
            TargetUser.owner_id == self.user_id
        ).first()
        
        if not target:
            target = TargetUser(
                telegram_user_id=str(user_id),
                group_id=group_id,
                username=username,
                full_name=full_name,
                is_dm_sent=False,
                owner_id=self.user_id
            )
            self.db.add(target)
            self.db.commit()
            logger.info(f"Yeni hedef kullanıcı eklendi: {username or user_id} ({group_id})")
        
        return target
            
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
                                    int(group.telegram_id),
                                    template.content
                                )
                                
                                # Mesaj gönderme işlemini logla
                                log = MessageLog(
                                    user_id=self.user_id,
                                    telegram_id=group.telegram_id,
                                    target_user_id=None,
                                    message_template_id=template.id,
                                    message_content=None,
                                    status="success",
                                    error_message=None
                                )
                                self.db.add(log)
                                self.db.commit()
                                
                                # Grup bilgilerini güncelle
                                group.last_message = current_time
                                group.message_count += 1
                                
                                logger.info(f"Zamanlanmış mesaj gönderildi: Şablon {template.id}, Grup: {group.title}")
                                
                            except Exception as e:
                                # Hata durumunu logla
                                log = MessageLog(
                                    user_id=self.user_id,
                                    telegram_id=group.telegram_id,
                                    target_user_id=None,
                                    message_template_id=template.id,
                                    message_content=None,
                                    status="error",
                                    error_message=str(e)[:100],
                                    sent_at=current_time
                                )
                                self.db.add(log)
                                self.db.commit()
                                logger.error(f"Zamanlanmış mesaj hatası: {str(e)}, Şablon: {template.id}, Grup: {group.title}")
                    
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
