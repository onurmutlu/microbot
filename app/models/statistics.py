from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class Statistics(Base):
    __tablename__ = "statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    total_messages = Column(Integer, default=0)
    successful_messages = Column(Integer, default=0)
    failed_messages = Column(Integer, default=0)
    cancelled_messages = Column(Integer, default=0)
    total_groups = Column(Integer, default=0)
    active_groups = Column(Integer, default=0)
    total_templates = Column(Integer, default=0)
    active_templates = Column(Integer, default=0)
    message_stats = Column(JSON, default={})  # Grup bazlı mesaj istatistikleri
    template_stats = Column(JSON, default={})  # Şablon bazlı mesaj istatistikleri
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="statistics")
    
    def __repr__(self):
        return f"<Statistics {self.user_id} - {self.date}>" 