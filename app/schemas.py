from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Enum tipler
class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

class WebhookTypeEnum(str, Enum):
    MESSAGE_SENT = "message_sent"
    GROUP_JOINED = "group_joined"
    AUTO_REPLY = "auto_reply"

class MediaTypeEnum(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"

class StatPeriodEnum(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

# Auth schemas
class UserCreate(BaseModel):
    username: str
    password: str
    api_id: str
    api_hash: str
    phone: str

class UserLogin(BaseModel):
    username: str
    password: str

class VerifyCode(BaseModel):
    code: str
    
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRoleEnum] = None
    language: Optional[str] = None

class User(BaseModel):
    id: int
    username: str
    is_active: bool
    role: UserRoleEnum
    language: str
    
    class Config:
        from_attributes = True

# Group schemas
class GroupBase(BaseModel):
    group_id: str
    title: str
    username: Optional[str] = None
    member_count: Optional[int] = None

class Group(GroupBase):
    id: int
    is_selected: bool
    is_active: bool
    last_message: Optional[datetime] = None
    message_count: int
    sent_message_count: int
    success_rate: float
    last_activity: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class GroupSelect(BaseModel):
    group_ids: List[str]

# Message schemas
class MessageTemplateBase(BaseModel):
    name: str = Field(..., description="Şablon adı")
    content: str = Field(..., description="Mesaj içeriği")
    interval_minutes: int = Field(60, description="Gönderim sıklığı (dakika olarak)")
    is_active: bool = Field(True, description="Şablonun aktif olup olmadığı")

class MessageTemplateCreate(BaseModel):
    name: str = Field(..., description="Şablon adı")
    content: str = Field(..., description="Mesaj içeriği")
    interval_minutes: int = Field(60, description="Gönderim sıklığı (dakika olarak)")
    cron_expression: Optional[str] = Field(None, description="Cron formatında zamanlama ifadesi (opsiyonel)")
    has_structured_content: bool = Field(False, description="Yapılandırılmış içerik kullanılsın mı?")
    structured_content: Optional[Dict[str, Any]] = Field(None, description="JSON formatında yapılandırılmış içerik")

class MessageTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Yeni şablon adı")
    content: Optional[str] = Field(None, description="Yeni mesaj içeriği")
    interval_minutes: Optional[int] = Field(None, description="Yeni gönderim sıklığı (dakika olarak)")
    cron_expression: Optional[str] = Field(None, description="Cron formatında zamanlama ifadesi (opsiyonel)")
    is_active: Optional[bool] = Field(None, description="Şablonun aktif/pasif durumu")
    has_structured_content: Optional[bool] = Field(None, description="Yapılandırılmış içerik kullanılsın mı?")
    structured_content: Optional[Dict[str, Any]] = Field(None, description="JSON formatında yapılandırılmış içerik")

class MessageTemplate(MessageTemplateBase):
    id: int
    user_id: int
    created_at: datetime
    cron_expression: Optional[str] = None
    has_structured_content: bool
    structured_content: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MessageSend(BaseModel):
    template_id: int
    group_ids: Optional[List[str]] = None  # Boş ise seçili tüm gruplara gönderilir
    media_ids: Optional[List[int]] = None  # Mesajla birlikte gönderilecek medya dosyaları

# Log schemas
class MessageLog(BaseModel):
    id: int
    group_id: str
    group_title: str
    message_template_id: int
    status: str
    error_message: Optional[str] = None
    sent_at: datetime
    message_id: Optional[str] = None
    view_count: int = 0
    reaction_count: int = 0
    
    class Config:
        from_attributes = True

# Stats schemas
class GroupStatBase(BaseModel):
    group_id: int
    date: datetime
    message_count: int
    success_count: int
    fail_count: int
    view_count: int
    peak_hour: Optional[int] = None
    stat_type: StatPeriodEnum = StatPeriodEnum.DAILY

class GroupStat(GroupStatBase):
    id: int
    
    class Config:
        from_attributes = True

class GroupStatCreate(GroupStatBase):
    pass

class GroupStatsRequest(BaseModel):
    group_ids: List[int]
    period: StatPeriodEnum = StatPeriodEnum.DAILY
    start_date: datetime
    end_date: Optional[datetime] = None

class GroupStatsSummary(BaseModel):
    group_id: int
    group_title: str
    total_messages: int
    success_rate: float
    total_views: int
    most_active_hour: Optional[int] = None
    period: StatPeriodEnum
    daily_stats: List[Dict[str, Any]]

# Webhook schemas
class WebhookBase(BaseModel):
    name: str
    url: HttpUrl
    secret: Optional[str] = None
    event_types: List[WebhookTypeEnum]
    is_active: bool = True

class WebhookCreate(WebhookBase):
    pass

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    event_types: Optional[List[WebhookTypeEnum]] = None
    is_active: Optional[bool] = None

class Webhook(WebhookBase):
    id: int
    created_at: datetime
    last_triggered: Optional[datetime] = None
    user_id: int
    
    class Config:
        from_attributes = True

# Media schemas
class MediaBase(BaseModel):
    file_name: str
    file_type: MediaTypeEnum
    mime_type: Optional[str] = None

class MediaCreate(MediaBase):
    pass

class MediaUpdate(BaseModel):
    file_name: Optional[str] = None
    template_id: Optional[int] = None

class Media(MediaBase):
    id: int
    file_path: str
    file_size: int
    telegram_file_id: Optional[str] = None
    created_at: datetime
    user_id: int
    template_id: Optional[int] = None
    
    class Config:
        from_attributes = True

# Structured content schemas
class ButtonAction(BaseModel):
    type: str  # url, callback
    value: str  # URL veya callback data
    text: str  # Buton metni

class StructuredContent(BaseModel):
    type: str  # text, card, poll, etc.
    text: Optional[str] = None
    title: Optional[str] = None
    media_id: Optional[int] = None
    buttons: Optional[List[ButtonAction]] = None
    additional_data: Optional[Dict[str, Any]] = None

# API Anahtarı Şemaları
class ApiKeyBase(BaseModel):
    name: str

class ApiKeyCreate(ApiKeyBase):
    user_id: Optional[int] = None
    expires_days: Optional[int] = None

class ApiKeyResponse(ApiKeyBase):
    id: int
    key: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    user_id: int

    class Config:
        orm_mode = True

# Kullanıcı Aktivitesi Şemaları
class UserActivityBase(BaseModel):
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class UserActivityCreate(UserActivityBase):
    user_id: int

class UserActivityResponse(UserActivityBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True

# Sistem Durum Şeması
class SystemStatus(BaseModel):
    users: Dict[str, int]
    api_keys: Dict[str, int]
    activities: Dict[str, int]
    system: Dict[str, Any]
