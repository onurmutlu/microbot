from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base
import enum

class TemplateType(str, enum.Enum):
    TEXT = "text"
    MEDIA = "media"
    POLL = "poll"

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    type = Column(SQLEnum(TemplateType))
    content = Column(String)
    variables = Column(JSON, nullable=True)
    media_url = Column(String, nullable=True)
    media_type = Column(String, nullable=True)
    poll_options = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    use_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    template_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # İlişkiler
    user = relationship("User", back_populates="templates")
    messages = relationship("Message", back_populates="template")
    auto_reply_rules = relationship("AutoReplyRule", back_populates="template")
    schedules = relationship("Schedule", back_populates="template")
    
    def __repr__(self):
        return f"<Template {self.name}>" 