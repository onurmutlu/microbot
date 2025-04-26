import os
import logging
from datetime import datetime
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
import uvicorn
import asyncio
import json
from typing import List, Optional, Dict
from contextlib import asynccontextmanager

from app.database import SessionLocal, engine, Base
from app.routers import auth, groups, messages, logs, auto_reply, message_template, scheduler
from app.services.scheduled_messaging import get_scheduled_messaging_service
from app.config import settings
from app.api.v1.endpoints import router as api_router
from app.services.telegram_service import TelegramService
from app.core.websocket import websocket_manager

# Prometheus metrik izleme için yeni eklemeler
from prometheus_fastapi_instrumentator import Instrumentator
import time

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log")
    ]
)

logger = logging.getLogger(__name__)

# Veritabanı tablolarını oluştur
Base.metadata.create_all(bind=engine)

# Aktif telegram service instance'larını tutacak dictionary
active_telegram_instances: Dict[int, TelegramService] = {}
active_schedulers: Dict[int, bool] = {}

# Lifespan ile uygulama başlangıç ve bitiş olaylarını yönet
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup olayları burada gerçekleşir
    try:
        # Gerekli dizinleri oluştur
        os.makedirs("logs", exist_ok=True)
        os.makedirs("sessions", exist_ok=True)

        # Veritabanı bağlantısını kontrol et
        db = SessionLocal()
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            logger.info("Veritabanı bağlantısı başarılı")
            
            # Aktif tüm kullanıcıların otomatik başlatması
            await start_telegram_handlers_for_all_users(db)
            
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
        finally:
            db.close()
            
        logger.info("Uygulama başlatıldı")
    except Exception as e:
        logger.error(f"Uygulama başlangıç hatası: {str(e)}")

    yield  # Bu noktada FastAPI uygulaması çalışmaya devam eder

    # Shutdown olayları burada gerçekleşir
    try:
        # Tüm zamanlayıcıları durdur
        scheduler_service = get_scheduled_messaging_service(next(get_db()))
        await scheduler_service.stop_all_schedulers()

        # Tüm Telegram handler'larını durdur
        await stop_all_telegram_handlers()
        
        logger.info("Uygulama düzgün şekilde kapatıldı")
    except Exception as e:
        logger.error(f"Uygulama kapatma hatası: {str(e)}")

# FastAPI uygulamasını oluştur
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Prometheus metrikleri
Instrumentator().instrument(app).expose(app)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Swagger'da Bearer token kutusu açılmasını sağlayan özel tanım
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler'lar
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin."}
    )

# API router'ını ekle
app.include_router(api_router, prefix=settings.API_V1_STR)

# Router'ları ekle
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(auto_reply.router, tags=["Auto Reply"])
app.include_router(message_template.router, prefix="/api/message-templates", tags=["Message Templates"])
app.include_router(scheduler.router, tags=["Scheduler"])

# Veritabanı bağımlılığı
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Tüm kullanıcılar için Telegram handler'larını başlat
async def start_telegram_handlers_for_all_users(db: Session):
    """Tüm aktif kullanıcılar için Telegram event handler'larını başlatır"""
    from app.models.user import User
    
    try:
        # Aktif kullanıcıları al
        active_users = db.query(User).filter(User.is_active == True).all()
        
        if not active_users:
            logger.info("Başlatılacak aktif kullanıcı bulunamadı")
            return
            
        logger.info(f"{len(active_users)} aktif kullanıcı için Telegram handler'ları başlatılıyor")
        
        for user in active_users:
            try:
                # Kullanıcının ayarlarını kontrol et (auto_start_bots vs.)
                # Not: Bu alan tablonuzda yoksa ekleyebilir veya her kullanıcı için başlatabilirsiniz
                if not hasattr(user, 'auto_start_bots') or user.auto_start_bots:
                    telegram_service = TelegramService(db, user.id)
                    
                    try:
                        # Event handler'ları başlat
                        await telegram_service.start_event_handlers()
                        active_telegram_instances[user.id] = telegram_service
                        logger.info(f"Kullanıcı {user.id} için Telegram handler'ları başlatıldı")
                        
                        # Auto-scheduling başlat
                        if hasattr(user, 'auto_start_scheduling') and user.auto_start_scheduling:
                            scheduler_service = get_scheduled_messaging_service(db)
                            await scheduler_service.start_scheduler_for_user(user.id)
                            active_schedulers[user.id] = True
                            logger.info(f"Kullanıcı {user.id} için otomatik zamanlama başlatıldı")
                    except Exception as e:
                        logger.error(f"Kullanıcı {user.id} için handler başlatma hatası: {str(e)}")
            except Exception as user_e:
                logger.error(f"Kullanıcı {user.id} işlemesi sırasında hata: {str(user_e)}")
    except Exception as e:
        logger.error(f"Tüm kullanıcılar için handler başlatma hatası: {str(e)}")

# Tüm Telegram handler'larını durdur
async def stop_all_telegram_handlers():
    """Tüm aktif Telegram event handler'larını durdurur"""
    for user_id, telegram_service in active_telegram_instances.items():
        try:
            await telegram_service.stop_event_handlers()
            logger.info(f"Kullanıcı {user_id} için Telegram handler'ları durduruldu")
        except Exception as e:
            logger.error(f"Kullanıcı {user_id} için handler durdurma hatası: {str(e)}")

# Root endpoint
@app.get("/")
async def root():
    return {"message": "MicroBot API'ye hoş geldiniz"}

# Sağlık kontrolü
@app.get("/health", tags=["Health"])
async def health_check():
    # Aktif handler ve zamanlayıcı sayılarını da ekle
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": os.environ.get("APP_VERSION", settings.VERSION),
        "active_telegram_handlers": len(active_telegram_instances),
        "active_schedulers": len(active_schedulers)
    }

# Sistem durumu
@app.get("/system/status", tags=["System"])
async def system_status():
    """Sistem durumunu ve aktif telegram handler'larını gösterir"""
    return {
        "active_telegram_handlers": list(active_telegram_instances.keys()),
        "active_schedulers": list(active_schedulers.keys()),
        "system_start_time": datetime.now().isoformat(),
        "version": settings.VERSION
    }

# Telegram handler'larını manuel yeniden başlatma
@app.post("/system/restart-handlers", tags=["System"])
async def restart_handlers():
    """Tüm telegram handler'larını yeniden başlatır"""
    try:
        await stop_all_telegram_handlers()
        active_telegram_instances.clear()
        active_schedulers.clear()
        
        db = next(get_db())
        await start_telegram_handlers_for_all_users(db)
        
        return {
            "success": True,
            "message": "Tüm Telegram handler'ları yeniden başlatıldı",
            "active_handlers": len(active_telegram_instances)
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Hata: {str(e)}"
        }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = f"anonymous_{datetime.now().timestamp()}"
    try:
        await websocket_manager.connect(websocket, client_id)
        await websocket.send_json({"type": "connection_established", "client_id": client_id})
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Mesaj işleme
                await websocket.send_json({"type": "message_received", "data": message})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Geçersiz JSON formatı"})
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket hatası: {str(e)}")
        try:
            await websocket_manager.disconnect(websocket, client_id)
        except:
            pass

# Geliştirme sunucusunu çalıştır
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
