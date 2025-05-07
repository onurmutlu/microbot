from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

class TargetUser(Base):
    __tablename__ = "target_users"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    telegram_user_id = Column(BigInteger, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_dm_sent = Column(Boolean, default=False)
    last_interaction = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    owner = relationship("User", foreign_keys=[owner_id])
    group = relationship("Group", foreign_keys=[group_id])
    
    def __repr__(self):
        return f"<TargetUser {self.telegram_user_id}>" 