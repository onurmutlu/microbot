from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    api_id = Column(Integer)
    api_hash = Column(String)
    session_file = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    # Otomatik bot başlatma ayarları
    auto_start_bots = Column(Boolean, default=True)
    auto_start_scheduling = Column(Boolean, default=False)
    
    # İlişkiler
    licenses = relationship("License", back_populates="user")
    messages = relationship("Message", back_populates="user")
    groups = relationship("Group", back_populates="user")
    templates = relationship("Template", back_populates="user")
    message_templates = relationship("MessageTemplate", back_populates="user")
    logs = relationship("Log", back_populates="user")
    settings = relationship("Settings", back_populates="user", uselist=False)
    statistics = relationship("Statistics", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    blacklist_entries = relationship("Blacklist", back_populates="user")
    schedules = relationship("Schedule", back_populates="user")
    analytics = relationship("Analytics", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    backups = relationship("Backup", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    target_users = relationship("TargetUser", back_populates="owner")
    auto_reply_rules = relationship("AutoReplyRule", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.phone}>" 