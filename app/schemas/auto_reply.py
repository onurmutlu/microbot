from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AutoReplyRuleBase(BaseModel):
    keyword: str = Field(..., description="Tetikleyici anahtar kelime")
    response: str = Field(..., description="Otomatik yanıt metni")
    is_regex: bool = Field(default=False, description="Regex kullanımı")
    is_active: bool = Field(default=True, description="Aktif durumu")
    user_id: int = Field(..., description="Kullanıcı ID")
    group_id: Optional[int] = Field(None, description="Grup ID")

class AutoReplyRuleCreate(AutoReplyRuleBase):
    pass

class AutoReplyRuleUpdate(AutoReplyRuleBase):
    keyword: Optional[str] = Field(None, description="Tetikleyici anahtar kelime")
    response: Optional[str] = Field(None, description="Otomatik yanıt metni")
    is_regex: Optional[bool] = Field(None, description="Regex kullanımı")
    is_active: Optional[bool] = Field(None, description="Aktif durumu")
    user_id: Optional[int] = Field(None, description="Kullanıcı ID")
    group_id: Optional[int] = Field(None, description="Grup ID")

class AutoReplyRule(AutoReplyRuleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True 