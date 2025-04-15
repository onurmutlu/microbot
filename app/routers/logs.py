from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, MessageLog
from app.schemas import MessageLog as MessageLogSchema
from app.services.auth_service import get_current_active_user

router = APIRouter(
    prefix="/logs",
    tags=["logs"]
)

@router.get("/", response_model=List[MessageLogSchema])
def get_logs(
    days: int = 1, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    # Belirtilen gün sayısı kadar öncesinden şimdiye kadar olan logları getir
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    return db.query(MessageLog).filter(
        MessageLog.user_id == current_user.id,
        MessageLog.sent_at >= cutoff_date
    ).order_by(MessageLog.sent_at.desc()).all()
