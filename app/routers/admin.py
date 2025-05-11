from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import or_

from app.database import get_db
from app.models import User, ApiKey, UserActivity
from app.schemas import ApiKeyCreate, ApiKeyResponse, UserActivityResponse
from app.dependencies import get_current_admin_user

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin_user)]
)

# API Anahtarı Yönetimi
@router.post("/api-keys", response_model=ApiKeyResponse)
def create_api_key(api_key: ApiKeyCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    # Yeni API anahtarı oluştur
    raw_key = secrets.token_hex(32)
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    
    # Son kullanma tarihi hesapla (varsa)
    expires_at = None
    if api_key.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=api_key.expires_days)
    
    # Veritabanına kaydet
    db_api_key = ApiKey(
        user_id=api_key.user_id or current_user.id,
        name=api_key.name,
        hashed_key=hashed_key,
        expires_at=expires_at
    )
    
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    
    # Kullanıcı aktivitesini kaydet
    activity = UserActivity(
        user_id=current_user.id,
        action="create_api_key",
        resource_type="api_key",
        resource_id=db_api_key.id,
        ip_address=request.client.host,
        details={"api_key_name": api_key.name, "for_user_id": api_key.user_id or current_user.id}
    )
    db.add(activity)
    db.commit()
    
    # Yanıtta ham anahtarı göster (bir kez gösterilecek)
    return {
        "success": True,
        "message": "API key created successfully",
        "data": {
            "id": db_api_key.id,
            "name": db_api_key.name,
            "key": raw_key,  # Sadece oluşturulduğunda bir kez gösterilir
            "created_at": db_api_key.created_at,
            "expires_at": db_api_key.expires_at,
            "user_id": db_api_key.user_id
        }
    }

@router.get("/api-keys", response_model=List[ApiKeyResponse])
def get_api_keys(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    # Tüm API anahtarlarını getir
    api_keys = db.query(ApiKey).all()
    return {
        "success": True,
        "message": "API keys retrieved successfully",
        "data": api_keys
    }

@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(key_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    # API anahtarını bul
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "API anahtarı bulunamadı", "data": {}}
        )
    
    # Aktivite logla
    activity = UserActivity(
        user_id=current_user.id,
        action="delete_api_key",
        resource_type="api_key",
        resource_id=api_key.id,
        ip_address=request.client.host,
        details={"api_key_name": api_key.name, "user_id": api_key.user_id}
    )
    db.add(activity)
    
    # Anahtarı sil
    db.delete(api_key)
    db.commit()
    
    return {
        "success": True,
        "message": "API key deleted successfully",
        "data": {}
    }

# Kullanıcı Aktivitesi İzleme
@router.get("/user-activities", response_model=List[UserActivityResponse])
def get_user_activities(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    # Filtrelerle sorgu oluştur
    query = db.query(UserActivity)
    
    if user_id:
        query = query.filter(UserActivity.user_id == user_id)
    if action:
        query = query.filter(UserActivity.action == action)
    if resource_type:
        query = query.filter(UserActivity.resource_type == resource_type)
    if start_date:
        query = query.filter(UserActivity.created_at >= start_date)
    if end_date:
        query = query.filter(UserActivity.created_at <= end_date)
    
    # Sıralama ve sayfalama
    total = query.count()
    activities = query.order_by(UserActivity.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "message": "User activities retrieved successfully",
        "data": activities
    }

# Sistem Durum İzleme
@router.get("/system-status")
def get_system_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    # Basit sistem istatistikleri hesapla
    user_count = db.query(User).count()
    active_user_count = db.query(User).filter(User.is_active == True).count()
    
    # Son 24 saatteki aktivite
    last_24h = datetime.utcnow() - timedelta(hours=24)
    activity_count = db.query(UserActivity).filter(UserActivity.created_at >= last_24h).count()
    
    # API anahtarı kullanımı
    api_keys_count = db.query(ApiKey).count()
    active_api_keys = db.query(ApiKey).filter(
        ApiKey.is_active == True,
        or_(ApiKey.expires_at == None, ApiKey.expires_at > datetime.utcnow())
    ).count()
    
    # Döndürülecek durum bilgisi
    return {
        "success": True,
        "message": "System status retrieved successfully",
        "data": {
            "users": {
                "total": user_count,
                "active": active_user_count
            },
            "api_keys": {
                "total": api_keys_count,
                "active": active_api_keys
            },
            "activities": {
                "last_24h": activity_count
            },
            "system": {
                "timestamp": datetime.utcnow(),
                "status": "healthy"
            }
        }
    } 