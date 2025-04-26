from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.group import Group
import pytest

client = TestClient(app)

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_create_user(db):
    response = client.post(
        "/api/v1/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"

def test_create_group(db):
    response = client.post(
        "/api/v1/groups/",
        json={
            "title": "Test Group",
            "description": "Test Description",
            "type": "public"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Group"
    assert data["description"] == "Test Description"

def test_get_groups(db):
    response = client.get("/api/v1/groups/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_get_users(db):
    response = client.get("/api/v1/users/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) 