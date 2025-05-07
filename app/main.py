import os
import logging
from datetime import datetime, timedelta
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn
import asyncio
import json
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import time
import uuid

from app.database import SessionLocal, engine, get_db
from app.models.base import Base
from app.routers import auth, groups, messages, logs, auto_reply, message_template, scheduler, dashboard
from app.routers.telegram_auth import router as telegram_auth
from app.routers.telegram_sessions import router as telegram_sessions
from app.services.scheduled_messaging import get_scheduled_messaging_service
from app.config import settings
from app.api.v1.endpoints import router as api_router
from app.services.telegram_service import TelegramService
from app.core.websocket import websocket_manager
from app.models.user import User
from app.models.message import Message
from app.models.group import Group
from app.models.message_template import MessageTemplate
from app.models.task import Task, TaskStatus
from app.models.schedule import Schedule, ScheduleStatus
from app.services.auth_service import get_current_user
from app.core.logging import logger, get_logger
from prometheus_fastapi_instrumentator import Instrumentator
from app.services.websocket_manager import websocket_manager
from app.services.sse_manager import sse_manager

# Uygulama logger'ı
logger = logging.getLogger("app.main")

# Uvicorn logger'ları için ayarlar
uvicorn_logger_names = ["uvicorn", "uvicorn.error", "uvicorn.access"]
for logger_name in uvicorn_logger_names:
    uvicorn_logger = logging.getLogger(logger_name)
    uvicorn_logger.handlers = []  # Mevcut handler'ları temizle
    uvicorn_logger.propagate = False  # Ana logger'a log gönderme

# Websocket logger'ı
websocket_logger = logging.getLogger("app")
websocket_logger.handlers = logger.handlers  # Ana logger ile aynı handlerları kullan

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
    lifespan=lifespan,
    description="MicroBot API"
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
    allow_origins=["http://localhost:5176", "http://localhost:5175", "http://localhost:5174", "http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)

# Statik dosyaları servis et
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# İstek işleme süresi middleware'i
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(
        f"İstek: {request.method} {request.url.path} - "
        f"İşlem süresi: {process_time:.2f}ms - "
        f"Durum kodu: {response.status_code}"
    )
    return response

# Hata işleyicileri
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_logger = get_logger("validation_error")
    error_logger.error(f"Doğrulama hatası: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_logger = get_logger("http_error")
    error_logger.error(f"HTTP Hatası: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    error_logger = get_logger("general_error")
    error_logger.exception(f"Beklenmeyen hata: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Sunucu hatası, lütfen daha sonra tekrar deneyin."},
    )

# API router'ını ekle
app.include_router(api_router, prefix="/api")

# Router'ları ekle - özel prefixleri olanlar
app.include_router(telegram_auth, prefix="/api")
app.include_router(telegram_sessions, prefix="/api")
app.include_router(scheduler, prefix="/api")
app.include_router(message_template, prefix="/api")

# Standart prefixli router'lar 
app.include_router(auth, prefix="/api")
app.include_router(groups, prefix="/api")
app.include_router(messages, prefix="/api")
app.include_router(logs, prefix="/api")
app.include_router(auto_reply, prefix="/api")
app.include_router(dashboard, prefix="/api")

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
def root():
    logger.info("Kök yoluna istek geldi")
    return {"message": f"MicroBot API'ye Hoş Geldiniz! Belgelere /docs adresinden erişebilirsiniz."}

# Sağlık kontrolü
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Sistem sağlık durumunu kontrol eder"""
    try:
        # Veritabanı bağlantısını kontrol et
        db = SessionLocal()
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
        finally:
            db.close()

        # Aktif handler ve zamanlayıcı sayılarını da ekle
        active_handlers = len(active_telegram_instances)
        active_scheduler_count = sum(1 for status in active_schedulers.values() if status)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_status,
            "active_handlers": active_handlers,
            "active_schedulers": active_scheduler_count
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Sistem durumu
@app.get("/system/status", tags=["System"])
async def system_status():
    return {
        "success": True,
        "message": "Sistem durumu",
        "data": {
            "active_telegram_instances": list(active_telegram_instances.keys()),
            "active_schedulers": list(active_schedulers.keys()),
            "server_time": datetime.utcnow()
        }
    }

# Telegram handler'larını manuel yeniden başlatma
@app.post("/system/restart-handlers", tags=["System"])
async def restart_handlers():
    try:
        await stop_all_telegram_handlers()
        db = SessionLocal()
        try:
            await start_telegram_handlers_for_all_users(db)
            return {
                "success": True,
                "message": "Tüm handler'lar yeniden başlatıldı",
                "data": {
                    "active_instances": list(active_telegram_instances.keys())
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Handler yeniden başlatma hatası: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Handler yeniden başlatma hatası: {str(e)}"
        )

# WebSocket endpoint
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket bağlantısını yönetir"""
    client_id = str(uuid.uuid4())
    user_id = "anonymous"
    
    try:
        # WebSocket bağlantısını başlat
        logger.info(f"WebSocket bağlantısı başlatıldı: {client_id}")
        
        # WebSocketManager'a bağlan
        await websocket_manager.connect(websocket, user_id, client_id)
        
        try:
            # Mesaj dinleme döngüsü
            while True:
                try:
                    # Mesaj bekle
                    data = await websocket.receive_text()
                    
                    # Gelen mesajı işle
                    try:
                        message = json.loads(data)
                        
                        # Mesaj türüne göre işlem yap
                        message_type = message.get("type", "message")
                        
                        if message_type == "subscribe" and "channel" in message:
                            # Kanal aboneliği
                            channel = message["channel"]
                            await websocket_manager.subscribe(client_id, channel)
                        elif message_type == "unsubscribe" and "channel" in message:
                            # Kanal aboneliği iptali
                            channel = message["channel"]
                            await websocket_manager.unsubscribe(client_id, channel)
                        elif message_type == "ping":
                            # Ping-pong kontrolleri
                            await websocket.send_json({
                                "type": "pong",
                                "client_id": client_id,
                                "timestamp": datetime.now().isoformat()
                            })
                        elif message_type == "broadcast" and "content" in message:
                            # İstemciden gelen yayın mesajı
                            await websocket_manager.broadcast({
                                "type": "broadcast",
                                "content": message["content"],
                                "sender": client_id,
                                "timestamp": datetime.now().isoformat()
                            })
                        else:
                            # Diğer mesaj türleri için genel işleme
                            await websocket_manager.broadcast({
                                "type": message_type,
                                "content": message,
                                "client_id": client_id,
                                "timestamp": datetime.now().isoformat()
                            })
                        
                        logger.debug(f"İşlenen mesaj: {message}")
                    except json.JSONDecodeError:
                        logger.error(f"Geçersiz JSON formatı: {data}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Geçersiz mesaj formatı",
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"WebSocket mesaj işleme hatası: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Mesaj işleme hatası: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        })
                except WebSocketDisconnect as wsd:
                    logger.info(f"WebSocket bağlantısı kapatıldı: {client_id} - Kod: {wsd.code}")
                    break
                except Exception as e:
                    logger.error(f"WebSocket mesaj alma hatası: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Bağlantı hatası: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                    # Ciddi bir hata varsa döngüden çık
                    if "socket" in str(e).lower() or "connection" in str(e).lower():
                        break
                    continue
                
        except WebSocketDisconnect as wsd:
            logger.info(f"WebSocket bağlantısı kapatıldı: {client_id} - Kod: {wsd.code}")
        except Exception as e:
            logger.error(f"WebSocket döngü hatası: {str(e)}")
        finally:
            # Bağlantıyı kapat ve temizle
            await websocket_manager.disconnect(user_id)
            
    except Exception as e:
        logger.error(f"WebSocket bağlantı hatası: {str(e)}")
        try:
            await websocket.close(code=1011, reason=f"Sunucu hatası: {str(e)}")
        except:
            pass

# SSE için mesaj broadcast endpoint'i
@app.post("/api/sse/broadcast")
async def broadcast_message(message: dict, request: Request):
    """Tüm SSE istemcilerine mesaj yayınlar"""
    try:
        # Mesajı tüm SSE istemcilerine yayınla
        await sse_manager.broadcast({
            "type": "broadcast",
            "content": message,
            "sender_ip": request.client.host if request.client else "unknown",
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

# Server-Sent Events (SSE) endpoint
@app.get("/api/sse")
async def sse_endpoint(request: Request):
    """Server-Sent Events (SSE) bağlantısını yönetir"""
    client_id = str(uuid.uuid4())
    user_id = "anonymous"
    
    # CORS kontrolü
    origin = request.headers.get("Origin", "")
    allowed_origins = [
        "http://localhost:5176", 
        "http://localhost:5175", 
        "http://localhost:5174", 
        "http://localhost:3000", 
        "http://localhost:8000"
    ]
    if origin and origin not in allowed_origins and '*' not in app.middleware_stack._middlewares[0].options.get('allow_origins', []):
        logger.warning(f"İzin verilmeyen kaynaktan SSE isteği: {origin}, client_ip: {request.client.host if request.client else 'unknown'}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu kaynaktan istek yapmaya yetkiniz yok"
        )
    
    async def event_generator():
        """SSE için event verisi üreten generator"""
        try:
            # Bağlantı kurulduğunda başlangıç mesajı gönder
            logger.info(f"SSE bağlantısı kuruldu: {client_id}, ip: {request.client.host if request.client else 'unknown'}")
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
            "X-Accel-Buffering": "no",  # NGINX için buffering'i devre dışı bırak
            "Access-Control-Allow-Origin": origin or "*",  # CORS için origin header'ı
            "Access-Control-Allow-Credentials": "true",    # Credentials (örn. cookie) gönderimi
            "Access-Control-Expose-Headers": "*"          # Tüm özel headerları expose et
        }
    )

# Telegram aktif oturum endpoint'i
@app.get("/api/telegram/active-session")
async def get_active_session():
    """Aktif Telegram oturumunu döndürür"""
    try:
        # Aktif oturum bilgilerini al
        active_session = {
            "is_active": True,
            "timestamp": datetime.now().isoformat()
        }
        return active_session
    except Exception as e:
        logger.error(f"Aktif oturum bilgisi alınamadı: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Aktif oturum bilgisi alınamadı"
        )

# SSE Test sayfası endpoint'i
@app.get("/sse-test", include_in_schema=False)
async def sse_test():
    """SSE test sayfasını döndürür"""
    from fastapi.responses import FileResponse
    return FileResponse("app/static/sse_test.html")

# SSE için konuya abone olma endpoint'i
@app.post("/api/sse/subscribe/{client_id}/{topic}")
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
@app.post("/api/sse/publish/{topic}")
async def publish_to_topic(topic: str, message: dict):
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
@app.get("/api/sse/stats", tags=["SSE"])
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

# Geliştirme sunucusunu çalıştır
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
