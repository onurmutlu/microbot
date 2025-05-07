from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, Group
from app.schemas import Group as GroupSchema, GroupSelect
from app.services.auth_service import get_current_active_user
from app.services.telegram_service import TelegramService

router = APIRouter(
    prefix="/groups",
    tags=["groups"]
)

@router.get("/", response_model=List[GroupSchema])
async def get_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Önce veritabanından grupları kontrol et
    groups = db.query(Group).filter(Group.user_id == current_user.id).all()
    
    # Grupları yenile ve veritabanına kaydet
    telegram_service = TelegramService(db, current_user.id)
    await telegram_service.discover_groups()
    
    # Güncel grupları getir
    groups = db.query(Group).filter(Group.user_id == current_user.id).all()
    return {"success": True, "message": "Groups retrieved successfully", "data": groups}

@router.post("/select")
async def select_groups(data: GroupSelect, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    telegram_service = TelegramService(db, current_user.id)
    result = await telegram_service.select_groups(data.group_ids)
    return {"success": True, "message": "Groups selected successfully", "data": result}
