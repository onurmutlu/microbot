import logging
import asyncio
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat
from datetime import datetime

from app.models.group import Group
from app.models.telegram_session import TelegramSession, SessionStatus
from app.database import get_db

logger = logging.getLogger(__name__)

async def discover_and_save_groups(db: Session, user_id: int, session_id: int) -> List[Dict[str, Any]]:
    """
    Kullanıcının Telegram hesabından (session) gruplarını çeker ve veritabanına kaydeder
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID
        session_id: Telegram oturum ID
        
    Returns:
        Keşfedilen grupların listesi
    """
    try:
        # Session kontrolü
        session = db.query(TelegramSession).filter(
            TelegramSession.id == session_id,
            TelegramSession.user_id == user_id,
            TelegramSession.status == SessionStatus.ACTIVE
        ).first()
        
        if not session:
            logger.error(f"Aktif oturum bulunamadı: user_id={user_id}, session_id={session_id}")
            return []
        
        # Telethon istemcisini hazırla
        client = TelegramClient(
            StringSession(session.session_string),
            session.api_id,
            session.api_hash
        )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error(f"Oturum yetkili değil: session_id={session_id}")
            await client.disconnect()
            return []
        
        # Grupları keşfet
        discovered_groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                entity = dialog.entity
                
                # Grup bilgilerini al
                group_id = entity.id
                group_name = entity.title if hasattr(entity, 'title') else "İsimsiz Grup"
                username = entity.username if hasattr(entity, 'username') else None
                
                # Üye sayısını al
                try:
                    members_count = entity.participants_count if hasattr(entity, 'participants_count') else None
                except:
                    members_count = None
                
                # Veritabanında kontrol et
                existing_group = db.query(Group).filter(
                    Group.group_id == group_id,
                    Group.user_id == user_id,
                    Group.session_id == session_id
                ).first()
                
                if existing_group:
                    # Mevcut grubu güncelle
                    existing_group.group_name = group_name
                    existing_group.username = username
                    existing_group.members_count = members_count
                    existing_group.is_active = True
                    existing_group.updated_at = datetime.utcnow()
                else:
                    # Yeni grup oluştur
                    new_group = Group(
                        user_id=user_id,
                        session_id=session_id,
                        group_id=group_id,
                        group_name=group_name,
                        username=username,
                        members_count=members_count,
                        is_active=True
                    )
                    db.add(new_group)
                    logger.info(f"Yeni grup eklendi: user_id={user_id}, session_id={session_id}, group_name={group_name}")
                
                # Sonuç listesine ekle
                discovered_groups.append({
                    "group_id": group_id,
                    "group_name": group_name,
                    "username": username,
                    "members_count": members_count
                })
        
        # Değişiklikleri kaydet
        db.commit()
        
        # Bağlantıyı kapat
        await client.disconnect()
        
        return discovered_groups
        
    except Exception as e:
        logger.error(f"Grup keşif hatası: {str(e)}")
        return []

# Komut satırından çalıştırıldığında test amaçlı kullan
if __name__ == "__main__":
    from app.database import SessionLocal
    import sys
    
    if len(sys.argv) < 3:
        print("Kullanım: python -m app.discover_groups <user_id> <session_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    session_id = int(sys.argv[2])
    
    db = SessionLocal()
    
    try:
        loop = asyncio.get_event_loop()
        groups = loop.run_until_complete(discover_and_save_groups(db, user_id, session_id))
        print(f"{len(groups)} grup keşfedildi ve kaydedildi")
        for group in groups:
            print(f"- {group['group_name']} (ID: {group['group_id']}, Üye: {group['members_count']})")
    finally:
        db.close() 