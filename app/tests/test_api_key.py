import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import secrets
import hashlib
from datetime import datetime, timedelta
import os

from app.database import Base, get_db
from app.models import User, ApiKey, UserRole
from app.main import app
from app.schemas import ApiKeyCreate
from app.dependencies import get_current_admin_user

# Test için PostgreSQL test veritabanı
TEST_POSTGRES_URL = os.environ.get(
    "TEST_DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/microbot_test"
)

engine = create_engine(
    TEST_POSTGRES_URL,
    pool_size=5,
    max_overflow=5,
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Test veritabanı oluşturma
Base.metadata.create_all(bind=engine)

# Test istemcisi oluşturma
client = TestClient(app)

# Bağımlılıkları değiştir
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Admin kullanıcısı oluştur
def create_test_admin():
    db = TestingSessionLocal()
    admin = User(
        username="testadmin",
        password_hash="hashed_password",
        api_id="123456",
        api_hash="abcdef",
        phone="+901234567890",
        is_active=True,
        role=UserRole.ADMIN
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()
    return admin

# Test verilerini hazırla
@pytest.fixture
def test_db():
    # Tablo yapısını sil ve yeniden oluştur
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Bağımlılıkları değiştir
    app.dependency_overrides[get_db] = override_get_db
    
    # Test admin kullanıcısı
    admin = create_test_admin()
    
    # Test JWT token (gerçek uygulamada auth_service üzerinden oluşturulur)
    token = "test-admin-token"
    
    # Admin kullanıcısını dönüş yap
    app.dependency_overrides[get_current_admin_user] = lambda: admin
    
    yield TestingSessionLocal()
    
    # Temizlik
    app.dependency_overrides = {}

# API Anahtarı oluşturma testi
def test_create_api_key(test_db):
    api_key_data = {
        "name": "Test API Key",
        "expires_days": 30
    }
    
    response = client.post(
        "/admin/api-keys",
        json=api_key_data,
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == api_key_data["name"]
    assert "key" in data
    assert data["user_id"] == 1

# API Anahtarlarını listeleme testi
def test_list_api_keys(test_db):
    # Önce bir anahtar oluştur
    api_key = ApiKey(
        user_id=1,
        name="Test API Key",
        hashed_key=hashlib.sha256("test-key".encode()).hexdigest(),
        is_active=True
    )
    test_db.add(api_key)
    test_db.commit()
    
    response = client.get(
        "/admin/api-keys",
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Test API Key"

# API Anahtarı silme testi
def test_delete_api_key(test_db):
    # Önce bir anahtar oluştur
    api_key = ApiKey(
        user_id=1,
        name="Test API Key",
        hashed_key=hashlib.sha256("test-key".encode()).hexdigest(),
        is_active=True
    )
    test_db.add(api_key)
    test_db.commit()
    test_db.refresh(api_key)
    
    key_id = api_key.id
    
    response = client.delete(
        f"/admin/api-keys/{key_id}",
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 204
    
    # Anahtarın silindiğini doğrula
    db_key = test_db.query(ApiKey).filter(ApiKey.id == key_id).first()
    assert db_key is None 