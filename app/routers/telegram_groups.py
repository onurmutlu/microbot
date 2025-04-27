from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.database import get_db
from app.models import User, TelegramSession, Group, SessionStatus
from app.services.telegram_service import TelegramService
from app.services.auth_service import get_current_active_user
from app.discover_groups import discover_and_save_groups
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/telegram",
    tags=["telegram-groups"]
)

# Pydantic modelleri
class JoinGroupRequest(BaseModel):
    session_id: int = Field(..., description="Telegram oturum ID'si")
    group_link: str = Field(..., description="Katılınacak grup linki (https://t.me/... veya @...)")

class GroupResponse(BaseModel):
    group_id: int
    group_name: str
    members_count: Optional[int] = None
    joined_at: datetime

# Grup katılma endpoint'i
@router.post("/join-group", status_code=status.HTTP_201_CREATED)
async def join_telegram_group(
    request: JoinGroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Verilen grup linkine katılmak için kullanılır.
    Katılım başarılı olursa grup bilgileri veritabanına kaydedilir.
    
    - **session_id**: Kullanılacak Telegram oturum ID'si
    - **group_link**: Katılınacak grup linki (https://t.me/groupname veya @groupname formatında)
    """
    try:
        # Session kontrolü
        session = db.query(TelegramSession).filter(
            TelegramSession.id == request.session_id,
            TelegramSession.user_id == current_user.id,
            TelegramSession.status == SessionStatus.ACTIVE
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ID'si {request.session_id} olan aktif bir oturum bulunamadı."
            )
        
        # TelegramService oluştur
        telegram_service = TelegramService(db, current_user.id)
        
        # Gruba katılma işlemi
        result = await telegram_service.join_group(
            session_id=request.session_id,
            group_link=request.group_link
        )
        
        if result.get("success", False):
            # Başarılı katılım
            group_data = result.get("group_data", {})
            logger.info(f"User {current_user.id} - Session {request.session_id} - Grup {group_data.get('title')} katıldı.")
            
            return {
                "success": True,
                "message": result.get("message", "Gruba başarıyla katıldınız."),
                "group": {
                    "group_id": group_data.get("id"),
                    "group_name": group_data.get("title"),
                    "members_count": group_data.get("members_count"),
                    "joined_at": group_data.get("joined_at")
                }
            }
        else:
            # Hata durumu
            error_msg = result.get("message", "Gruba katılırken bir hata oluştu.")
            logger.error(f"Grup katılım hatası: {error_msg}")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grup katılım hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gruba katılırken bir hata oluştu: {str(e)}"
        )

# Katılınan grupları listeleme endpoint'i
@router.get("/list-joined-groups", response_model=List[GroupResponse])
async def list_joined_groups(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Belirtilen oturum üzerinden katılınan tüm grupları listeler.
    
    - **session_id**: Telegram oturum ID'si
    """
    try:
        # Session kontrolü
        session = db.query(TelegramSession).filter(
            TelegramSession.id == session_id,
            TelegramSession.user_id == current_user.id,
            TelegramSession.status == SessionStatus.ACTIVE
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ID'si {session_id} olan aktif bir oturum bulunamadı."
            )
        
        # Grupları getir
        groups = db.query(Group).filter(
            Group.session_id == session_id,
            Group.user_id == current_user.id
        ).order_by(Group.joined_at.desc()).all()
        
        return [
            GroupResponse(
                group_id=group.group_id,
                group_name=group.group_name,
                members_count=group.members_count,
                joined_at=group.joined_at
            ) for group in groups
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grup listeleme hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gruplar listelenirken bir hata oluştu: {str(e)}"
        )

# Tüm grupları keşfetme endpoint'i
@router.post("/discover-groups", status_code=status.HTTP_200_OK)
async def discover_all_groups(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Belirtilen oturum üzerinden Telegram'daki tüm grupları keşfeder ve kaydeder
    
    - **session_id**: Telegram oturum ID'si
    """
    try:
        # Session kontrolü
        session = db.query(TelegramSession).filter(
            TelegramSession.id == session_id,
            TelegramSession.user_id == current_user.id,
            TelegramSession.status == SessionStatus.ACTIVE
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ID'si {session_id} olan aktif bir oturum bulunamadı."
            )
        
        # Grupları keşfet
        discovered_groups = await discover_and_save_groups(db, current_user.id, session_id)
        
        if not discovered_groups:
            return {
                "success": True,
                "message": "Hiç grup bulunamadı veya keşif sırasında bir hata oluştu.",
                "groups_count": 0,
                "groups": []
            }
        
        return {
            "success": True,
            "message": f"{len(discovered_groups)} grup keşfedildi ve kaydedildi.",
            "groups_count": len(discovered_groups),
            "groups": discovered_groups
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grup keşif hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gruplar keşfedilirken bir hata oluştu: {str(e)}"
        ) 