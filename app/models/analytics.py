from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    period = Column(String)  # daily, weekly, monthly, yearly
    message_stats = Column(JSON, default={})  # Mesaj istatistikleri
    group_stats = Column(JSON, default={})  # Grup istatistikleri
    template_stats = Column(JSON, default={})  # Şablon istatistikleri
    user_stats = Column(JSON, default={})  # Kullanıcı aktivite istatistikleri
    performance_metrics = Column(JSON, default={})  # Performans metrikleri
    error_rates = Column(JSON, default={})  # Hata oranları
    success_rates = Column(JSON, default={})  # Başarı oranları
    engagement_metrics = Column(JSON, default={})  # Etkileşim metrikleri
    custom_metrics = Column(JSON, default={})  # Özel metrikler
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="analytics")
    
    def __repr__(self):
        return f"<Analytics {self.user_id} - {self.period}>" 