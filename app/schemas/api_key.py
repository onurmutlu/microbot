from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ApiKeyCreate(BaseModel):
    name: str = Field(..., description="API anahtarı adı")
    user_id: int = Field(..., description="Kullanıcı ID")

class ApiKeyResponse(BaseModel):
    id: int
    name: str = Field(..., description="API anahtarı adı")
    key: str = Field(..., description="API anahtarı")
    user_id: int = Field(..., description="Kullanıcı ID")
    created_at: datetime
    last_used: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserActivity(BaseModel):
    date: datetime
    count: int

class UserActivityResponse(BaseModel):
    activities: List[UserActivity]
    
    class Config:
        from_attributes = True 