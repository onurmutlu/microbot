from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.message_template import MessageTemplate
from app.models.scheduled_message import ScheduledMessage
import asyncio
import random

class MessageSender:
    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self.db: Session = SessionLocal()

    async def send_scheduled_message(self, template_id: int, group_id: int) -> bool:
        """Zamanlanmış mesajı gönder"""
        try:
            template = self.db.query(MessageTemplate).filter_by(id=template_id).first()
            if not template:
                raise ValueError(f"Template {template_id} not found")

            # Mesaj içeriğini oluştur
            message = self._prepare_message(template.content)
            
            # Mesajı gönder
            await self.client.send_message(group_id, message)
            
            # Gönderim kaydını oluştur
            scheduled = ScheduledMessage(
                template_id=template_id,
                group_id=group_id,
                sent_at=datetime.now(),
                status="sent"
            )
            self.db.add(scheduled)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending scheduled message: {str(e)}")
            return False

    def _prepare_message(self, template: str) -> str:
        """Mesaj şablonunu hazırla"""
        # Dinamik değişkenleri ekle
        variables = {
            "{date}": datetime.now().strftime("%d.%m.%Y"),
            "{time}": datetime.now().strftime("%H:%M"),
            "{random}": str(random.randint(1, 1000))
        }
        
        message = template
        for var, value in variables.items():
            message = message.replace(var, value)
            
        return message

    async def schedule_message(self, template_id: int, group_id: int, 
                             schedule_time: datetime) -> bool:
        """Yeni mesaj zamanla"""
        try:
            scheduled = ScheduledMessage(
                template_id=template_id,
                group_id=group_id,
                scheduled_at=schedule_time,
                status="scheduled"
            )
            self.db.add(scheduled)
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling message: {str(e)}")
            return False

    async def get_scheduled_messages(self, group_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Zamanlanmış mesajları getir"""
        try:
            query = self.db.query(ScheduledMessage)
            if group_id:
                query = query.filter_by(group_id=group_id)
                
            messages = query.all()
            
            return [{
                "id": m.id,
                "template_id": m.template_id,
                "group_id": m.group_id,
                "scheduled_at": m.scheduled_at,
                "sent_at": m.sent_at,
                "status": m.status
            } for m in messages]
            
        except Exception as e:
            logger.error(f"Error getting scheduled messages: {str(e)}")
            return []

    async def cancel_scheduled_message(self, message_id: int) -> bool:
        """Zamanlanmış mesajı iptal et"""
        try:
            message = self.db.query(ScheduledMessage).filter_by(id=message_id).first()
            if not message:
                raise ValueError(f"Message {message_id} not found")
                
            message.status = "cancelled"
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling scheduled message: {str(e)}")
            return False

    async def get_message_stats(self, template_id: int) -> Dict[str, Any]:
        """Mesaj istatistiklerini getir"""
        try:
            messages = self.db.query(ScheduledMessage).filter_by(template_id=template_id).all()
            
            total = len(messages)
            sent = len([m for m in messages if m.status == "sent"])
            scheduled = len([m for m in messages if m.status == "scheduled"])
            cancelled = len([m for m in messages if m.status == "cancelled"])
            
            return {
                "total": total,
                "sent": sent,
                "scheduled": scheduled,
                "cancelled": cancelled,
                "success_rate": (sent / total * 100) if total > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting message stats: {str(e)}")
            return {} 