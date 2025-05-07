from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

class Member(Base):
    __tablename__ = "members"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    status = Column(String, nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("telegram_sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    group = relationship("Group", back_populates="members")
    session = relationship("TelegramSession", back_populates="members")
    
    def __repr__(self):
        return f"<Member {self.user_id} - {self.username or self.first_name}>" 