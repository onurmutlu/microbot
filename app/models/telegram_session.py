from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

class TelegramSession(Base):
    __tablename__ = "telegram_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, nullable=False)
    api_id = Column(String, nullable=False)
    api_hash = Column(String, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.INACTIVE)
    license_key = Column(String, ForeignKey("licenses.key"))
    created_at = Column(DateTime, default=datetime.utcnow)
    telegram_user_id = Column(String, nullable=True)
    session_string = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # İlişkiler
    user = relationship("User", back_populates="telegram_sessions")
    license = relationship("License", back_populates="telegram_sessions")
    groups = relationship("Group", back_populates="session", cascade="all, delete-orphan")
    members = relationship("Member", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TelegramSession {self.id} - {self.phone}>" 