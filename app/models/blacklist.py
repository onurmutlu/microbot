from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class BlacklistType(enum.Enum):
    USER = "user"
    GROUP = "group"
    PHONE = "phone"
    IP = "ip"

class BlacklistReason(enum.Enum):
    SPAM = "spam"
    ABUSE = "abuse"
    FRAUD = "fraud"
    VIOLATION = "violation"
    OTHER = "other"

class Blacklist(Base):
    __tablename__ = "blacklist"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    type = Column(Enum(BlacklistType))
    identifier = Column(String, index=True)  # Yasaklanan varlığın benzersiz tanımlayıcısı
    reason = Column(Enum(BlacklistReason))
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="blacklist_entries")
    
    def __repr__(self):
        return f"<Blacklist {self.type.value} - {self.identifier}>" 