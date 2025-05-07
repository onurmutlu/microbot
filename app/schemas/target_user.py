from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TargetUserBase(BaseModel):
    username: str = Field(..., description="Hedef kullanıcı adı")
    first_name: Optional[str] = Field(None, description="İsim")
    last_name: Optional[str] = Field(None, description="Soyisim")
    notes: Optional[str] = Field(None, description="Notlar")
    user_id: int = Field(..., description="Kullanıcı ID")

class TargetUserCreate(TargetUserBase):
    pass

class TargetUserUpdate(TargetUserBase):
    username: Optional[str] = Field(None, description="Hedef kullanıcı adı")
    user_id: Optional[int] = Field(None, description="Kullanıcı ID")

class TargetUser(TargetUserBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True 