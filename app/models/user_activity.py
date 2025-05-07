from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

class UserActivity(Base):
    __tablename__ = "user_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    details = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="activities")
    
    def __repr__(self):
        return f"<UserActivity {self.id} - {self.user_id} - {self.action}>" 