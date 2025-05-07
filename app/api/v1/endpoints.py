from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime, timedelta
from app.database import SessionLocal, get_db
from app.models.group import Group
from app.models.user import User
from app.models.message import Message
from app.models.message_template import MessageTemplate
from app.models.task import Task, TaskStatus
from app.models.schedule import Schedule, ScheduleStatus
from app.core.websocket import websocket_manager
from app.services.sse_manager import sse_manager
from app.schemas.group import GroupCreate, GroupUpdate, GroupResponse
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.auth_service import AuthService, get_current_user
from app.core.logging import logger

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Dependency - Redundant, using app.database.get_db instead
# def get_db():
#    db = SessionLocal()
#    try:
#        yield db
#    finally:
#        db.close()

# WebSocket endpoint
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket_manager.handle_websocket(websocket, client_id)

# Server-Sent Events (SSE) endpoint
@router.get("/sse/{client_id}")
async def sse_endpoint(client_id: str):
    """Server-Sent Events (SSE) bağlantısını yönetir"""
    
    async def event_generator():
        """SSE için event verisi üreten generator"""
        try:
            # Bağlantı kurulduğunda başlangıç mesajı gönder
            logger.info(f"SSE bağlantısı kuruldu: {client_id}")
            yield f"data: {json.dumps({'type': 'connection', 'client_id': client_id, 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Message queue oluştur
            message_queue = asyncio.Queue()
            
            # SSE Manager'e kaydol
            await sse_manager.connect(client_id, message_queue)
            
            try:
                # Ping mesajı göndermek için task oluştur
                async def send_ping():
                    while True:
                        try:
                            await asyncio.sleep(30)  # 30 saniyede bir ping gönder
                            await message_queue.put({
                                "type": "ping",
                                "timestamp": datetime.now().isoformat()
                            })
                        except asyncio.CancelledError:
                            break
                        except Exception as e:
                            logger.error(f"SSE ping hatası: {str(e)}")
                
                # Ping task'ını başlat
                ping_task = asyncio.create_task(send_ping())
                
                # Mesajları dinlemeye başla
                while True:
                    # Queue'dan mesaj al
                    message = await message_queue.get()
                    
                    # Mesajı gönder
                    yield f"data: {json.dumps(message)}\n\n"
                    
                    # Queue işlemi tamamlandı
                    message_queue.task_done()
                    
            except asyncio.CancelledError:
                logger.info(f"SSE bağlantısı kapatıldı: {client_id}")
            except Exception as e:
                logger.error(f"SSE akış hatası: {str(e)}")
            finally:
                # Temizlik işlemleri
                ping_task.cancel()
                await sse_manager.disconnect(client_id)
                logger.info(f"SSE bağlantısı sonlandırıldı: {client_id}")
        
        except Exception as e:
            logger.error(f"SSE generator hatası: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.now().isoformat()})}\n\n"
    
    # SSE response döndür
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # NGINX için buffering'i devre dışı bırak
        }
    )

# SSE için mesaj broadcast endpoint'i
@router.post("/sse/broadcast")
async def broadcast_message(message: Dict[str, Any]):
    """Tüm SSE istemcilerine mesaj yayınlar"""
    try:
        # Mesajı tüm SSE istemcilerine yayınla
        await sse_manager.broadcast({
            "type": "broadcast",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        return {
            "success": True,
            "message": "Mesaj başarıyla yayınlandı",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"SSE broadcast hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mesaj yayınlama hatası: {str(e)}"
        )

# SSE için konuya abone olma endpoint'i
@router.post("/sse/subscribe/{client_id}/{topic}")
async def subscribe_to_topic(client_id: str, topic: str):
    """Bir istemciyi belirli bir konuya abone eder"""
    try:
        success = await sse_manager.subscribe(client_id, topic)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"İstemci bulunamadı veya abone olunamadı: {client_id}"
            )
        return {
            "success": True,
            "message": f"İstemci {topic} konusuna abone oldu",
            "data": {
                "client_id": client_id,
                "topic": topic,
                "timestamp": datetime.now().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSE abonelik hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Abonelik hatası: {str(e)}"
        )

# SSE için konuya mesaj yayınlama endpoint'i
@router.post("/sse/publish/{topic}")
async def publish_to_topic(topic: str, message: Dict[str, Any]):
    """Belirli bir konuya abone olan tüm istemcilere mesaj yayınlar"""
    try:
        recipient_count = await sse_manager.publish_to_topic(topic, {
            "type": "topic_message",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        return {
            "success": True,
            "message": f"Mesaj başarıyla {recipient_count} alıcıya yayınlandı",
            "data": {
                "topic": topic,
                "recipients": recipient_count,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"SSE konu yayınlama hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Konu yayınlama hatası: {str(e)}"
        )

# SSE istatistikleri endpoint'i
@router.get("/sse/stats")
async def get_sse_stats():
    """SSE yöneticisi hakkında istatistikler döndürür"""
    try:
        stats = sse_manager.get_stats()
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"SSE istatistik hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"İstatistik alma hatası: {str(e)}"
        )

# Group endpoints
@router.post("/groups/", response_model=GroupResponse)
async def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    db_group = Group(**group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@router.get("/groups/", response_model=List[GroupResponse])
async def read_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    groups = db.query(Group).offset(skip).limit(limit).all()
    return groups

@router.get("/groups/{group_id}", response_model=GroupResponse)
async def read_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Grup bulunamadı")
    return group

# User endpoints
@router.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/users/", response_model=List[UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/users/{user_id}", response_model=UserResponse)
async def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return user

# Dashboard endpoints
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

# Mevcut kullanıcıyı getir
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = AuthService.get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user 