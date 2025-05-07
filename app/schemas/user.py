from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SubscriptionPlan(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"

class UserBase(BaseModel):
    phone: str = Field(..., description="Telefon numarası")
    api_id: Optional[int] = Field(None, description="Telegram API ID")
    api_hash: Optional[str] = Field(None, description="Telegram API Hash")
    plan: SubscriptionPlan = Field(default=SubscriptionPlan.STARTER, description="Abonelik planı")
    max_sessions: int = Field(default=1, description="Maksimum oturum sayısı")
    auto_start_bots: bool = Field(default=True, description="Otomatik bot başlatma")
    auto_start_scheduling: bool = Field(default=False, description="Otomatik zamanlama başlatma")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Şifre")

class UserLogin(BaseModel):
    phone: str = Field(..., description="Telefon numarası")
    password: str = Field(..., description="Şifre")

class UserUpdate(BaseModel):
    phone: Optional[str] = Field(None, description="Telefon numarası")
    api_id: Optional[int] = Field(None, description="Telegram API ID")
    api_hash: Optional[str] = Field(None, description="Telegram API Hash")
    plan: Optional[SubscriptionPlan] = Field(None, description="Abonelik planı")
    max_sessions: Optional[int] = Field(None, description="Maksimum oturum sayısı")
    auto_start_bots: Optional[bool] = Field(None, description="Otomatik bot başlatma")
    auto_start_scheduling: Optional[bool] = Field(None, description="Otomatik zamanlama başlatma")

class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    verified_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class User(UserInDB):
    pass

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    verified_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True 