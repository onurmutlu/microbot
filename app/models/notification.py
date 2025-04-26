from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime
import enum

class NotificationType(enum.Enum):
    SYSTEM = "system"
    MESSAGE = "message"
    PAYMENT = "payment"
    SUBSCRIPTION = "subscription"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class NotificationStatus(enum.Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(NotificationType))
    status = Column(Enum(NotificationStatus), default=NotificationStatus.UNREAD)
    title = Column(String)
    message = Column(String)
    data = Column(JSON, default={})  # Ek bilgiler
    is_email_sent = Column(Boolean, default=False)
    is_telegram_sent = Column(Boolean, default=False)
    is_push_sent = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification {self.type.value} - {self.status.value}>" 