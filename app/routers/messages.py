from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import User
from app.schemas import MessageSend
from app.services.auth_service import get_current_active_user
from app.services.telegram_service import TelegramService

router = APIRouter(
    prefix="/messages",
    tags=["messages"]
)

@router.post("/send")
async def send_message(data: MessageSend, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """
    Kullanıcının seçtiği template_id ve group_ids bilgilerine göre anlık mesaj gönderimi yapar.
    Boş group_ids gönderilirse, kullanıcının seçili tüm gruplarına mesaj gönderilir.
    """
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.send_message(data.template_id, data.group_ids)
    return result
