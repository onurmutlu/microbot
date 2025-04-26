from telethon import TelegramClient
from telethon.sessions import StringSession
from pathlib import Path
from app.core.config import settings
from app.core.logger import logger

class TelegramClientManager:
    def __init__(self):
        self.clients = {}
        self.session_dir = Path(settings.SESSION_DIR)
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_client(self, session_name: str) -> TelegramClient:
        """Belirtilen session için TelegramClient oluşturur veya mevcut olanı döndürür."""
        if session_name in self.clients:
            return self.clients[session_name]
        
        session_file = self.session_dir / f"{session_name}.session"
        session_string = None
        
        if session_file.exists():
            session_string = session_file.read_text()
        
        client = TelegramClient(
            StringSession(session_string),
            settings.TELEGRAM_API_ID,
            settings.TELEGRAM_API_HASH
        )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.warning(f"Session {session_name} için kullanıcı yetkilendirilmemiş")
            return None
        
        # Session string'i kaydet
        session_string = client.session.save()
        session_file.write_text(session_string)
        
        self.clients[session_name] = client
        return client
    
    async def disconnect_all(self):
        """Tüm bağlı client'ları kapatır."""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()

telegram_manager = TelegramClientManager() 