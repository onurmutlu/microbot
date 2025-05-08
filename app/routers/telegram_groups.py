from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import random
import asyncio
from telethon import TelegramClient

from app.database import get_db
from app.models import User, TelegramSession, Group, SessionStatus, Member
from app.services.telegram_service import TelegramService
from app.services.auth_service import get_current_active_user
from app.discover_groups import discover_and_save_groups
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/telegram",
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

class FetchGroupsRequest(BaseModel):
    session_id: int = Field(..., description="Telegram oturum ID'si")

class FetchGroupsResponse(BaseModel):
    success: bool
    message: str
    groups: List[GroupResponse]

class MemberResponse(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    status: Optional[str]

class SendDMRequest(BaseModel):
    session_id: int
    user_ids: List[int]
    message: str

class SendDMResponse(BaseModel):
    success: List[int]
    failed: List[int]

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

# Tüm katılınan grupları çekme endpoint'i
@router.post("/fetch-joined-groups", response_model=FetchGroupsResponse)
async def fetch_joined_groups(
    request: FetchGroupsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
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
        
        # Tüm katılınan grupları çek
        groups = await telegram_service.fetch_all_joined_groups(
            session_id=request.session_id,
            db=db,
            user_id=current_user.id
        )
        
        # GroupResponse'a dönüştür
        group_responses = []
        for group in groups:
            joined_at = datetime.fromisoformat(group["joined_at"]) if isinstance(group["joined_at"], str) else group["joined_at"]
            group_responses.append(
                GroupResponse(
                    group_id=group["group_id"],
                    group_name=group["group_name"],
                    members_count=group["members_count"],
                    joined_at=joined_at
                )
            )
        
        return FetchGroupsResponse(
            success=True,
            message=f"{len(groups)} grup başarıyla çekildi",
            groups=group_responses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grup çekme hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gruplar çekilirken bir hata oluştu: {str(e)}"
        )

@router.get("/list-members", response_model=List[MemberResponse])
async def list_members(
    session_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
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
        
        members = db.query(Member).filter(
            Member.session_id == session_id,
            Member.group_id == group_id
        ).all()
        
        return [
            MemberResponse(
                user_id=member.user_id,
                username=member.username,
                first_name=member.first_name,
                last_name=member.last_name,
                status=member.status
            ) for member in members
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Üye listeleme hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Üyeler listelenirken bir hata oluştu: {str(e)}"
        )

@router.post("/send-dm", response_model=SendDMResponse)
async def send_dm(
    request: SendDMRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
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
        
        client = TelegramClient(
            session.session_string,
            settings.TELEGRAM_API_ID,
            settings.TELEGRAM_API_HASH
        )
        
        await client.connect()
        
        success = []
        failed = []
        
        for user_id in request.user_ids:
            try:
                await client.send_message(user_id, request.message)
                success.append(user_id)
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"DM gönderme hatası (user_id: {user_id}): {str(e)}")
                failed.append(user_id)
        
        await client.disconnect()
        
        return SendDMResponse(success=success, failed=failed)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DM gönderme hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DM gönderilirken bir hata oluştu: {str(e)}"
        ) 