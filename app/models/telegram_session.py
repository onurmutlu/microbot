from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class SessionStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    ERROR = "error"

class TelegramSession(Base):
    __tablename__ = "telegram_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_string = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    api_id = Column(String, nullable=False)
    api_hash = Column(String, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.INACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="telegram_sessions")
    groups = relationship("Group", back_populates="session")
    members = relationship("Member", back_populates="session")
    
    def __repr__(self):
        return f"<TelegramSession {self.id} - {self.phone_number}>" 