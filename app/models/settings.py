from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    notification_enabled = Column(Boolean, default=True)
    notification_email = Column(String, nullable=True)
    notification_telegram = Column(Boolean, default=True)
    message_delay = Column(Integer, default=0)  # Mesajlar arası bekleme süresi (saniye)
    max_messages_per_day = Column(Integer, default=100)
    timezone = Column(String, default="UTC")
    language = Column(String, default="tr")
    theme = Column(String, default="light")
    custom_settings = Column(JSON, default={})  # Özel ayarlar için JSON alanı
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="settings")
    
    def __repr__(self):
        return f"<Settings {self.user_id}>" 