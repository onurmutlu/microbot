from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str
    telegram_login_required: bool = False

class VerifyCode(BaseModel):
    code: str
    password: Optional[str] = None 