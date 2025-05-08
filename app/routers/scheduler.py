from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_active_user
from app.services.scheduled_messaging import get_scheduled_messaging_service

router = APIRouter(
    prefix="/scheduler",
    tags=["scheduler"]
)

@router.post("/start", response_model=Dict[str, Any])
async def start_scheduler(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcı için zamanlanmış mesaj gönderimini başlatır.
    
    Mesaj şablonlarının interval_minutes değerine göre belirlenen aralıklarla otomatik mesaj gönderimi yapılır.
    Sadece aktif şablonlar ve seçili gruplar için çalışır.
    """
    scheduler_service = get_scheduled_messaging_service(db)
    result = await scheduler_service.start_scheduler_for_user(current_user.id)
    return result

@router.post("/stop", response_model=Dict[str, Any])
async def stop_scheduler(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcı için zamanlanmış mesaj gönderimini durdurur.
    """
    scheduler_service = get_scheduled_messaging_service(db)
    result = await scheduler_service.stop_scheduler_for_user(current_user.id)
    return result

@router.get("/status", response_model=Dict[str, Any])
async def get_scheduler_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcı için zamanlanmış mesaj gönderiminin durumunu kontrol eder.
    
    Dönüş değerleri:
    - is_running: Zamanlayıcının çalışıp çalışmadığı
    - active_templates: Aktif şablon sayısı
    - messages_last_24h: Son 24 saatte gönderilen mesaj sayısı
    """
    scheduler_service = get_scheduled_messaging_service(db)
    status = await scheduler_service.get_scheduler_status(current_user.id)
    return status

@router.post("/validate-cron", response_model=Dict[str, Any])
async def validate_cron_expression(
    cron_expression: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cron ifadesinin geçerliliğini kontrol eder ve sonraki çalışma zamanlarını döndürür.
    
    Standart cron formatında (dakika saat gün ay haftanın_günü) bir ifade beklenir.
    Örnek: "0 9 * * 1-5" (Hafta içi her gün saat 9'da)
    
    Dönüş değerleri:
    - is_valid: İfadenin geçerli olup olmadığı
    - next_dates: Sonraki 5 çalışma zamanı (ISO formatında)
    - error: Hata varsa açıklaması
    """
    scheduler_service = get_scheduled_messaging_service(db)
    result = await scheduler_service.validate_cron_expression(cron_expression)
    return result

@router.get("/auto-start-settings", response_model=Dict[str, Any]) 
async def get_auto_start_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcının otomatik başlatma ayarlarını getirir.
    """
    return {
        "auto_start_bots": current_user.auto_start_bots,
        "auto_start_scheduling": current_user.auto_start_scheduling
    }

@router.post("/auto-start-settings", response_model=Dict[str, Any])
async def update_auto_start_settings(
    settings: Dict[str, bool] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcının otomatik başlatma ayarlarını günceller.
    
    Ayarlanabilir değerler:
    - auto_start_bots: Uygulama başlatıldığında Telegram event handler'larını otomatik başlatma
    - auto_start_scheduling: Uygulama başlatıldığında zamanlı mesaj gönderimini otomatik başlatma
    """
    # Ayarları güncelle
    if "auto_start_bots" in settings:
        current_user.auto_start_bots = settings["auto_start_bots"]
    
    if "auto_start_scheduling" in settings:
        current_user.auto_start_scheduling = settings["auto_start_scheduling"]
    
    db.commit()
    
    return {
        "success": True,
        "message": "Otomatik başlatma ayarları güncellendi",
        "auto_start_bots": current_user.auto_start_bots,
        "auto_start_scheduling": current_user.auto_start_scheduling
    } 