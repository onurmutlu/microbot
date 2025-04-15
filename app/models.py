from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Table, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    api_id = Column(String)
    api_hash = Column(String)
    phone = Column(String)
    session_string = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # İlişkiler
    groups = relationship("Group", back_populates="user")
    message_templates = relationship("MessageTemplate", back_populates="user")
    logs = relationship("MessageLog", back_populates="user")

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String, index=True)  # Telegram group_id
    title = Column(String)
    username = Column(String, nullable=True)
    member_count = Column(Integer, nullable=True)
    is_selected = Column(Boolean, default=False)  # Mesaj gönderme için seçilmiş mi
    is_active = Column(Boolean, default=True)
    last_message = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    user = relationship("User", back_populates="groups")

class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    content = Column(Text)
    interval_minutes = Column(Integer, default=60)  # Gönderim sıklığı (dakika)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    user = relationship("User", back_populates="message_templates")

class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String)
    group_title = Column(String)
    message_template_id = Column(Integer, ForeignKey("message_templates.id"))
    status = Column(String)  # success, error
    error_message = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    user = relationship("User", back_populates="logs")
