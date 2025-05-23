from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, JSON, Text
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class BackupType(enum.Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    DATABASE = "database"
    FILES = "files"
    SETTINGS = "settings"

class BackupStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    RESTORED = "restored"

class Backup(Base):
    __tablename__ = "backups"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(BackupType), nullable=False)
    status = Column(Enum(BackupStatus), default=BackupStatus.PENDING)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)  # Byte cinsinden
    checksum = Column(String)  # Dosya bütünlük kontrolü
    backup_metadata = Column(Text, nullable=True)  # JSON formatında yedekleme detayları
    is_encrypted = Column(Boolean, default=False)
    encryption_key = Column(String, nullable=True)
    storage_location = Column(String, nullable=True)  # Yedekleme konumu
    retention_period = Column(Integer, nullable=True)  # Gün olarak saklama süresi
    last_verified = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="backups")
    
    def __repr__(self):
        return f"<Backup(id={self.id}, user_id={self.user_id}, type={self.type}, status={self.status})>" 