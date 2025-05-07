from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class ApiKeyPermission(enum.Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    CUSTOM = "custom"

class ApiKeyStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"
    EXPIRED = "expired"

class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key = Column(String, unique=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)
    permissions = Column(String, nullable=True)  # JSON formatında izinler
    status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.ACTIVE)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    ip_whitelist = Column(String, nullable=True)  # JSON formatında IP listesi
    rate_limit = Column(Integer, default=100)  # Saatlik istek limiti
    custom_permissions = Column(JSON, default={})  # Özel izinler
    api_metadata = Column(JSON, default={})  # Ek bilgiler
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="api_keys")
    
    def __repr__(self):
        return f"<ApiKey {self.name} - {self.status.value}>" 