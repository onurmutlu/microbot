from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import User, MessageTemplate
from app.schemas import MessageTemplateCreate, MessageTemplate as MessageTemplateSchema, MessageSend
from app.services.auth_service import get_current_active_user
from app.services.telegram_service import TelegramService

router = APIRouter(
    prefix="/messages",
    tags=["messages"]
)

@router.get("/", response_model=List[MessageTemplateSchema])
def get_messages(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return db.query(MessageTemplate).filter(MessageTemplate.user_id == current_user.id).all()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=MessageTemplateSchema)
def create_message(message: MessageTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    db_message = MessageTemplate(
        name=message.name,
        content=message.content,
        interval_minutes=message.interval_minutes,
        user_id=current_user.id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@router.post("/send")
async def send_message(data: MessageSend, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.send_message(data.template_id, data.group_ids)
    return result
