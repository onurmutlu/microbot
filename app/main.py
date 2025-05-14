import os
import logging
from datetime import datetime, timedelta
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn
import asyncio
import json
import sys
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import time
import uuid
import psutil
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Temel logging ayarlarını yap
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.database import SessionLocal, engine, get_db
from app.models.base import Base
from app.routers import auth, groups, messages, logs, auto_reply, message_template, scheduler, dashboard
from app.routers.telegram_auth import router as telegram_auth
from app.routers.telegram_sessions import router as telegram_sessions
from app.services.scheduled_messaging import get_scheduled_messaging_service
from app.config import settings
from app.api import router as api_v1_router  # API router'larını ekle
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
from app.services.cache_service import cache_service
from app.middleware.rate_limiter import add_rate_limiter
from app.middleware.cors import setup_secure_cors

# Uygulama logger'ı
logger = logging.getLogger("app.main")

# Uvicorn logger'ları için ayarlar
uvicorn_logger_names = ["uvicorn", "uvicorn.error", "uvicorn.access"]
for logger_name in uvicorn_logger_names:
    uvicorn_logger = logging.getLogger(logger_name)
    if not uvicorn_logger.handlers:
        uvicorn_logger.handlers = logger.handlers  # Ana logger ile aynı handlerları kullan
    uvicorn_logger.setLevel(logging.INFO)
    uvicorn_logger.propagate = True  # Ana logger'a log gönder

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
            
            # Redis önbellekleme servisini başlat
            if settings.CACHE_ENABLED:
                await cache_service.init()
                logger.info("Redis önbellekleme servisi başlatıldı")
            else:
                logger.info("Redis önbellekleme devre dışı bırakıldı")
            
            # Aktif tüm kullanıcıların otomatik başlatması
            await start_telegram_handlers_for_all_users(db)
            
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
        finally:
            db.close()
        
        # SSE ve WebSocket Manager temizlik görevlerini başlat
        try:
            websocket_manager.start_cleanup_task()
            sse_manager.start_cleanup_task()
            logger.info("WebSocket ve SSE temizlik görevleri başlatıldı")
        except Exception as e:
            logger.error(f"Temizlik görevlerini başlatma hatası: {str(e)}, uygulama devam ediyor")
            
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
        
        # WebSocket ve SSE Manager temizlik görevlerini durdur
        websocket_manager.stop_cleanup_task()
        sse_manager.stop_cleanup_task()
        
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

# Rate limiter ekle
add_rate_limiter(app)

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

# CORS ayarlarını yükle
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,  # Cookie erişimi için gerekli
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telegram MiniApp kimliklendirme middleware'i
@app.middleware("http")
async def telegram_miniapp_auth_middleware(request: Request, call_next):
    """
    Telegram MiniApp'den gelen istekleri özel olarak işler.
    initData içeren istekleri yakalayıp, hata durumunda uygun yanıt verir.
    """
    # İsteği işle
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        # Sadece Telegram MiniApp'den gelen istekleri özel olarak işle
        content_type = request.headers.get("content-type", "")
        
        is_miniapp_request = False
        body = None
        
        if "application/json" in content_type:
            try:
                body = await request.json()
                # initData varsa, bu bir MiniApp isteğidir
                is_miniapp_request = "initData" in body
            except:
                pass
        
        # MiniApp isteği ise özel işlem yap
        if is_miniapp_request and body:
            logger.warning(f"MiniApp isteği hatası yakalandı: {str(e)}")
            
            # Kullanıcı bilgisini alma
            user_data = body.get("user", {})
            if not user_data and body.get("initDataUnsafe"):
                user_data = body.get("initDataUnsafe", {}).get("user", {})
            
            # Daha anlamlı bir yanıt döndür
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=200,  # 401 yerine, MiniApp'in işleyebileceği 200 dön
                content={
                    "success": False,
                    "error": "auth_required",
                    "message": "Kimlik doğrulama gerekli",
                    "user_info": user_data
                }
            )
        
        # MiniApp isteği değilse normal hata yanıtı
        raise e

# Güvenlik önlemleri
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# Router'ları ekle
app.include_router(auth)
app.include_router(groups)
app.include_router(messages)
app.include_router(logs)
app.include_router(auto_reply)
app.include_router(message_template)
app.include_router(scheduler)
app.include_router(dashboard)
app.include_router(telegram_auth)
app.include_router(telegram_sessions)
app.include_router(api_v1_router)  # API v1 router'ını ekle

# Statik dosyaları sun
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
@app.get("/health", tags=["Health"], operation_id="main_health_check")
async def health_check(db: Session = Depends(get_db)):
    """
    Sistem sağlık kontrolü için kapsamlı endpoint.
    Veritabanı bağlantısı, telegram servisi durumu ve sistem kaynaklarını kontrol eder.
    """
    start_time = time.time()
    health_data = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "checks": {}
    }
    
    try:
        # Veritabanı bağlantı kontrolü
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            health_data["checks"]["database"] = {
                "status": "ok",
                "message": "Veritabanı bağlantısı aktif"
            }
        except Exception as e:
            health_data["status"] = "error"
            health_data["checks"]["database"] = {
                "status": "error",
                "message": f"Veritabanı bağlantı hatası: {str(e)}"
            }
        
        # Redis bağlantı kontrolü (önbellekleme)
        if settings.CACHE_ENABLED:
            try:
                # Redis bağlantısı kontrolü
                is_connected = await cache_service._redis.ping() if cache_service._redis else False
                
                if is_connected:
                    health_data["checks"]["redis"] = {
                        "status": "ok",
                        "message": "Redis bağlantısı aktif"
                    }
                else:
                    health_data["status"] = "warning"
                    health_data["checks"]["redis"] = {
                        "status": "warning",
                        "message": "Redis bağlantısı kurulamadı"
                    }
            except Exception as e:
                health_data["status"] = "warning"
                health_data["checks"]["redis"] = {
                    "status": "error",
                    "message": f"Redis bağlantı hatası: {str(e)}"
                }
        else:
            health_data["checks"]["redis"] = {
                "status": "disabled",
                "message": "Redis önbelleği devre dışı"
            }
        
        # Sistem kaynaklarını kontrol et
        memory = psutil.virtual_memory()
        health_data["checks"]["system"] = {
            "status": "ok",
            "cpu_percent": psutil.cpu_percent(),
            "memory_usage_percent": memory.percent,
            "memory_available_mb": round(memory.available / (1024 * 1024), 2)
        }
        
        # Aktif telegram instance sayısı
        health_data["checks"]["telegram"] = {
            "status": "ok",
            "active_instances": len(active_telegram_instances),
            "active_schedulers": len(active_schedulers)
        }
        
        # Check disk space
        disk = psutil.disk_usage('/')
        health_data["checks"]["disk"] = {
            "status": "ok",
            "free_space_gb": round(disk.free / (1024 * 1024 * 1024), 2),
            "used_percent": disk.percent
        }
        
        # Metrics durumu (Prometheus)
        if settings.METRICS_ENABLED:
            health_data["checks"]["metrics"] = {
                "status": "ok",
                "provider": "prometheus",
                "endpoint": settings.METRICS_PATH
            }
        else:
            health_data["checks"]["metrics"] = {
                "status": "disabled",
                "message": "Prometheus metrikleri devre dışı"
            }
        
        # GraphQL durumu
        if settings.GRAPHQL_ENABLED:
            health_data["checks"]["graphql"] = {
                "status": "ok",
                "endpoint": settings.GRAPHQL_PATH,
                "graphiql": settings.GRAPHIQL_ENABLED
            }
        else:
            health_data["checks"]["graphql"] = {
                "status": "disabled",
                "message": "GraphQL API devre dışı"
            }
        
        # Response time
        health_data["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        # Uygulama hazır olma durumu
        overall_status = health_data["status"]
        health_data["ready"] = overall_status == "ok"
        
        return health_data
    except Exception as e:
        logger.error(f"Sağlık kontrolü hatası: {str(e)}")
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
    
    try:
        # Bağlantıyı kabul et
        await websocket.accept()
        
        # Bağlantı bilgisini logla
        origin = websocket.headers.get("origin", "unknown")
        logger.info(f"WebSocket bağlantısı kabul edildi: {client_id}, origin: {origin}")
        
        # Token kontrolü yok, açık bağlantı (MiniApp için)
        await websocket_manager.handle_websocket(websocket, client_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket bağlantısı kesildi: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket hatası: {str(e)}")

# WebSocket endpoint - özel ID ile
@app.websocket("/api/ws/{client_id}")
async def websocket_endpoint_with_id(websocket: WebSocket, client_id: str):
    """WebSocket bağlantısını özel ID ile yönetir"""
    try:
        # Bağlantıyı kabul etmeden önce doğrulama parametrelerini kontrol et
        params = websocket.query_params
        auth_key = params.get("auth_key")
        
        # Bağlantıyı kabul et
        await websocket.accept()
        
        # Bağlantı bilgisini logla
        origin = websocket.headers.get("origin", "unknown")
        logger.info(f"WebSocket bağlantısı kabul edildi (özel ID): {client_id}, origin: {origin}, auth: {'yes' if auth_key else 'no'}")
        
        # MiniApp için özel kontrol - auth_key varsa ve Telegram'dan geliyorsa doğrula
        user_id = None
        if auth_key and ("t.me" in origin or "telegram" in origin or "tg://" in origin):
            try:
                # Burada basit bir doğrulama, gerçek uygulamada JWT token doğrulaması yapılabilir
                if len(auth_key) > 10:  # Basit kontrol
                    # Telegram ile doğrulanmış kullanıcı ID'si
                    from app.services.auth_service import get_token_data
                    token_data = await get_token_data(auth_key)
                    if token_data:
                        user_id = token_data.sub
                        logger.info(f"WebSocket auth başarılı (özel ID), user_id: {user_id}")
                    else:
                        logger.warning(f"WebSocket geçersiz auth_key (özel ID): {auth_key[:10]}...")
            except Exception as e:
                logger.error(f"WebSocket auth hatası (özel ID): {str(e)}")
        
        # MiniApp bilgisi varsa ekstra log tut
        init_data = params.get("tgWebAppData")
        if init_data:
            logger.info(f"WebSocket Telegram MiniApp bağlantısı: {client_id}")
        
        # WebSocketManager ile bağlantıyı yönet
        await websocket_manager.handle_websocket(websocket, client_id, user_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket bağlantısı kesildi (özel ID): {client_id}")
    except Exception as e:
        logger.error(f"WebSocket hatası (özel ID): {str(e)}", exc_info=True)

# Ek WebSocket endpoint'leri (diğer URL formatlarını desteklemek için)
@app.websocket("/ws")
async def websocket_endpoint_alt1(websocket: WebSocket):
    """Alternatif WebSocket bağlantı noktası"""
    await websocket_endpoint(websocket)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint_with_id_alt1(websocket: WebSocket, client_id: str):
    """Alternatif WebSocket bağlantı noktası (özel ID ile)"""
    await websocket_endpoint_with_id(websocket, client_id)

@app.websocket("/api/socket/{client_id}")
async def websocket_endpoint_with_id_alt2(websocket: WebSocket, client_id: str):
    """Alternatif WebSocket bağlantı noktası (özel ID ile)"""
    await websocket_endpoint_with_id(websocket, client_id)

@app.websocket("/socket/{client_id}")
async def websocket_endpoint_with_id_alt3(websocket: WebSocket, client_id: str):
    """Alternatif WebSocket bağlantı noktası (özel ID ile)"""
    await websocket_endpoint_with_id(websocket, client_id)

# Server-Sent Events (SSE) endpoint
@app.get("/api/sse")
async def sse_endpoint(request: Request):
    """Server-Sent Events (SSE) bağlantısını yönetir"""
    client_id = str(uuid.uuid4())
    user_id = "anonymous"
    
    # CORS kontrolü - Global CORS ayarlarını kullan, ayrıca kontrol etme
    origin = request.headers.get("Origin", "*")
    
    async def event_generator():
        """SSE için event verisi üreten generator"""
        try:
            # Bağlantı kurulduğunda başlangıç mesajı gönder
            logger.info(f"SSE bağlantısı kuruldu: {client_id}, ip: {request.client.host if request.client else 'unknown'}, origin: {origin}")
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
            "Access-Control-Allow-Origin": origin,  # CORS için origin header'ı
            "Access-Control-Allow-Credentials": "true",    # Credentials (örn. cookie) gönderimi
            "Access-Control-Expose-Headers": "Content-Type,Content-Length,Date,X-Request-ID"
        }
    )

# SSE endpoint - Belirli bir client_id ile
@app.get("/api/sse/{client_id}")
async def sse_endpoint_with_id(client_id: str, request: Request):
    """Belirli bir client_id ile SSE bağlantısını yönetir"""
    user_id = "anonymous"
    
    # CORS kontrolü - Global CORS ayarlarını kullan
    origin = request.headers.get("Origin", "*")
    
    async def event_generator():
        """SSE için event verisi üreten generator"""
        try:
            # Bağlantı kurulduğunda başlangıç mesajı gönder
            logger.info(f"SSE bağlantısı kuruldu (özel ID): {client_id}, ip: {request.client.host if request.client else 'unknown'}, origin: {origin}")
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
            "Access-Control-Allow-Origin": origin,  # CORS için origin header'ı
            "Access-Control-Allow-Credentials": "true",    # Credentials (örn. cookie) gönderimi
            "Access-Control-Expose-Headers": "Content-Type,Content-Length,Date,X-Request-ID"
        }
    )

# SSE için mesaj broadcast endpoint'i
@app.post("/api/sse/broadcast", operation_id="main_sse_broadcast")
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

# Ping endpoint'i (GET metodu)
@app.get("/api/ping", tags=["Health"])
async def ping():
    """Basit bir sağlık kontrolü için ping endpoint'i"""
    return {
        "status": "pong", 
        "timestamp": datetime.now().isoformat()
    }

# Ping endpoint'i (POST metodu)
@app.post("/api/ping", tags=["Health"])
async def ping_post():
    """Basit bir sağlık kontrolü için ping endpoint'i (POST metodu)"""
    return {
        "status": "pong", 
        "timestamp": datetime.now().isoformat()
    }

# SSE için konuya abone olma endpoint'i
@app.post("/api/sse/subscribe/{client_id}/{topic}", operation_id="main_sse_subscribe")
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
@app.post("/api/sse/publish/{topic}", operation_id="main_sse_publish")
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
@app.get("/api/sse/stats", tags=["SSE"], operation_id="main_get_sse_stats")
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

# SSE Test sayfası endpoint'i
@app.get("/sse-test", include_in_schema=False)
async def sse_test():
    """SSE test sayfasını döndürür"""
    from fastapi.responses import FileResponse
    return FileResponse("app/static/sse_test.html")

# API Test sayfası endpoint'i
@app.get("/api-test", include_in_schema=False)
async def api_test():
    """API test sayfasını döndürür"""
    html_content = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MicroBot API Test</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f8f9fa;
                color: #333;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #4a6cf7;
                border-bottom: 2px solid #eaeaea;
                padding-bottom: 10px;
            }
            h2 {
                margin-top: 30px;
                color: #5a5a5a;
            }
            .endpoint {
                background-color: #f1f5ff;
                padding: 15px;
                border-radius: 6px;
                margin: 15px 0;
                border-left: 4px solid #4a6cf7;
            }
            .endpoint h3 {
                margin-top: 0;
                color: #4a6cf7;
            }
            pre {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                overflow-x: auto;
            }
            .method {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 4px;
                font-weight: bold;
                margin-right: 8px;
            }
            .get { background-color: #e7f5ff; color: #0066cc; }
            .post { background-color: #e3f9e5; color: #00994c; }
            .info {
                background-color: #fffaeb;
                padding: 10px;
                border-radius: 4px;
                margin: 15px 0;
                border-left: 4px solid #ffcc00;
            }
            .graphql-container {
                margin-top: 30px;
            }
            .btn {
                background-color: #4a6cf7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                transition: background-color 0.3s;
            }
            .btn:hover {
                background-color: #3a5ce5;
            }
            #health-result, #graphql-result {
                margin-top: 15px;
                min-height: 50px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MicroBot API Test</h1>
            
            <div class="info">
                Bu sayfa, MicroBot API'lerini test etmek ve kullanımlarını göstermek için tasarlanmıştır.
            </div>
            
            <h2>API Sağlık Kontrolü</h2>
            <div class="endpoint">
                <h3><span class="method get">GET</span> /health</h3>
                <p>API'nin sağlık durumunu kontrol eder. Veritabanı, Redis, Prometheus ve diğer servislerin durumunu döndürür.</p>
                <button id="check-health" class="btn">Sağlık Kontrolü Yap</button>
                <div id="health-result"></div>
            </div>
            
            <div class="graphql-container">
                <h2>GraphQL API</h2>
                <div class="endpoint">
                    <h3><span class="method post">POST</span> /api/v1/graphql</h3>
                    <p>GraphQL API endpoint'i. Grup içgörüleri, mesaj optimizasyonu gibi işlemler için kullanılabilir.</p>
                    <button id="check-graphql" class="btn">GraphQL Bilgisi Al</button>
                    <div id="graphql-result"></div>
                </div>
                
                <h3>Örnek GraphQL Sorguları</h3>
                <pre>
query GetGroupInsights($groupId: Int!) {
  group_content_insights(group_id: $groupId) {
    status
    message_count
    success_rate
    recommendations {
      type
      message
    }
  }
}

mutation OptimizeMessage($message: String!, $groupId: Int!) {
  optimize_message(message: $message, group_id: $groupId) {
    original_message
    optimized_message
    applied_optimizations {
      type
      message
    }
  }
}
                </pre>
            </div>
            
            <h2>AI Endpoints</h2>
            <div class="endpoint">
                <h3><span class="method get">GET</span> /api/v1/ai/group-insights/{group_id}</h3>
                <p>Bir grubun içerik analizini ve performans önerilerini döndürür.</p>
            </div>
            <div class="endpoint">
                <h3><span class="method post">POST</span> /api/v1/ai/optimize-message</h3>
                <p>Verilen mesajı belirtilen grup için optimize eder.</p>
            </div>
            <div class="endpoint">
                <h3><span class="method post">POST</span> /api/v1/ai/batch-analyze</h3>
                <p>Birden fazla grubu toplu olarak analiz eder.</p>
            </div>
        </div>
        
        <script>
            document.getElementById('check-health').addEventListener('click', async () => {
                const resultDiv = document.getElementById('health-result');
                resultDiv.innerHTML = 'Kontrol ediliyor...';
                
                try {
                    const response = await fetch('/health');
                    const data = await response.json();
                    
                    resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
                } catch (error) {
                    resultDiv.innerHTML = `<p style="color: red">Hata: ${error.message}</p>`;
                }
            });
            
            document.getElementById('check-graphql').addEventListener('click', async () => {
                const resultDiv = document.getElementById('graphql-result');
                resultDiv.innerHTML = 'Kontrol ediliyor...';
                
                try {
                    const response = await fetch('/api/v1/graphql');
                    const data = await response.json();
                    
                    resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
                } catch (error) {
                    resultDiv.innerHTML = `<p style="color: red">Hata: ${error.message}</p>`;
                }
            });
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

# SSE için ping endpoint'i
@app.get("/api/sse/ping/{client_id}", tags=["SSE"])
async def sse_ping(client_id: str):
    """Belirli bir client_id için ping kontrolü"""
    return {
        "status": "pong", 
        "client_id": client_id,
        "timestamp": datetime.now().isoformat()
    }
    
# SSE için ping endpoint'i (POST metodu)
@app.post("/api/sse/ping/{client_id}", tags=["SSE"])
async def sse_ping_post(client_id: str):
    """Belirli bir client_id için ping kontrolü (POST metodu)"""
    return {
        "status": "pong", 
        "client_id": client_id,
        "timestamp": datetime.now().isoformat()
    }

# Telegram aktif oturum endpoint'i
@app.get("/api/telegram/active-session", operation_id="main_get_active_session")
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

# WebSocket Test sayfası
@app.get("/websocket-test", include_in_schema=False)
async def websocket_test():
    """WebSocket test sayfasını döndürür"""
    html_content = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MicroBot WebSocket Test</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f8f9fa;
                color: #333;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #4a6cf7;
            }
            .connection-controls {
                margin: 20px 0;
                padding: 15px;
                background-color: #f1f5ff;
                border-radius: 8px;
                border-left: 4px solid #4a6cf7;
            }
            .token-input {
                width: 100%;
                padding: 8px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .messages {
                margin-top: 20px;
                height: 300px;
                overflow-y: auto;
                border: 1px solid #eee;
                padding: 10px;
                border-radius: 4px;
                background-color: #f5f5f5;
                font-family: monospace;
            }
            .message {
                margin: 5px 0;
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            .sent {
                background-color: #e3f9e5;
            }
            .received {
                background-color: #e7f5ff;
            }
            .error {
                background-color: #ffebee;
                color: #d32f2f;
            }
            .status {
                margin-top: 10px;
                font-weight: bold;
            }
            .status.connected {
                color: #4caf50;
            }
            .status.disconnected {
                color: #f44336;
            }
            .button {
                background-color: #4a6cf7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                margin-right: 8px;
            }
            .button:hover {
                background-color: #3a5ce5;
            }
            .message-input {
                width: 70%;
                padding: 8px;
                margin-right: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MicroBot WebSocket Test</h1>
            
            <div class="connection-controls">
                <h3>Bağlantı Ayarları</h3>
                <input type="text" id="wsUrl" class="token-input" value="ws://localhost:8000/api/ws" placeholder="WebSocket URL">
                <input type="text" id="authToken" class="token-input" placeholder="JWT Token (opsiyonel)">
                <div>
                    <button id="connectBtn" class="button">Bağlan</button>
                    <button id="disconnectBtn" class="button" disabled>Bağlantıyı Kes</button>
                </div>
                <div class="status disconnected" id="status">Bağlantı kesik</div>
            </div>
            
            <div>
                <h3>Mesaj Gönder</h3>
                <input type="text" id="messageInput" class="message-input" placeholder="Mesaj">
                <button id="sendBtn" class="button" disabled>Gönder</button>
            </div>
            
            <div>
                <h3>Mesajlar</h3>
                <div class="messages" id="messages"></div>
            </div>
        </div>
        
        <script>
            let socket = null;
            
            document.getElementById('connectBtn').addEventListener('click', connect);
            document.getElementById('disconnectBtn').addEventListener('click', disconnect);
            document.getElementById('sendBtn').addEventListener('click', sendMessage);
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            function connect() {
                const wsUrl = document.getElementById('wsUrl').value;
                const authToken = document.getElementById('authToken').value;
                
                let url = wsUrl;
                // Eğer token varsa query parameter olarak ekle
                if (authToken) {
                    url += (url.includes('?') ? '&' : '?') + 'auth_key=' + encodeURIComponent(authToken);
                }
                
                try {
                    socket = new WebSocket(url);
                    
                    socket.onopen = function(e) {
                        updateStatus('Bağlantı kuruldu', true);
                        addMessage('Sistem', 'WebSocket bağlantısı açıldı', 'received');
                        document.getElementById('connectBtn').disabled = true;
                        document.getElementById('disconnectBtn').disabled = false;
                        document.getElementById('sendBtn').disabled = false;
                    };
                    
                    socket.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        addMessage('Sunucu', event.data, 'received');
                        
                        // Ping gönderildiyse pong yanıtı ver
                        if (data.type === 'ping') {
                            socket.send(JSON.stringify({
                                type: 'pong',
                                timestamp: new Date().toISOString()
                            }));
                        }
                    };
                    
                    socket.onclose = function(event) {
                        if (event.wasClean) {
                            addMessage('Sistem', `Bağlantı düzgün kapatıldı, kod=${event.code} neden=${event.reason}`, 'received');
                        } else {
                            addMessage('Sistem', 'Bağlantı koptu', 'error');
                        }
                        updateStatus('Bağlantı kesik', false);
                        document.getElementById('connectBtn').disabled = false;
                        document.getElementById('disconnectBtn').disabled = true;
                        document.getElementById('sendBtn').disabled = true;
                    };
                    
                    socket.onerror = function(error) {
                        addMessage('Hata', 'WebSocket hatası: ' + JSON.stringify(error), 'error');
                        updateStatus('Bağlantı hatası', false);
                    };
                    
                } catch (e) {
                    addMessage('Hata', 'Bağlantı hatası: ' + e.message, 'error');
                    updateStatus('Bağlantı hatası', false);
                }
            }
            
            function disconnect() {
                if (socket) {
                    socket.close();
                    socket = null;
                }
            }
            
            function sendMessage() {
                const messageInput = document.getElementById('messageInput');
                const message = messageInput.value;
                
                if (!socket || socket.readyState !== WebSocket.OPEN) {
                    addMessage('Hata', 'Bağlantı açık değil', 'error');
                    return;
                }
                
                if (!message) {
                    return;
                }
                
                try {
                    // JSON olarak göndermeyi dene
                    let jsonMessage;
                    try {
                        jsonMessage = JSON.parse(message);
                        socket.send(message);
                    } catch (e) {
                        // JSON değilse, metin mesajı olarak gönder
                        socket.send(JSON.stringify({
                            type: 'message',
                            content: message,
                            timestamp: new Date().toISOString()
                        }));
                    }
                    
                    addMessage('Siz', message, 'sent');
                    messageInput.value = '';
                } catch (e) {
                    addMessage('Hata', 'Mesaj gönderme hatası: ' + e.message, 'error');
                }
            }
            
            function addMessage(sender, message, type) {
                const messagesDiv = document.getElementById('messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}`;
                messageDiv.innerHTML = `<strong>${sender}:</strong> ${message}`;
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function updateStatus(message, isConnected) {
                const statusDiv = document.getElementById('status');
                statusDiv.textContent = message;
                statusDiv.className = `status ${isConnected ? 'connected' : 'disconnected'}`;
            }
        </script>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

# Geliştirme sunucusunu çalıştır
if __name__ == "__main__":
    try:
        print("MicroBot başlatılıyor... Lütfen bekleyin.")
        print("Uvicorn başlatma...")
        import uvicorn
        uvicorn.run(
            "app.main:app", 
            host="0.0.0.0", 
            port=8000,  # Sunucu 8000 portundan çalışıyor
            log_level="info",
            log_config=None,  # Varsayılan ayarları kullan
            access_log=True
        )
    except Exception as e:
        print(f"Başlatma hatası: {str(e)}")
