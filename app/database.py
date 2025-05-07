import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings

# Logger ayarı
logger = logging.getLogger(__name__)

# Veritabanı bağlantı parametreleri
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Veritabanı bağlantısı ve oturum oluşturma
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=False
)

# Oturum oluşturucu
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Veritabanı modelleri için temel sınıf
Base = declarative_base()

# Bağımlılık enjeksiyonu için yardımcı fonksiyon
def get_db():
    """Veritabanı oturumu elde etmek için bağımlılık enjeksiyonu fonksiyonu."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Veritabanı hatası: {str(e)}")
        raise
    finally:
        db.close()
