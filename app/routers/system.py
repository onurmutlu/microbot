"""
Sistem durumu ve yönetimi için router modülü.

Bu modül, sistem durumu görüntüleme, uygulamayı yeniden başlatma, 
hata raporlarını görüntüleme gibi sistem yönetim fonksiyonlarını içerir.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import logging
import asyncio
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.core.auth import get_current_active_user
from app.services.telegram_service import TelegramService
from app.services.scheduled_messaging import get_scheduled_messaging_service
from app.services.websocket_manager import websocket_manager
from app.services.connection_store import connection_store
from app.services.reconnect_manager import reconnect_manager, ReconnectStrategy
from app.services.error_reporting import (
    error_reporter, ErrorCategory, ErrorSeverity
)

router = APIRouter(
    prefix="/system",
    tags=["System"],
    dependencies=[Depends(get_current_active_user)],
)

logger = logging.getLogger(__name__)

@router.get("/status")
async def system_status(db: Session = Depends(get_db)):
    """Sistem durumunu getir"""
    try:
        # Aktif telegram handler sayısı
        from app.main import active_telegram_instances, active_schedulers
        telegram_count = len(active_telegram_instances)
        scheduler_count = sum(1 for value in active_schedulers.values() if value)
        
        # Kullanıcılar ve gruplar
        user_count = db.query(User).count()
        
        # WebSocket bağlantıları
        websocket_stats = websocket_manager.get_connection_stats()
        connection_stats = connection_store.get_connection_stats()
        
        # Yeniden bağlanma istatistikleri
        reconnect_stats = reconnect_manager.get_stats()
        
        # Hata raporlama istatistikleri
        error_stats = error_reporter.get_stats()
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "version": "1.5.0",
            "uptime": "N/A",  # TODO: Uygulama uptime'ını hesapla
            "telegram": {
                "active_handlers": telegram_count,
                "active_schedulers": scheduler_count
            },
            "database": {
                "user_count": user_count,
            },
            "websocket": websocket_stats,
            "connections": {
                "total": connection_stats.total_connections,
                "active": connection_stats.active_connections,
                "peak": connection_stats.peak_connections,
            },
            "reconnect": reconnect_stats,
            "errors": {
                "total": error_stats.get("total_errors", 0),
                "active": error_stats.get("active_errors", 0),
                "by_category": error_stats.get("error_categories", {})
            }
        }
    except Exception as e:
        logger.error(f"Sistem durumu alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sistem durumu alınamadı: {str(e)}"
        )

@router.post("/restart-handlers")
async def restart_handlers(db: Session = Depends(get_db)):
    """Telegram handler'larını yeniden başlat"""
    try:
        # Aktif telegram handler'larını al
        from app.main import active_telegram_instances, active_schedulers
        from app.main import stop_all_telegram_handlers, start_telegram_handlers_for_all_users
        
        # Tüm handler'ları durdur
        await stop_all_telegram_handlers()
        
        # Tüm handler'ları yeniden başlat
        await start_telegram_handlers_for_all_users(db)
        
        return {
            "status": "success",
            "message": "Tüm Telegram handler'ları yeniden başlatıldı",
            "handlers_count": len(active_telegram_instances)
        }
    except Exception as e:
        logger.error(f"Handler'ları yeniden başlatırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Handler'lar yeniden başlatılamadı: {str(e)}"
        )

@router.get("/websocket-connections")
async def get_websocket_connections():
    """WebSocket bağlantı istatistiklerini getir"""
    try:
        return websocket_manager.get_connection_stats()
    except Exception as e:
        logger.error(f"WebSocket bağlantı istatistikleri alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bağlantı istatistikleri alınamadı: {str(e)}"
        )

@router.get("/connection-stats")
async def get_connection_stats():
    """ConnectionStore bağlantı istatistiklerini getir"""
    try:
        stats = connection_store.get_connection_stats()
        return {
            "total_connections": stats.total_connections,
            "active_connections": stats.active_connections,
            "messages_sent": stats.messages_sent,
            "messages_received": stats.messages_received,
            "failed_messages": stats.failed_messages,
            "connection_errors": stats.connection_errors,
            "avg_message_size": stats.avg_message_size,
            "peak_connections": stats.peak_connections,
            "last_updated": stats.last_updated
        }
    except Exception as e:
        logger.error(f"Bağlantı istatistikleri alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bağlantı istatistikleri alınamadı: {str(e)}"
        )

@router.get("/reconnect-stats")
async def get_reconnect_stats(client_id: Optional[str] = None):
    """Yeniden bağlanma istatistiklerini getir"""
    try:
        stats = reconnect_manager.get_stats(client_id)
        return stats.dict()
    except Exception as e:
        logger.error(f"Yeniden bağlanma istatistikleri alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Yeniden bağlanma istatistikleri alınamadı: {str(e)}"
        )

@router.post("/reconnect-strategy")
async def update_reconnect_strategy(strategy: str):
    """Yeniden bağlanma stratejisini güncelle"""
    try:
        try:
            reconnect_strategy = ReconnectStrategy(strategy)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Geçersiz yeniden bağlanma stratejisi: {strategy}. Geçerli değerler: {[s.value for s in ReconnectStrategy]}"
            )
        
        reconnect_manager.update_strategy(reconnect_strategy)
        return {
            "status": "success",
            "message": f"Yeniden bağlanma stratejisi güncellendi: {strategy}",
            "current_strategy": reconnect_manager.strategy
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yeniden bağlanma stratejisi güncellenirken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Yeniden bağlanma stratejisi güncellenemedi: {str(e)}"
        )

@router.get("/errors")
async def get_errors(
    limit: int = 10, 
    category: Optional[str] = None,
):
    """Son hata raporlarını getir"""
    try:
        error_cat = None
        if category:
            try:
                error_cat = ErrorCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Geçersiz hata kategorisi: {category}. Geçerli değerler: {[c.value for c in ErrorCategory]}"
                )
        
        errors = error_reporter.get_recent_errors(limit, error_cat)
        return errors
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hata raporları alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata raporları alınamadı: {str(e)}"
        )

@router.get("/error-stats")
async def get_error_stats():
    """Hata istatistiklerini getir"""
    try:
        return error_reporter.get_stats()
    except Exception as e:
        logger.error(f"Hata istatistikleri alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata istatistikleri alınamadı: {str(e)}"
        )

@router.post("/resolve-error/{error_id}")
async def resolve_error(error_id: str, notes: Optional[str] = None):
    """Bir hatayı çözüldü olarak işaretle"""
    try:
        success = await error_reporter.resolve_error(error_id, notes)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hata bulunamadı veya zaten çözülmüş: {error_id}"
            )
        
        return {
            "status": "success",
            "message": f"Hata çözüldü olarak işaretlendi: {error_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hata çözülürken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata çözülemedi: {str(e)}"
        )

@router.post("/clear-error-stats")
async def clear_error_stats():
    """Hata istatistiklerini temizle"""
    try:
        error_reporter.clear_stats()
        return {"status": "success", "message": "Hata istatistikleri temizlendi"}
    except Exception as e:
        logger.error(f"Hata istatistikleri temizlenirken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata istatistikleri temizlenemedi: {str(e)}"
        )

@router.post("/reset-connection/{client_id}")
async def reset_connection(client_id: str):
    """Belirli bir bağlantının yeniden bağlanma durumunu sıfırla"""
    try:
        reconnect_manager.reset_connection(client_id)
        return {
            "status": "success", 
            "message": f"Bağlantı sıfırlandı: {client_id}",
            "connection_info": reconnect_manager.get_connection_info(client_id)
        }
    except Exception as e:
        logger.error(f"Bağlantı sıfırlanırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bağlantı sıfırlanamadı: {str(e)}"
        ) 