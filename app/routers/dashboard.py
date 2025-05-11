from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.message import Message
from app.models.group import Group
from app.models.message_template import MessageTemplate
from app.models.task import Task, TaskStatus
from app.models.schedule import Schedule, ScheduleStatus
from fastapi.security import OAuth2PasswordBearer
from app.services.auth_service import get_current_user
from app.services.scheduled_messaging import get_scheduled_messaging_service
from app.services.group_analyzer import GroupAnalyzer

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Mevcut kullanıcıyı getir
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.services.auth_service import AuthService
    auth_service = AuthService(db)
    user = auth_service.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.get("/stats", operation_id="dashboard_get_stats")
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
    template_count = db.query(MessageTemplate).filter(
        MessageTemplate.user_id == current_user.id
    ).count()
    
    active_template_count = db.query(MessageTemplate).filter(
        MessageTemplate.user_id == current_user.id,
        MessageTemplate.is_active == True
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

@router.get("/statistics", response_model=Dict[str, Any])
async def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcı dashboard'u için temel istatistikleri döndürür"""
    
    # Son 24 saatteki mesajlar
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    messages_last_24h = db.query(Message).filter(
        Message.user_id == current_user.id,
        Message.created_at >= one_day_ago
    ).count()
    
    # Son 24 saatteki başarılı mesajlar
    success_messages = db.query(Message).filter(
        Message.user_id == current_user.id,
        Message.created_at >= one_day_ago,
        Message.status == 'success'
    ).count()
    
    # Aktif gruplar
    active_groups = db.query(Group).filter(
        Group.user_id == current_user.id,
        Group.is_active == True
    ).count()
    
    # Aktif mesaj şablonları
    active_templates = db.query(MessageTemplate).filter(
        MessageTemplate.user_id == current_user.id,
        MessageTemplate.is_active == True
    ).count()
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "messages_last_24h": messages_last_24h,
        "success_messages": success_messages,
        "success_rate": (success_messages / messages_last_24h * 100) if messages_last_24h > 0 else 0,
        "active_groups": active_groups,
        "active_templates": active_templates,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/group-activity", response_model=Dict[str, Any])
async def get_group_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    group_id: Optional[int] = None
):
    """
    Grupların aktivite istatistiklerini döndürür.
    Belirli bir group_id belirtilirse sadece o grup için detaylı istatistik döndürür.
    """
    try:
        # GroupAnalyzer servisini oluştur
        from app.services.telegram_service import TelegramService
        telegram_service = TelegramService(db, current_user.id)
        client = await telegram_service.get_client()
        group_analyzer = GroupAnalyzer(client)
        
        if group_id:
            # Tek grup için detaylı istatistik
            stats = await group_analyzer.get_group_stats(group_id)
            return {
                "group_id": group_id,
                "statistics": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Tüm gruplar için genel istatistik
            stats = await group_analyzer.get_user_group_stats(current_user.id)
            return {
                "user_id": current_user.id,
                "group_statistics": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grup aktivite bilgisi alınamadı: {str(e)}"
        )

@router.get("/optimal-intervals", response_model=Dict[str, Any])
async def get_optimal_intervals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Kullanıcının tüm grupları için hesaplanan optimal mesaj gönderme aralıklarını döndürür
    """
    try:
        # GroupAnalyzer servisini oluştur
        from app.services.telegram_service import TelegramService
        telegram_service = TelegramService(db, current_user.id)
        client = await telegram_service.get_client()
        group_analyzer = GroupAnalyzer(client)
        
        # Optimal aralıkları hesapla
        intervals = group_analyzer.get_optimal_intervals_for_user(current_user.id)
        
        # Grup bilgilerini ekle
        groups = db.query(Group).filter(
            Group.user_id == current_user.id,
            Group.is_active == True
        ).all()
        
        group_intervals = []
        for group in groups:
            group_id = group.telegram_id
            interval = intervals.get(group_id, 60)  # Varsayılan 60 dakika
            
            group_intervals.append({
                "group_id": group_id,
                "group_name": group.title,
                "optimal_interval": interval,
                "participants": group.participants_count,
                "category": group.category,
                "metadata": group.group_metadata
            })
        
        return {
            "user_id": current_user.id,
            "group_intervals": group_intervals,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimal interval bilgisi alınamadı: {str(e)}"
        )

@router.get("/cooled-groups", response_model=Dict[str, Any])
async def get_cooled_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soğutma modundaki grupların listesini ve detaylarını döndürür
    """
    try:
        # ScheduledMessagingService'i al
        scheduler_service = get_scheduled_messaging_service(db)
        
        # Soğutmadaki grupları al
        cooled_groups = await scheduler_service.get_group_cooldown_info(current_user.id)
        
        return {
            "user_id": current_user.id,
            "cooled_groups": cooled_groups,
            "count": len(cooled_groups),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Soğutma bilgisi alınamadı: {str(e)}"
        )

@router.post("/reset-cooldown/{group_id}", response_model=Dict[str, Any])
async def reset_group_cooldown(
    group_id: str = Path(..., description="Soğutması sıfırlanacak grup ID'si"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Belirli bir grup için soğutma modunu manuel olarak sıfırlar
    """
    try:
        # ScheduledMessagingService'i al
        scheduler_service = get_scheduled_messaging_service(db)
        
        # Grup kullanıcıya ait mi kontrol et
        group = db.query(Group).filter(
            Group.telegram_id == group_id,
            Group.user_id == current_user.id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grup {group_id} bulunamadı veya size ait değil"
            )
        
        # Soğutmayı sıfırla
        result = await scheduler_service.reset_group_cooldown(group_id)
        
        if not result["success"]:
            return {
                "success": False,
                "message": result["message"],
                "group_id": group_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return {
            "success": True,
            "message": f"Grup {group.title} için soğutma sıfırlandı",
            "group_id": group_id,
            "group_name": group.title,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Soğutma sıfırlama hatası: {str(e)}"
        )

@router.get("/scheduled-stats", response_model=Dict[str, Any])
async def get_scheduled_message_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Zamanlanmış mesaj gönderimi ile ilgili detaylı istatistikleri döndürür
    """
    try:
        # ScheduledMessagingService'i al
        scheduler_service = get_scheduled_messaging_service(db)
        
        # İstatistikleri al
        stats = await scheduler_service.get_scheduled_messages_stats(current_user.id)
        
        return {
            "user_id": current_user.id,
            "statistics": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Zamanlama istatistik hatası: {str(e)}"
        )

@router.get("/scheduler-status", response_model=Dict[str, Any])
async def get_scheduler_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Kullanıcının mesaj zamanlayıcısının mevcut durumunu döndürür
    """
    try:
        # ScheduledMessagingService'i al
        scheduler_service = get_scheduled_messaging_service(db)
        
        # Zamanlayıcı durumunu al
        status = scheduler_service.get_scheduler_status(current_user.id)
        
        return status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Zamanlayıcı durum hatası: {str(e)}"
        ) 