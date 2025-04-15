from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

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

class User(BaseModel):
    id: int
    username: str
    is_active: bool
    
    class Config:
        orm_mode = True

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
    
    class Config:
        orm_mode = True

class GroupSelect(BaseModel):
    group_ids: List[str]

# Message schemas
class MessageTemplateBase(BaseModel):
    name: str
    content: str
    interval_minutes: int = 60

class MessageTemplateCreate(MessageTemplateBase):
    pass

class MessageTemplate(MessageTemplateBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class MessageSend(BaseModel):
    template_id: int
    group_ids: Optional[List[str]] = None  # Boş ise seçili tüm gruplara gönderilir

# Log schemas
class MessageLog(BaseModel):
    id: int
    group_id: str
    group_title: str
    message_template_id: int
    status: str
    error_message: Optional[str] = None
    sent_at: datetime
    
    class Config:
        orm_mode = True
