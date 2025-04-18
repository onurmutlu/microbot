import os
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uvicorn

from app.database import SessionLocal, engine, Base
from app.routers import auth, groups, messages, logs, auto_reply, message_template

# Veritabanı tablolarını oluştur
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Telegram MicroBot API",
    description="Telegram grup mesajlarını otomatik yöneten, çoklu kullanıcı destekli MicroBot API.",
    version="1.0.0"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")  # token yolu doğru olmalı

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
    allow_origins=["*"],  # Güvenlik için production ortamında özelleştirin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(auto_reply.router, tags=["auto-reply"])
app.include_router(message_template.router, prefix="/api/message-templates", tags=["message-templates"])

# Veritabanı bağımlılığı (opsiyonel olarak burada tanımlanabilir)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Root endpoint
@app.get("/")
async def root():
    return {"message": "📡 Telegram MicroBot API'ye Hoş Geldiniz."}

# Geliştirme sunucusunu çalıştır
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
