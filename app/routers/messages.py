from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.database import get_db
from app.models import User, Message, Group, MessageTemplate
from app.services.auth_service import get_current_active_user
from app.services.telegram_service import TelegramService
from app.schemas import MessageSend

router = APIRouter(
    prefix="/messages",
    tags=["messages"]
)

@router.post("/send")
async def send_message(
    data: MessageSend, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    """Bir veya daha fazla gruba mesaj gönderir"""
    # Şablonu doğrula
    template = db.query(MessageTemplate).filter(
        MessageTemplate.id == data.template_id,
        MessageTemplate.user_id == current_user.id
    ).first()
    
    if not template:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Şablon bulunamadı", "data": {}}
        )
    
    # Grupları belirle
    if data.group_ids and len(data.group_ids) > 0:
        # Kullanıcı belirli gruplara göndermek istiyor
        groups = []
        for group_id in data.group_ids:
            group = db.query(Group).filter(
                Group.user_id == current_user.id,
                Group.group_id == group_id
            ).first()
            if group:
                groups.append(group)
    else:
        # Seçili tüm gruplara gönder
        groups = db.query(Group).filter(
            Group.user_id == current_user.id,
            Group.is_selected == True
        ).all()
    
    if not groups:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Mesaj gönderilecek grup bulunamadı", "data": {}}
        )
    
    # Telegram servisini başlat
    telegram_service = TelegramService(db, current_user.id)
    
    # Her gruba mesaj gönder
    results = []
    for group in groups:
        try:
            result = await telegram_service.send_message(
                group_id=group.group_id,
                template_id=template.id,
                media_ids=data.media_ids
            )
            results.append({
                "group_id": group.group_id,
                "group_title": group.title,
                "success": True,
                "message_id": result.get("message_id")
            })
        except Exception as e:
            results.append({
                "group_id": group.group_id,
                "group_title": group.title,
                "success": False,
                "error": str(e)
            })
    
    return {
        "success": True,
        "message": f"Mesaj {len(results)} gruba gönderilmeye çalışıldı",
        "data": {
            "results": results
        }
    }
