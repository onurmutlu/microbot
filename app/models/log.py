from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime
import enum

class LogLevel(enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class LogType(enum.Enum):
    SYSTEM = "system"
    USER = "user"
    MESSAGE = "message"
    GROUP = "group"
    TEMPLATE = "template"
    LICENSE = "license"

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    level = Column(Enum(LogLevel), default=LogLevel.INFO)
    type = Column(Enum(LogType), default=LogType.SYSTEM)
    message = Column(Text)
    details = Column(Text, nullable=True)  # JSON formatında detaylar
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="logs")
    
    def __repr__(self):
        return f"<Log {self.level.value} - {self.type.value}>" 