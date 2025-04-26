from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Table, DateTime, Text, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.database import Base

# Kullanıcı rolleri için enum
class UserRole(enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

# Webhook tipleri için enum
class WebhookType(enum.Enum):
    MESSAGE_SENT = "message_sent"
    GROUP_JOINED = "group_joined"
    AUTO_REPLY = "auto_reply"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    telegram_id = Column(String, unique=True, nullable=True, index=True)  # Telegram kullanıcı ID'si - değişmez
    password_hash = Column(String)
    api_id = Column(String)
    api_hash = Column(String)
    phone = Column(String)
    session_string = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    role = Column(Enum(UserRole), default=UserRole.USER)  # Kullanıcı rolü eklendi
    language = Column(String, default="tr")  # Dil tercihi eklendi
    
    # İlişkiler
    groups = relationship("Group", back_populates="user")
    message_templates = relationship("MessageTemplate", back_populates="user")
    logs = relationship("MessageLog", back_populates="user")
    targets = relationship("TargetUser", back_populates="owner")
    auto_reply_rules = relationship("AutoReplyRule", back_populates="user")
    webhooks = relationship("Webhook", back_populates="user")
    medias = relationship("Media", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
    activities = relationship("UserActivity", back_populates="user")

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
    
    # İstatistik alanları
    sent_message_count = Column(Integer, default=0)  # Gruba gönderilen toplam mesaj sayısı
    success_rate = Column(Float, default=100.0)  # Başarılı mesaj oranı (%)
    last_activity = Column(DateTime, nullable=True)  # Son aktivite zamanı
    
    # İlişkiler
    user = relationship("User", back_populates="groups")
    stats = relationship("GroupStat", back_populates="group", cascade="all, delete-orphan")

class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    content = Column(String, nullable=False)
    interval_minutes = Column(Integer, default=60)
    cron_expression = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Yapılandırılmış şablon özellikleri
    has_structured_content = Column(Boolean, default=False)  # Düz metin yerine yapılandırılmış içerik mi?
    structured_content = Column(JSON, nullable=True)  # JSON formatında yapılandırılmış içerik
    
    # İlişkiler
    user = relationship("User", back_populates="message_templates")
    logs = relationship("MessageLog", back_populates="message_template", cascade="all, delete-orphan")
    medias = relationship("Media", back_populates="template")

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
    
    # İstatistik alanları
    message_id = Column(String, nullable=True)  # Telegram'dan dönen mesaj ID'si
    view_count = Column(Integer, default=0)  # Görüntülenme sayısı
    reaction_count = Column(Integer, default=0)  # Tepki sayısı
    
    # İlişkiler
    user = relationship("User", back_populates="logs")
    message_template = relationship("MessageTemplate", back_populates="logs")

class TargetUser(Base):
    __tablename__ = "target_users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, index=True)
    group_id = Column(String, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_dm_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    owner = relationship("User", back_populates="targets")

class AutoReplyRule(Base):
    __tablename__ = "auto_reply_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    trigger_keywords = Column(String)  # Virgülle ayrılmış anahtar kelimeler
    response_text = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    user = relationship("User", back_populates="auto_reply_rules")

# Grupların istatistiklerini tutan tablo (günlük, haftalık, aylık)
class GroupStat(Base):
    __tablename__ = "group_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    date = Column(DateTime, default=datetime.utcnow)
    message_count = Column(Integer, default=0)  # O gün gönderilen mesaj sayısı
    success_count = Column(Integer, default=0)  # Başarılı gönderim sayısı
    fail_count = Column(Integer, default=0)  # Başarısız gönderim sayısı
    view_count = Column(Integer, default=0)  # Görüntülenme sayısı
    peak_hour = Column(Integer, nullable=True)  # En yüksek aktivite saati
    stat_type = Column(String, default="daily")  # daily, weekly, monthly
    
    # İlişkiler
    group = relationship("Group", back_populates="stats")

# Webhook tanımları
class Webhook(Base):
    __tablename__ = "webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=True)  # Güvenlik için webhook secret
    event_types = Column(String, nullable=False)  # Virgülle ayrılmış event tipleri
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    user = relationship("User", back_populates="webhooks")

# Medya dosyaları tablosu
class Media(Base):
    __tablename__ = "medias"
    
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Dosyanın saklandığı yol
    file_type = Column(String, nullable=False)  # image, video, audio, document
    file_size = Column(Integer, nullable=False)  # Bayt cinsinden dosya boyutu
    telegram_file_id = Column(String, nullable=True)  # Telegram File ID (yeniden kullanım için)
    mime_type = Column(String, nullable=True)  # Dosya MIME tipi
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    template_id = Column(Integer, ForeignKey("message_templates.id"), nullable=True)
    
    # İlişkiler
    user = relationship("User", back_populates="medias")
    template = relationship("MessageTemplate", back_populates="medias")

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(50), nullable=False)
    hashed_key = Column(String(256), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)

    user = relationship("User", back_populates="api_keys")

class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON, nullable=True)

    user = relationship("User", back_populates="activities")
