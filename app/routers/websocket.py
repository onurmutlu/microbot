from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import asyncio
import json
from datetime import datetime, timedelta

from app.services.auth_service import get_current_user, get_token_data, validate_telegram_login
from app.services.websocket_manager import websocket_manager
from app.models.user import User
from app.database import get_db
from app.core.logging import logger
from app.config import settings

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket):
    """
    Ana WebSocket bağlantı noktası.
    
    WebSocket üzerinden gerçek zamanlı iletişim sağlar.
    """
    client_id = str(uuid.uuid4())
    try:
        # Parametreleri alma
        query_params = websocket.query_params
        token = query_params.get("token")
        
        # Token yoksa anonim bağlantı
        user_id = None
        
        # Token varsa doğrulama
        if token:
            try:
                # Token doğrulama fonksiyonunu kullan
                token_data = await get_token_data(token)
                if token_data:
                    user_id = token_data.sub
                    logger.info(f"WebSocket bağlantısı kimlik doğrulaması başarılı: {user_id}")
                else:
                    # Token geçersiz, anonim bağlantı
                    logger.warning(f"WebSocket için geçersiz token: {token[:10]}...")
            except Exception as e:
                logger.error(f"WebSocket token doğrulama hatası: {str(e)}")
                
        # WebSocket yöneticisine bağlantıyı işlet
        await websocket_manager.handle_websocket(websocket, client_id, user_id)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket bağlantısı kesildi: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket hatası: {str(e)}")
        await websocket.close(code=1011)  # Internal Server Error

@router.websocket("/auth")
async def websocket_auth_endpoint(websocket: WebSocket):
    """
    Kimlik doğrulama gerektiren WebSocket bağlantı noktası.
    
    Token olmadan erişime izin verilmez.
    """
    client_id = str(uuid.uuid4())
    
    try:
        # Token al
        query_params = websocket.query_params
        token = query_params.get("token")
        
        if not token:
            # Token olmayanları kabul etme
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "Kimlik doğrulama gerekli",
                "code": "unauthorized"
            })
            await websocket.close(code=1008)  # Policy Violation
            return
            
        # Token doğrulama
        token_data = await get_token_data(token)
        if not token_data:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "Geçersiz veya süresi dolmuş token",
                "code": "invalid_token"
            })
            await websocket.close(code=1008)
            return
            
        # WebSocket yöneticisine bağlantıyı işlet
        await websocket_manager.handle_websocket(websocket, client_id, token_data.sub)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket auth bağlantısı kesildi: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket auth hatası: {str(e)}")
        try:
            if not websocket.client_state == "disconnected":
                await websocket.close(code=1011)
        except:
            pass

@router.websocket("/channel/{channel_name}")
async def websocket_channel_endpoint(websocket: WebSocket, channel_name: str):
    """
    Belirli bir kanala WebSocket bağlantısı.
    
    Belirtilen kanala mesaj alıp göndermek için kullanılır.
    """
    client_id = f"{channel_name}_{str(uuid.uuid4())}"
    
    try:
        # Bağlantıyı kabul et
        await websocket.accept()
        
        # Parametreleri alma
        query_params = websocket.query_params
        token = query_params.get("token")
        user_id = None
        
        # Token kontrolü (opsiyonel)
        if token:
            token_data = await get_token_data(token)
            if token_data:
                user_id = token_data.sub
        
        # WebSocket Manager ile bağlantıyı yönet
        await websocket_manager.connect(websocket, client_id, user_id)
        
        # Kanala otomatik abone et
        if channel_name:
            await websocket_manager.subscribe(client_id, channel_name)
            logger.info(f"WebSocket client {client_id} kanala abone oldu: {channel_name}")
            
            # Hoş geldin mesajı gönder
            await websocket.send_json({
                "type": "welcome",
                "message": f"{channel_name} kanalına hoş geldiniz",
                "channel": channel_name,
                "timestamp": datetime.now().isoformat()
            })
        
        # Mesaj döngüsü
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Kanalda yayınla
            message["channel"] = channel_name
            message["timestamp"] = datetime.now().isoformat()
            message["client_id"] = client_id
            
            # Kullanıcı bilgisi ekle
            if user_id:
                message["user_id"] = user_id
                
            # Tüm abonelere mesajı yayınla
            await websocket_manager.publish_to_channel(channel_name, message)
            
    except WebSocketDisconnect:
        # Bağlantı kesildiğinde
        websocket_manager.disconnect(client_id)
        logger.info(f"WebSocket kanal bağlantısı kesildi: {client_id}, kanal: {channel_name}")
    except json.JSONDecodeError:
        # JSON hatası
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Geçersiz JSON formatı"
            })
        except:
            pass
        finally:
            websocket_manager.disconnect(client_id)
    except Exception as e:
        # Diğer hatalar
        logger.error(f"WebSocket kanal hatası: {str(e)}")
        try:
            if not websocket.client_state == "disconnected":
                await websocket.close(code=1011)
        except:
            pass
        websocket_manager.disconnect(client_id)

@router.get("/status")
async def websocket_status():
    """
    WebSocket sunucu durum bilgilerini döndürür.
    
    Aktif bağlantı sayısı, kanallar gibi bilgileri içerir.
    """
    stats = websocket_manager.get_stats()
    return JSONResponse(content=stats)

@router.post("/publish/{channel}")
async def publish_to_channel(
    channel: str, 
    message: Dict[str, Any],
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Belirli bir kanala mesaj yayınlar.
    
    REST API üzerinden WebSocket kanallarına mesaj göndermek için kullanılır.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli"
        )
    
    # Mesaja ek bilgiler ekle
    message["timestamp"] = datetime.now().isoformat()
    message["user_id"] = str(user.id)
    message["channel"] = channel
    message["source"] = "api"
    
    # Mesajı yayınla
    sent_count = await websocket_manager.publish_to_channel(channel, message)
    
    return {
        "success": True,
        "channel": channel,
        "recipients": sent_count,
        "message_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat()
    }

@router.post("/send/{user_id}")
async def send_to_user(
    user_id: str,
    message: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Belirli bir kullanıcıya mesaj gönderir.
    
    REST API üzerinden belirli bir kullanıcıya mesaj göndermek için kullanılır.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli"
        )
    
    # Mesaja ek bilgiler ekle
    message["timestamp"] = datetime.now().isoformat()
    message["from_user_id"] = str(current_user.id)
    message["source"] = "api"
    
    # Mesajı gönder
    sent_count = await websocket_manager.broadcast_to_user(user_id, message)
    
    if sent_count == 0:
        return {
            "success": False,
            "message": "Kullanıcı çevrimiçi değil veya WebSocket bağlantısı yok",
            "user_id": user_id
        }
    
    return {
        "success": True,
        "user_id": user_id,
        "recipients": sent_count,
        "message_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat()
    } 