from typing import Dict, List, Any, Union
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.group import Group
from app.models.user import User
from app.models.message_log import MessageLog
import asyncio
import json

class GroupAnalyzer:
    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self.db: Session = SessionLocal()

    async def analyze_user_groups(self, user_id: int) -> List[Dict[str, Any]]:
        """Kullanıcının dahil olduğu grupları analiz eder"""
        # Kullanıcının olduğu tüm dialog'ları çek
        try:
            dialogs = await self.client.get_dialogs()
            group_results = []
            
            # Sadece grup ve kanalları filtrele
            groups = [dialog.entity for dialog in dialogs if isinstance(dialog.entity, (Channel, Chat))]
            
            for group in groups:
                # Grup analizi yap
                group_info = await self._analyze_group(group)
                group_results.append(group_info)
            
            # Sonuçları cache'le veya DB'ye kaydet
            self._save_group_analysis(user_id, group_results)
            
            return group_results
            
        except Exception as e:
            logger.error(f"Grup analizi sırasında hata: {str(e)}")
            return []

    async def _analyze_group(self, group: Union[Channel, Chat]) -> Dict[str, Any]:
        """Bir grubu analiz eder ve istatistikleri döndürür"""
        group_info = {
            'id': group.id,
            'title': group.title,
            'type': 'channel' if isinstance(group, Channel) else 'group',
            'member_count': getattr(group, 'participants_count', 0),
            'analyzed_at': datetime.now().isoformat()
        }
        
        try:
            # Son mesajları çek
            messages = await self.client.get_messages(group, limit=100)
            
            # Mesaj istatistikleri
            message_count = len(messages)
            message_authors = {}
            topics = {}
            
            for msg in messages:
                if msg.sender_id:
                    if msg.sender_id not in message_authors:
                        message_authors[msg.sender_id] = 0
                    message_authors[msg.sender_id] += 1
                
                # Mesaj konuları analizi (basit)
                if msg.text:
                    words = msg.text.lower().split()
                    for word in words:
                        if len(word) > 4:  # kısa kelimeleri atla
                            if word not in topics:
                                topics[word] = 0
                            topics[word] += 1
            
            # En aktif kullanıcılar
            top_authors = sorted(message_authors.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # En yaygın konular
            top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # İstatistikleri ekle
            group_info.update({
                'message_count': message_count,
                'active_users': len(message_authors),
                'top_authors': [{'id': a[0], 'message_count': a[1]} for a in top_authors],
                'top_topics': [{'word': t[0], 'count': t[1]} for t in top_topics],
            })
        
        except Exception as e:
            logger.error(f"Grup analizi ayrıntı hatası ({group.id}): {str(e)}")
        
        return group_info
        
    def _save_group_analysis(self, user_id: int, group_results: List[Dict[str, Any]]) -> None:
        """Grup analiz sonuçlarını veritabanına kaydeder"""
        try:
            for group_data in group_results:
                # Grup varsa güncelle, yoksa oluştur
                group = self.db.query(Group).filter(Group.telegram_id == group_data['id']).first()
                
                if not group:
                    group = Group(
                        telegram_id=group_data['id'],
                        title=group_data['title'],
                        type=group_data['type'],
                        member_count=group_data['member_count'],
                        last_analyzed=datetime.now()
                    )
                    self.db.add(group)
                else:
                    # Mevcut grubu güncelle
                    group.title = group_data['title']
                    group.member_count = group_data['member_count']
                    group.last_analyzed = datetime.now()
                
                # İşlemi veritabanında kaydet
                self.db.commit()
                
                # JSON formatında istatistik verilerini kaydet
                message_log = MessageLog(
                    group_id=group.id,
                    user_id=user_id,
                    log_date=datetime.now(),
                    message_count=group_data.get('message_count', 0),
                    active_users=group_data.get('active_users', 0),
                    statistics=json.dumps({
                        'top_authors': group_data.get('top_authors', []),
                        'top_topics': group_data.get('top_topics', [])
                    })
                )
                self.db.add(message_log)
                self.db.commit()
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Grup analiz sonuçları kaydedilirken hata: {str(e)}")
    
    def close(self) -> None:
        """Kaynakları temizle"""
        if self.db:
            self.db.close()

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
            
            # Group metadata'ya aktivite bilgilerini ekle
            group_metadata = group.group_metadata or {}
            group_metadata.update({
                "activity_hours": group_info["activity_hours"],
                "top_active_hours": group_info["top_active_hours"],
                "recent_messages": group_info["recent_messages"],
                "last_activity_check": datetime.now().isoformat()
            })
            group.group_metadata = group_metadata
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
                "activity_data": group.group_metadata,
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
                    "category": g.category,
                    "metadata": g.group_metadata
                } for g in groups]
            }
            
        except Exception as e:
            logger.error(f"Error getting user group stats: {str(e)}")
            raise
            
    def get_optimal_interval(self, group_id: int) -> int:
        """
        Belirli bir grup için optimal mesaj gönderme aralığını hesaplar
        Son 24 saatteki aktiviteye, grup boyutuna, kategorisine göre belirlenir
        
        Args:
            group_id: Grubun ID'si
            
        Returns:
            Dakika cinsinden optimal mesaj gönderme aralığı
        """
        try:
            group = self.db.query(Group).filter_by(telegram_id=group_id).first()
            if not group:
                return 60  # Varsayılan 60 dakika
                
            # Grup metadatasını kontrol et
            metadata = group.group_metadata or {}
            
            # Son 24 saatteki mesaj sayısını al
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            messages_count = self.db.query(MessageLog).filter(
                MessageLog.telegram_id == group_id,
                MessageLog.sent_at >= one_day_ago
            ).count()
            
            # Grup aktivitesi (recent_messages) değerini kontrol et
            recent_messages = metadata.get("recent_messages", 0)
            
            # Temel interval değeri
            base_interval = 60  # Varsayılan 60 dakika
            
            # Yüksek aktivite grupları için daha sık mesaj (3 dakikaya kadar)
            if recent_messages > 500 or messages_count > 50:
                base_interval = 3  # Çok aktif grup
            elif recent_messages > 200 or messages_count > 20:
                base_interval = 5  # Aktif grup
            elif recent_messages > 100 or messages_count > 10:
                base_interval = 10  # Orta aktif grup
            elif recent_messages > 50 or messages_count > 5:
                base_interval = 20  # Az aktif grup
            else:
                base_interval = 30  # Çok az aktif grup
                
            # Grup kategorisine göre ayarla
            if group.category == "news":
                # Haber grupları için biraz daha sık
                base_interval = max(base_interval - 5, 3)
            elif group.category == "advertisement":
                # Reklam grupları için daha az sık
                base_interval = min(base_interval + 10, 60)
                
            # Grup boyutuna göre ayarla (büyük gruplarda daha sık)
            if group.participants_count > 1000:
                base_interval = max(base_interval - 3, 3)
            elif group.participants_count < 100:
                base_interval = min(base_interval + 5, 60)
                
            # Sonucu logla
            logger.info(f"Grup {group_id} ({group.title}) için optimal mesaj aralığı: {base_interval} dakika")
            
            return base_interval
            
        except Exception as e:
            logger.error(f"Optimal interval hesaplama hatası: {str(e)}")
            return 60  # Hata durumunda 60 dakika
            
    def get_optimal_intervals_for_user(self, user_id: int) -> Dict[int, int]:
        """
        Kullanıcının tüm grupları için optimal mesaj gönderme aralıklarını hesaplar
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            {group_id: interval_minutes} formatında sözlük
        """
        try:
            groups = self.db.query(Group).filter_by(user_id=user_id, is_active=True).all()
            
            intervals = {}
            for group in groups:
                intervals[group.telegram_id] = self.get_optimal_interval(group.telegram_id)
                
            return intervals
                
        except Exception as e:
            logger.error(f"Kullanıcı grupları için interval hesaplama hatası: {str(e)}")
            return {} 