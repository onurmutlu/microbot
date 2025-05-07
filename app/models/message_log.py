from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class MessageStatus(enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    CANCELLED = "cancelled"

class MessageLog(Base):
    __tablename__ = "message_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    group_id = Column(Integer, ForeignKey("groups.id"))
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message_template_id = Column(Integer, ForeignKey("message_templates.id"))
    message_content = Column(Text, nullable=True)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    error_message = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", foreign_keys=[user_id])
    group = relationship("Group", foreign_keys=[group_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    template = relationship("MessageTemplate")
    
    def __repr__(self):
        return f"<MessageLog {self.id}>" 