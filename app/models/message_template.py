from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class MessageType(enum.Enum):
    BROADCAST = "broadcast"
    DIRECT = "direct"
    REPLY = "reply"
    AUTO_REPLY = "auto_reply"

class MessageTemplate(Base):
    __tablename__ = "message_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, index=True)
    content = Column(Text)
    message_type = Column(Enum(MessageType), default=MessageType.BROADCAST)
    is_active = Column(Boolean, default=True)
    interval_minutes = Column(Integer, default=60)  # Dakika cinsinden gönderim aralığı
    variables = Column(String, nullable=True)  # JSON string olarak değişkenler
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="message_templates")
    logs = relationship("MessageLog", back_populates="template")
    auto_reply_rules = relationship("AutoReplyRule", back_populates="template")
    schedules = relationship("Schedule", back_populates="template")
    messages = relationship("Message", back_populates="template")
    
    def __repr__(self):
        return f"<MessageTemplate {self.name}>" 