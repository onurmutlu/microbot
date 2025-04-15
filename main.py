import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uvicorn

from app.database import SessionLocal, engine, Base
from app.routers import auth, groups, messages, logs
from app.config import settings

# Veritabanı tablolarını oluştur
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Telegram Bot API",
    description="Telegram grup mesajlarını otomatik gönderen API",
    version="1.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Güvenlik için production'da güncelleyin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(messages.router)
app.include_router(logs.router)

@app.get("/")
async def root():
    return {"message": "Telegram Bot API'ye Hoş Geldiniz"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
