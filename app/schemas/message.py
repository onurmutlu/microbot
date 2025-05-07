from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class MessageStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"

class MessageBase(BaseModel):
    content: str = Field(..., description="Mesaj içeriği")
    group_id: Optional[int] = Field(None, description="Gönderilecek grup ID")
    user_id: Optional[int] = Field(None, description="Kullanıcı ID")

class MessageCreate(MessageBase):
    pass

class MessageUpdate(MessageBase):
    content: Optional[str] = Field(None, description="Mesaj içeriği")

class Message(MessageBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class MessageSend(BaseModel):
    template_id: int
    group_ids: Optional[List[int]] = None

class MessageLog(BaseModel):
    id: int
    user_id: int
    message_id: Optional[int] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    sent_at: datetime
    status: MessageStatus
    error: Optional[str] = None

    class Config:
        from_attributes = True 