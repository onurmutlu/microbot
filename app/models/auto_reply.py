from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base
import enum

class TriggerType(str, enum.Enum):
    KEYWORD = "keyword"
    COMMAND = "command"
    REGEX = "regex"
    TIME = "time"
    JOIN = "join"
    LEAVE = "leave"

class ResponseType(str, enum.Enum):
    TEXT = "text"
    TEMPLATE = "template"
    MEDIA = "media"
    POLL = "poll"
    ACTION = "action"

class AutoReplyRule(Base):
    __tablename__ = "auto_reply_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    group_id = Column(Integer, ForeignKey("groups.telegram_id"))
    trigger_type = Column(SQLEnum(TriggerType))
    trigger_value = Column(String)
    response_type = Column(SQLEnum(ResponseType))
    response_value = Column(String)
    template_id = Column(Integer, ForeignKey("message_templates.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    cooldown = Column(Integer, default=0)  # Dakika cinsinden
    last_triggered = Column(DateTime, nullable=True)
    rule_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # İlişkiler
    user = relationship("User", back_populates="auto_reply_rules")
    group = relationship("Group", back_populates="auto_reply_rules")
    template = relationship("MessageTemplate", back_populates="auto_reply_rules")

    def __repr__(self):
        return f"<AutoReplyRule {self.trigger_type.value} - {self.response_type.value}>" 