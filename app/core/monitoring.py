from typing import Dict, Any, List
from datetime import datetime
from app.core.logging import logger
from prometheus_client import Counter, Gauge, Histogram
import time

class WebSocketMonitor:
    def __init__(self) -> None:
        # Prometheus metrikleri
        self.connections_total = Counter(
            'websocket_connections_total',
            'Total number of WebSocket connections'
        )
        self.active_connections = Gauge(
            'websocket_active_connections',
            'Number of active WebSocket connections'
        )
        self.messages_sent = Counter(
            'websocket_messages_sent_total',
            'Total number of messages sent',
            ['type']
        )
        self.messages_received = Counter(
            'websocket_messages_received_total',
            'Total number of messages received',
            ['type']
        )
        self.message_latency = Histogram(
            'websocket_message_latency_seconds',
            'Message processing latency in seconds',
            ['type']
        )
        
        # İzleme verileri
        self.connection_stats: Dict[str, Dict[str, Any]] = {}
        self.message_stats: Dict[str, Dict[str, int]] = {}
        self.error_stats: Dict[str, int] = {}

    def connection_established(self, user_id: str) -> None:
        self.connections_total.inc()
        self.active_connections.inc()
        
        self.connection_stats[user_id] = {
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0,
            'error_count': 0
        }
        
        logger.info(f"Connection established for user {user_id}")

    def connection_closed(self, user_id: str) -> None:
        self.active_connections.dec()
        
        if user_id in self.connection_stats:
            del self.connection_stats[user_id]
        
        logger.info(f"Connection closed for user {user_id}")

    def message_sent(self, user_id: str, message_type: str, latency: float = 0.0) -> None:
        self.messages_sent.labels(type=message_type).inc()
        self.message_latency.labels(type=message_type).observe(latency)
        
        if user_id in self.connection_stats:
            self.connection_stats[user_id]['message_count'] += 1
            self.connection_stats[user_id]['last_activity'] = datetime.now()
        
        if message_type not in self.message_stats:
            self.message_stats[message_type] = {'sent': 0, 'received': 0}
        self.message_stats[message_type]['sent'] += 1
        
        logger.debug(f"Message sent to user {user_id}: {message_type}")

    def message_received(self, user_id: str, message_type: str) -> None:
        self.messages_received.labels(type=message_type).inc()
        
        if user_id in self.connection_stats:
            self.connection_stats[user_id]['last_activity'] = datetime.now()
        
        if message_type not in self.message_stats:
            self.message_stats[message_type] = {'sent': 0, 'received': 0}
        self.message_stats[message_type]['received'] += 1
        
        logger.debug(f"Message received from user {user_id}: {message_type}")

    def message_processed(self, user_id: str, message_type: str) -> None:
        if user_id in self.connection_stats:
            self.connection_stats[user_id]['last_activity'] = datetime.now()
        
        logger.debug(f"Message processed for user {user_id}: {message_type}")

    def error_occurred(self, user_id: str, error_type: str) -> None:
        if user_id in self.connection_stats:
            self.connection_stats[user_id]['error_count'] += 1
        
        if error_type not in self.error_stats:
            self.error_stats[error_type] = 0
        self.error_stats[error_type] += 1
        
        logger.error(f"Error occurred for user {user_id}: {error_type}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            'connections': {
                'total': self.connections_total._value.get(),
                'active': self.active_connections._value.get(),
                'per_user': self.connection_stats
            },
            'messages': self.message_stats,
            'errors': self.error_stats
        }

    def get_connection_health(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self.connection_stats:
            return {'status': 'disconnected'}
        
        stats = self.connection_stats[user_id]
        last_activity = (datetime.now() - stats['last_activity']).total_seconds()
        
        return {
            'status': 'connected',
            'connected_at': stats['connected_at'].isoformat(),
            'last_activity': stats['last_activity'].isoformat(),
            'inactive_seconds': last_activity,
            'message_count': stats['message_count'],
            'error_count': stats['error_count']
        }

websocket_monitor = WebSocketMonitor() 