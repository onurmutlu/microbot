#!/usr/bin/env python3
with open('app/main.py', 'r') as f:
    content = f.read()

# WebSocket bölümünü daha basit versiyonla değiştir
import re
pattern = r'@app\.websocket\("/api/ws"\).*?# SSE'
replacement = '''@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket bağlantısını yönetir"""
    client_id = str(uuid.uuid4())
    
    # WebSocketManager.handle_websocket metodunu kullan
    await websocket_manager.handle_websocket(websocket, client_id)

# SSE'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('app/main.py', 'w') as f:
    f.write(new_content)

print("WebSocket endpoint güncellendi") 