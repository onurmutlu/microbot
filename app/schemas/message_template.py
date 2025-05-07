from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class MessageTemplateBase(BaseModel):
    name: str = Field(..., description="Şablon adı")
    content: str = Field(..., description="Şablon içeriği")
    user_id: Optional[int] = Field(None, description="Kullanıcı ID")

class MessageTemplateCreate(MessageTemplateBase):
    pass

class MessageTemplateUpdate(MessageTemplateBase):
    name: Optional[str] = Field(None, description="Şablon adı")
    content: Optional[str] = Field(None, description="Şablon içeriği")

class MessageTemplate(MessageTemplateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True 