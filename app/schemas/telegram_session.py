from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class TelegramSessionBase(BaseModel):
    session_name: str = Field(..., description="Oturum adı")
    session_string: str = Field(..., description="Telegram oturum string")
    status: SessionStatus = Field(default=SessionStatus.INACTIVE, description="Oturum durumu")
    user_id: int = Field(..., description="Kullanıcı ID")
    error_message: Optional[str] = Field(None, description="Hata mesajı")

class TelegramSessionCreate(TelegramSessionBase):
    pass

class TelegramSessionUpdate(TelegramSessionBase):
    session_name: Optional[str] = Field(None, description="Oturum adı")
    session_string: Optional[str] = Field(None, description="Telegram oturum string")
    status: Optional[SessionStatus] = Field(None, description="Oturum durumu")
    user_id: Optional[int] = Field(None, description="Kullanıcı ID")
    error_message: Optional[str] = Field(None, description="Hata mesajı")

class TelegramSession(TelegramSessionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True 