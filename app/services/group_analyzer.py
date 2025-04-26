from typing import Dict, List, Any
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.group import Group
from app.models.user import User
import asyncio

class GroupAnalyzer:
    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self.db: Session = SessionLocal()

    async def analyze_user_groups(self, user_id: int) -> List[Dict[str, Any]]:
        """Kullanıcının üye olduğu grupları analiz et"""
        try:
            # Kullanıcının gruplarını çek
            dialogs = await self.client.get_dialogs()
            groups = []
            
            for dialog in dialogs:
                if isinstance(dialog.entity, (Channel, Chat)):
                    # Grup bilgilerini topla
                    group_info = await self._analyze_group(dialog.entity)
                    groups.append(group_info)
                    
                    # Veritabanında güncelle
                    await self._update_group_db(user_id, group_info)
            
            return groups
            
        except Exception as e:
            logger.error(f"Error analyzing user groups: {str(e)}")
            raise

    async def _analyze_group(self, group: Channel | Chat) -> Dict[str, Any]:
        """Grup detaylarını analiz et"""
        try:
            # Grup istatistiklerini topla
            participants = await self.client.get_participants(group)
            messages = await self.client.get_messages(group, limit=100)
            
            # Aktivite analizi
            active_users = len([p for p in participants if p.status is not None])
            recent_messages = len(messages)
            
            # Grup kategorisini belirle
            category = await self._determine_group_category(group, messages)
            
            return {
                "id": group.id,
                "title": group.title,
                "username": getattr(group, "username", None),
                "participants_count": len(participants),
                "active_users": active_users,
                "recent_messages": recent_messages,
                "category": category,
                "last_analyzed": datetime.now(),
                "rules": await self._get_group_rules(group)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing group {group.id}: {str(e)}")
            raise

    async def _determine_group_category(self, group: Channel | Chat, messages: List[Any]) -> str:
        """Grup kategorisini belirle"""
        # Mesaj içeriklerini analiz et
        content_types = {}
        for msg in messages:
            if msg.text:
                content = msg.text.lower()
                if "reklam" in content or "duyuru" in content:
                    content_types["advertisement"] = content_types.get("advertisement", 0) + 1
                elif "soru" in content or "yardım" in content:
                    content_types["support"] = content_types.get("support", 0) + 1
                elif "haber" in content or "güncel" in content:
                    content_types["news"] = content_types.get("news", 0) + 1
        
        # En yaygın içerik tipine göre kategori belirle
        if content_types:
            return max(content_types.items(), key=lambda x: x[1])[0]
        return "general"

    async def _get_group_rules(self, group: Channel | Chat) -> Dict[str, Any]:
        """Grup kurallarını çek"""
        try:
            # Grup açıklamasından kuralları çıkar
            description = getattr(group, "about", "")
            rules = {
                "no_spam": "spam" in description.lower(),
                "no_ads": "reklam" in description.lower(),
                "no_links": "link" in description.lower(),
                "no_media": "medya" in description.lower()
            }
            return rules
        except Exception as e:
            logger.error(f"Error getting group rules: {str(e)}")
            return {}

    async def _update_group_db(self, user_id: int, group_info: Dict[str, Any]) -> None:
        """Grup bilgilerini veritabanında güncelle"""
        try:
            group = self.db.query(Group).filter_by(telegram_id=group_info["id"]).first()
            if not group:
                group = Group(
                    telegram_id=group_info["id"],
                    title=group_info["title"],
                    username=group_info["username"],
                    user_id=user_id
                )
                self.db.add(group)
            
            # Grup bilgilerini güncelle
            group.participants_count = group_info["participants_count"]
            group.active_users = group_info["active_users"]
            group.category = group_info["category"]
            group.last_analyzed = group_info["last_analyzed"]
            group.rules = group_info["rules"]
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating group in database: {str(e)}")
            self.db.rollback()
            raise

    async def get_group_stats(self, group_id: int) -> Dict[str, Any]:
        """Grup istatistiklerini getir"""
        try:
            group = self.db.query(Group).filter_by(telegram_id=group_id).first()
            if not group:
                raise ValueError(f"Group {group_id} not found")
            
            return {
                "id": group.telegram_id,
                "title": group.title,
                "participants_count": group.participants_count,
                "active_users": group.active_users,
                "category": group.category,
                "last_analyzed": group.last_analyzed,
                "rules": group.rules
            }
            
        except Exception as e:
            logger.error(f"Error getting group stats: {str(e)}")
            raise

    async def get_user_group_stats(self, user_id: int) -> Dict[str, Any]:
        """Kullanıcının grup istatistiklerini getir"""
        try:
            groups = self.db.query(Group).filter_by(user_id=user_id).all()
            
            total_groups = len(groups)
            total_participants = sum(g.participants_count for g in groups)
            total_active = sum(g.active_users for g in groups)
            
            categories = {}
            for group in groups:
                categories[group.category] = categories.get(group.category, 0) + 1
            
            return {
                "total_groups": total_groups,
                "total_participants": total_participants,
                "total_active_users": total_active,
                "categories": categories,
                "groups": [{
                    "id": g.telegram_id,
                    "title": g.title,
                    "participants": g.participants_count,
                    "active": g.active_users,
                    "category": g.category
                } for g in groups]
            }
            
        except Exception as e:
            logger.error(f"Error getting user group stats: {str(e)}")
            raise 