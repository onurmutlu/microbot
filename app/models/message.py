from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, JSON, BigInteger
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime
import enum

class MessageType(enum.Enum):
    TEXT = "text"
    MEDIA = "media"
    POLL = "poll"
    COMMAND = "command"
    SYSTEM = "system"

class MessageStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELIVERED = "delivered"
    READ = "read"

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    group_id = Column(Integer, ForeignKey("groups.id"))
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    type = Column(Enum(MessageType), default=MessageType.TEXT)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    content = Column(Text)
    media_url = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    poll_data = Column(JSON, nullable=True)
    reply_to_message_id = Column(BigInteger, nullable=True)
    is_scheduled = Column(Boolean, default=False)
    scheduled_time = Column(DateTime, nullable=True)
    sent_time = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    meta_data = Column(JSON, default={})  # Ek bilgiler
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="messages")
    group = relationship("Group", back_populates="messages")
    template = relationship("Template", back_populates="messages")
    
    def __repr__(self):
        return f"<Message {self.id} - {self.status.value}>" 