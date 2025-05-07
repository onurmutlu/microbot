from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class TaskType(enum.Enum):
    MESSAGE = "message"
    BACKUP = "backup"
    CLEANUP = "cleanup"
    SYNC = "sync"
    REPORT = "report"
    CUSTOM = "custom"

class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(TaskType))
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    name = Column(String)
    description = Column(String, nullable=True)
    parameters = Column(JSON, default={})  # Görev parametreleri
    result = Column(JSON, nullable=True)  # Görev sonucu
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_time = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Integer, default=0)  # Yüzde olarak ilerleme
    worker_id = Column(String, nullable=True)  # Görevi çalıştıran worker
    task_metadata = Column(JSON, default={})  # Ek bilgiler - metadata yerine task_metadata olarak değiştirildi
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="tasks")
    
    def __repr__(self):
        return f"<Task {self.type.value} - {self.status.value}>" 