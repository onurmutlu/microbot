from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class ScheduleType(enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class ScheduleStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    template_id = Column(Integer, ForeignKey("message_templates.id"))
    group_id = Column(Integer, ForeignKey("groups.id"))
    type = Column(Enum(ScheduleType))
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.PENDING)
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    repeat_interval = Column(Integer, nullable=True)  # Tekrar aralığı (dakika)
    repeat_days = Column(String, nullable=True)  # JSON formatında günler [1,2,3,4,5]
    repeat_hours = Column(String, nullable=True)  # JSON formatında saatler [9,12,15]
    timezone = Column(String, default="UTC")
    is_active = Column(Boolean, default=True)
    last_execution = Column(DateTime, nullable=True)  # Son çalıştırma zamanı
    next_execution = Column(DateTime, nullable=True)  # Sonraki çalıştırma zamanı
    schedule_metadata = Column(JSON, default={})  # Ek ayarlar ve bilgiler
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="schedules")
    template = relationship("MessageTemplate", back_populates="schedules")
    group = relationship("Group", back_populates="schedules")
    
    def __repr__(self):
        return f"<Schedule {self.type.value} - {self.status.value}>" 