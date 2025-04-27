from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime
import enum

class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ERROR = "error"
    EXPIRED = "expired"
    PENDING = "pending"

class TelegramSession(Base):
    __tablename__ = "telegram_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    phone_number = Column(String, index=True)
    api_id = Column(String)
    api_hash = Column(String)
    session_name = Column(String, nullable=True)
    session_string = Column(String, nullable=True)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.PENDING)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="telegram_sessions")
    groups = relationship("Group", back_populates="session")
    
    def __repr__(self):
        return f"<TelegramSession {self.phone_number}>" 