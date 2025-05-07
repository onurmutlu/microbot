from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class MessageStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"

class MessageLogBase(BaseModel):
    user_id: int = Field(..., description="Kullanıcı ID")
    message_id: Optional[int] = Field(None, description="Mesaj ID")
    group_id: Optional[int] = Field(None, description="Grup ID")
    group_name: Optional[str] = Field(None, description="Grup adı")
    template_id: Optional[int] = Field(None, description="Şablon ID")
    template_name: Optional[str] = Field(None, description="Şablon adı")
    status: MessageStatus = Field(default=MessageStatus.PENDING, description="Mesaj durumu")
    error: Optional[str] = Field(None, description="Hata mesajı")

class MessageLogCreate(MessageLogBase):
    pass

class MessageLog(MessageLogBase):
    id: int
    sent_at: datetime
    
    class Config:
        from_attributes = True 