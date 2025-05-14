from sqlalchemy import Column, Integer, String, Boolean, DateTime, ARRAY, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class AdminRole(str, enum.Enum):
    ADMIN = "admin"
    SUPERADMIN = "superadmin"

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(AdminRole), default=AdminRole.ADMIN)
    permissions = Column(String, nullable=True)  # JSON formatında saklanacak izinler
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<AdminUser {self.username}>" 