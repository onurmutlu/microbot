import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Logger ayarı
logger = logging.getLogger(__name__)

# SQLite veritabanı bağlantısı ve oturum oluşturma
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite için gerekli
    echo=False  # SQL komutlarını loglamayı kapatma
)

# Oturum oluşturucu
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Veritabanı modelleri için temel sınıf
Base = declarative_base()

# Bağımlılık enjeksiyonu için yardımcı fonksiyon
def get_db():
    """Veritabanı oturumu elde etmek için bağımlılık enjeksiyonu fonksiyonu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
