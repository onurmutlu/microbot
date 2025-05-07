"""
Veritabanı bağlantı işlemleri için yardımcı fonksiyonlar.

Bu modül, veritabanı bağlantısı ve oturum yönetimi için gereken
işlevleri içerir.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.config import settings

# SQLAlchemy veritabanı URL'sini ayarla
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Veritabanı motorunu oluştur
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    poolclass=QueuePool,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
)

# Oturum fabrikasını oluştur
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base sınıfını oluştur
Base = declarative_base()

def get_db() -> Session:
    """
    Veritabanı oturumu alma fonksiyonu.
    FastAPI Depends ile kullanılır.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Veritabanını başlatır."""
    # İhtiyaç olursa veritabanı tablolarını oluştur
    # Base.metadata.create_all(bind=engine)
    pass 