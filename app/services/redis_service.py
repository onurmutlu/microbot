import aioredis
from typing import Optional, Dict, List
import json
from datetime import datetime, timedelta

class RedisService:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self.online_users: Dict[str, datetime] = {}

    async def init_redis(self, redis_url: str):
        self.redis = await aioredis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()

    async def publish(self, channel: str, message: dict):
        if self.redis:
            await self.redis.publish(channel, json.dumps(message))
            
            receiver_id = message.get('receiver_id')
            if receiver_id and not await self.is_user_online(receiver_id):
                await self.add_to_queue(receiver_id, message)

    async def subscribe(self, channel: str):
        if self.pubsub:
            await self.pubsub.subscribe(channel)

    async def get_message(self):
        if self.pubsub:
            message = await self.pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                return json.loads(message['data'])
        return None

    async def set_user_online(self, user_id: str):
        if self.redis:
            self.online_users[user_id] = datetime.now()
            await self.redis.set(f"user:{user_id}:status", "online", ex=300)
            await self.check_queued_messages(user_id)

    async def set_user_offline(self, user_id: str):
        if self.redis:
            self.online_users.pop(user_id, None)
            await self.redis.delete(f"user:{user_id}:status")

    async def is_user_online(self, user_id: str) -> bool:
        if self.redis:
            status = await self.redis.get(f"user:{user_id}:status")
            return status == b"online"
        return False

    async def add_to_queue(self, user_id: str, message: dict):
        if self.redis:
            queue_key = f"user:{user_id}:queue"
            await self.redis.rpush(queue_key, json.dumps(message))
            await self.redis.expire(queue_key, 604800)

    async def check_queued_messages(self, user_id: str):
        if self.redis:
            queue_key = f"user:{user_id}:queue"
            while True:
                message = await self.redis.lpop(queue_key)
                if not message:
                    break
                message_data = json.loads(message)
                await self.publish(f"user:{user_id}", message_data)

    async def cleanup_old_connections(self):
        current_time = datetime.now()
        offline_users = []
        for user_id, last_seen in self.online_users.items():
            if current_time - last_seen > timedelta(minutes=5):
                offline_users.append(user_id)
        
        for user_id in offline_users:
            await self.set_user_offline(user_id)

redis_service = RedisService() 