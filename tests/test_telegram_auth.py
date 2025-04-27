import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.main import app
from app.database import get_db
from app.models import User

client = TestClient(app)

@pytest.fixture
def mock_telegram_service():
    """TelegramService sınıfını mock'lamak için fixture"""
    with patch("app.routers.telegram_auth.TelegramService") as mock:
        instance = mock.return_value
        
        # create_session metodu mock
        async def mock_create_session(api_id=None, api_hash=None, phone=None):
            return {"message": "Doğrulama kodu telefonunuza gönderildi"}
        instance.create_session = mock_create_session
        
        # verify_session metodu mock - başarılı kod
        async def mock_verify_session(code=None, password=None):
            if code == "12345":
                return {"success": True, "session": "test_session_string"}
            elif code == "99999":
                return {"two_factor_required": True, "message": "İki faktörlü doğrulama şifresi gerekli"}
            elif password == "correct_password":
                return {"success": True, "session": "test_session_string"}
            else:
                return {"success": False, "message": "Geçersiz kod veya şifre"}
        instance.verify_session = mock_verify_session
        
        yield instance

def test_start_login(mock_telegram_service):
    """start-login endpoint testi"""
    response = client.post(
        "/api/telegram/start-login",
        json={
            "api_id": "12345",
            "api_hash": "abcdefghijklmn",
            "phone": "+905551234567"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert "Doğrulama kodu telefonunuza gönderildi" in data["message"]

def test_confirm_code_success(mock_telegram_service):
    """confirm-code endpoint testi - başarılı durum"""
    # Önce login başlat
    client.post(
        "/api/telegram/start-login",
        json={
            "api_id": "12345",
            "api_hash": "abcdefghijklmn",
            "phone": "+905551234567"
        }
    )
    
    # Doğrulama kodunu gönder
    response = client.post(
        "/api/telegram/confirm-code",
        json={
            "phone": "+905551234567",
            "code": "12345"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["session_saved"] == True

def test_confirm_code_2fa_required(mock_telegram_service):
    """confirm-code endpoint testi - 2FA gerekli durumu"""
    # Önce login başlat
    client.post(
        "/api/telegram/start-login",
        json={
            "api_id": "12345",
            "api_hash": "abcdefghijklmn",
            "phone": "+905551234568"
        }
    )
    
    # Doğrulama kodunu gönder
    response = client.post(
        "/api/telegram/confirm-code",
        json={
            "phone": "+905551234568",
            "code": "99999"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["requires_2fa"] == True

def test_confirm_2fa_password(mock_telegram_service):
    """confirm-2fa-password endpoint testi"""
    # Önce login başlat
    client.post(
        "/api/telegram/start-login",
        json={
            "api_id": "12345",
            "api_hash": "abcdefghijklmn",
            "phone": "+905551234569"
        }
    )
    
    # 2FA şifresini gönder
    response = client.post(
        "/api/telegram/confirm-2fa-password",
        json={
            "phone": "+905551234569",
            "password": "correct_password"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["session_saved"] == True

def test_confirm_code_invalid(mock_telegram_service):
    """confirm-code endpoint testi - geçersiz kod"""
    # Önce login başlat
    client.post(
        "/api/telegram/start-login",
        json={
            "api_id": "12345",
            "api_hash": "abcdefghijklmn",
            "phone": "+905551234570"
        }
    )
    
    # Geçersiz doğrulama kodunu gönder
    response = client.post(
        "/api/telegram/confirm-code",
        json={
            "phone": "+905551234570",
            "code": "wrong_code"
        }
    )
    assert response.status_code == 400
    data = response.json()
    assert "Geçersiz kod" in data["detail"] 