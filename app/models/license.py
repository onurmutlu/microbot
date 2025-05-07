from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

class License(Base):
    __tablename__ = "licenses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    license_key = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    # İlişkiler
    user = relationship("User", back_populates="licenses")
    
    def __repr__(self):
        return f"<License {self.license_key}>" 