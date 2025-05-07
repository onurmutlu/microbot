from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str = Field(..., description="JWT erişim tokeni")
    token_type: str = Field(default="bearer", description="Token tipi")
    expires_at: datetime = Field(..., description="Token son kullanma tarihi")
    telegram_login_required: bool = False

class TokenPayload(BaseModel):
    sub: int = Field(..., description="Kullanıcı ID")
    exp: datetime = Field(..., description="Token son kullanma tarihi")

class VerifyCode(BaseModel):
    phone: str = Field(..., description="Telefon numarası")
    code: str = Field(..., min_length=6, max_length=6, description="Doğrulama kodu")
    password: Optional[str] = None

class TelegramLoginData(BaseModel):
    id: int
    first_name: str
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str
    last_name: Optional[str] = None 