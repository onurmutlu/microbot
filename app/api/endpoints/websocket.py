from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.services.websocket_service import websocket_manager
from app.core.logging import logger
from app.core.auth import get_current_user
from app.models.user import User
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
import json
from datetime import datetime
from typing import Optional
from app.core.security import decode_access_token
from app.core.monitoring import websocket_monitor

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
) -> None:
    if not token:
        await websocket.close(code=1008, reason="Token required")
        return

    try:
        # Token doğrulama
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return

        # Kullanıcı doğrulama
        current_user = await get_current_user(token, db)
        if not current_user:
            await websocket.close(code=1008, reason="User not found")
            return

        # WebSocket bağlantısını başlat
        await websocket_manager.connect(websocket, token)
        
        try:
            while True:
                # Mesaj al
                data = await websocket.receive_json()
                
                # Mesaj tipini kontrol et
                message_type = data.get("type")
                if not message_type:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Message type is required"
                    })
                    continue

                # Mesajı işle
                try:
                    await handle_message(data, user_id, db)
                    logger.info(f"Message processed: {message_type}")
                    websocket_monitor.message_processed(user_id, message_type)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Error processing message"
                    })
                    
        except WebSocketDisconnect:
            await websocket_manager.disconnect(token)
            logger.info(f"WebSocket disconnected: {user_id}")
            
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            await websocket.close(code=1011, reason=str(e))
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        await websocket.close(code=1011, reason=str(e))

async def handle_message(message: dict, user_id: str, db: Session) -> None:
    """Gelen mesajları işle"""
    message_type = message.get("type")
    
    if message_type == "subscribe":
        channel = message.get("channel")
        if channel:
            await websocket_manager.subscribe(user_id, channel)
            
    elif message_type == "unsubscribe":
        channel = message.get("channel")
        if channel:
            await websocket_manager.unsubscribe(user_id, channel)
            
    elif message_type == "update_template":
        template_id = message.get("template_id")
        content = message.get("content")
        if template_id and content:
            template = db.query(MessageTemplate).filter_by(id=template_id, user_id=user_id).first()
            if template:
                template.content = content
                db.commit()
                await websocket_manager.broadcast({
                    "type": "template_updated",
                    "template_id": template_id,
                    "content": content
                })
                
    elif message_type == "update_rule":
        rule_id = message.get("rule_id")
        pattern = message.get("pattern")
        response = message.get("response")
        if rule_id and pattern and response:
            rule = db.query(AutoReplyRule).filter_by(id=rule_id, user_id=user_id).first()
            if rule:
                rule.pattern = pattern
                rule.response = response
                db.commit()
                await websocket_manager.broadcast({
                    "type": "rule_updated",
                    "rule_id": rule_id,
                    "pattern": pattern,
                    "response": response
                })
                
    elif message_type == "update_group":
        group_id = message.get("group_id")
        name = message.get("name")
        members = message.get("members")
        if group_id and name and members:
            group = db.query(Group).filter_by(id=group_id, user_id=user_id).first()
            if group:
                group.name = name
                group.members = members
                db.commit()
                await websocket_manager.broadcast({
                    "type": "group_updated",
                    "group_id": group_id,
                    "name": name,
                    "members": members
                })
                
    elif message_type == "update_scheduler":
        scheduler_id = message.get("scheduler_id")
        status = message.get("status")
        if scheduler_id and status:
            scheduler = db.query(Scheduler).filter_by(id=scheduler_id, user_id=user_id).first()
            if scheduler:
                scheduler.status = status
                db.commit()
                await websocket_manager.broadcast({
                    "type": "scheduler_updated",
                    "scheduler_id": scheduler_id,
                    "status": status
                })
                
    else:
        raise ValueError(f"Unknown message type: {message_type}")

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Bağlantıyı kabul et ve yönet
        await websocket_manager.connect(websocket, user_id)
        
        # İlk bağlantıda veri senkronizasyonu
        await send_initial_data(websocket, user_id, db)
        
        while True:
            try:
                # WebSocket'ten mesaj al
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Mesaj tipine göre işlem yap
                await handle_message(message, user_id, db)
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from user {user_id}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message format"
                })
            except Exception as e:
                logger.error(f"Error processing message from user {user_id}: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal server error"
                })
                
    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected")
        await websocket_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        await websocket_manager.disconnect(user_id)
        raise HTTPException(status_code=500, detail="WebSocket connection error")

async def send_initial_data(websocket: WebSocket, user_id: str, db: Session):
    """İlk bağlantıda gerekli verileri gönder"""
    try:
        # Mesaj şablonlarını getir
        templates = db.query(MessageTemplate).filter_by(user_id=user_id).all()
        await websocket.send_json({
            "type": "initial_data",
            "templates": [template.to_dict() for template in templates]
        })
        
        # Otomatik yanıt kurallarını getir
        rules = db.query(AutoReplyRule).filter_by(user_id=user_id).all()
        await websocket.send_json({
            "type": "initial_data",
            "rules": [rule.to_dict() for rule in rules]
        })
        
        # Grup listesini getir
        groups = db.query(Group).filter_by(user_id=user_id).all()
        await websocket.send_json({
            "type": "initial_data",
            "groups": [group.to_dict() for group in groups]
        })
        
        # Zamanlayıcı durumlarını getir
        schedulers = db.query(Scheduler).filter_by(user_id=user_id).all()
        await websocket.send_json({
            "type": "initial_data",
            "schedulers": [scheduler.to_dict() for scheduler in schedulers]
        })
        
    except Exception as e:
        logger.error(f"Error sending initial data to user {user_id}: {str(e)}") 