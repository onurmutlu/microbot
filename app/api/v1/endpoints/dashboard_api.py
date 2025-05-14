from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.message import Message
from app.models.group import Group
from app.models.message_template import MessageTemplate as Template
from app.models.task import Task, TaskStatus
from app.models.schedule import Schedule, ScheduleStatus
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/dashboard/stats", response_model=Dict[str, Any])
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Kullanıcı için dashboard istatistikleri döndürür.
    """
    # Bugün ve dün için tarih aralığı
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    
    # Mesaj sayıları
    message_count = db.query(Message).filter(
        Message.user_id == current_user.id
    ).count()
    
    today_message_count = db.query(Message).filter(
        Message.user_id == current_user.id,
        Message.created_at >= today
    ).count()
    
    yesterday_message_count = db.query(Message).filter(
        Message.user_id == current_user.id,
        Message.created_at >= yesterday,
        Message.created_at < today
    ).count()
    
    # Grup sayıları
    group_count = db.query(Group).filter(
        Group.user_id == current_user.id
    ).count()
    
    active_group_count = db.query(Group).filter(
        Group.user_id == current_user.id,
        Group.is_active == True
    ).count()
    
    # Şablon sayıları
    template_count = db.query(Template).filter(
        Template.user_id == current_user.id
    ).count()
    
    active_template_count = db.query(Template).filter(
        Template.user_id == current_user.id,
        Template.is_active == True
    ).count()
    
    # Görev sayıları
    pending_tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.status == TaskStatus.PENDING
    ).count()
    
    completed_tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.status == TaskStatus.COMPLETED
    ).count()
    
    failed_tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.status == TaskStatus.FAILED
    ).count()
    
    # Zamanlama sayıları
    active_schedules = db.query(Schedule).filter(
        Schedule.user_id == current_user.id,
        Schedule.is_active == True
    ).count()
    
    # Başarı oranı
    success_rate = 0
    if message_count > 0:
        success_count = db.query(Message).filter(
            Message.user_id == current_user.id,
            Message.status == "sent"  # Başarılı durum
        ).count()
        success_rate = round((success_count / message_count) * 100, 2)
    
    # Grafik verisi (basitleştirilmiş)
    graph_data = {
        "daily": [
            {"date": (today - timedelta(days=i)).strftime("%Y-%m-%d"), 
             "count": db.query(Message).filter(
                 Message.user_id == current_user.id,
                 Message.created_at >= (today - timedelta(days=i)),
                 Message.created_at < (today - timedelta(days=i-1))
             ).count()} 
            for i in range(7)
        ],
    }
    
    # Son aktivite
    last_message = db.query(Message).filter(
        Message.user_id == current_user.id
    ).order_by(Message.created_at.desc()).first()
    
    last_activity = None
    if last_message:
        last_activity = last_message.created_at.isoformat()
    
    return {
        "messages": {
            "total": message_count,
            "today": today_message_count,
            "yesterday": yesterday_message_count,
            "growth": calculate_growth(today_message_count, yesterday_message_count)
        },
        "groups": {
            "total": group_count,
            "active": active_group_count
        },
        "templates": {
            "total": template_count,
            "active": active_template_count
        },
        "tasks": {
            "pending": pending_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks
        },
        "schedules": {
            "active": active_schedules
        },
        "performance": {
            "success_rate": success_rate
        },
        "activity": {
            "last_activity": last_activity
        },
        "graph_data": graph_data
    }

def calculate_growth(current, previous):
    """Büyüme oranını hesaplar"""
    if previous == 0:
        return 100 if current > 0 else 0
    
    growth = ((current - previous) / previous) * 100
    return round(growth, 2) 