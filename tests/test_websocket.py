import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.websocket import websocket_manager

client = TestClient(app)

@pytest.mark.asyncio
async def test_websocket_connection():
    with client.websocket_connect("/ws/test_client") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "connection_established"

@pytest.mark.asyncio
async def test_websocket_broadcast():
    with client.websocket_connect("/ws/test_client1") as websocket1:
        with client.websocket_connect("/ws/test_client2") as websocket2:
            message = {"type": "test", "content": "test message"}
            await websocket_manager.broadcast("test_client1", message)
            data = websocket1.receive_json()
            assert data == message
            data = websocket2.receive_json()
            assert data == message 