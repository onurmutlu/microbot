from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, JSON, BigInteger
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class GroupType(enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    CHANNEL = "channel"
    SUPERGROUP = "supergroup"

class GroupStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(Integer, ForeignKey("telegram_sessions.id"))
    group_id = Column(BigInteger, index=True)
    group_name = Column(String)
    type = Column(Enum(GroupType), default=GroupType.PUBLIC)
    status = Column(Enum(GroupStatus), default=GroupStatus.ACTIVE)
    username = Column(String, nullable=True)
    description = Column(String, nullable=True)
    members_count = Column(Integer, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    last_message_time = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)
    group_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="groups")
    session = relationship("TelegramSession", back_populates="groups")
    messages = relationship("Message", back_populates="group")
    auto_reply_rules = relationship("AutoReplyRule", back_populates="group")
    members = relationship("Member", back_populates="group")
    schedules = relationship("Schedule", back_populates="group")
    
    def __repr__(self):
        return f"<Group {self.group_name}>" 