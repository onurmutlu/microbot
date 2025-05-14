from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class LicenseType(str, enum.Enum):
    TRIAL = "TRIAL"
    PRO = "PRO"
    VIP = "VIP"

class License(Base):
    __tablename__ = "licenses"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    type = Column(Enum(LicenseType, name="licensetype", create_constraint=True, checkfirst=True), default=LicenseType.TRIAL)
    expiry_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_by = Column(String, nullable=True)  # Kullanıcının e-posta veya telefon numarası
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # İlişkiler
    user = relationship("User", back_populates="licenses")
    telegram_sessions = relationship("TelegramSession", back_populates="license")
    
    def __repr__(self):
        return f"<License {self.key}>" 