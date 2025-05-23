from app.routers.auth import router as auth
from app.routers.groups import router as groups
from app.routers.messages import router as messages
from app.routers.logs import router as logs
from app.routers.auto_reply import router as auto_reply
from app.routers.message_template import router as message_template
from app.routers.scheduler import router as scheduler
from app.routers.dashboard import router as dashboard
from app.routers.websocket import router as websocket

# Farklı modüllerden tüm router'ları buraya ekle
__all__ = [
    "auth",
    "groups",
    "messages",
    "logs",
    "auto_reply",
    "message_template",
    "scheduler",
    "dashboard",
    "websocket"
] 