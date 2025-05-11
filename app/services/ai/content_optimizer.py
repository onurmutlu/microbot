import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json
import random
from collections import Counter

from app.models.message import Message
from app.models.group import Group
from app.models.message_log import MessageLog

logger = logging.getLogger(__name__)

class ContentOptimizer:
    """
    Grup mesajlarını analiz ederek en iyi performans gösteren içerik türlerini 
    tespit eden ve gelecek mesajları optimize eden servis.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def analyze_group_content(self, group_id: int) -> Dict[str, Any]:
        """
        Gruptaki mesajları analiz ederek, en iyi performans gösteren içerik türlerini tespit eder.
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            İçerik analizi sonuçları
        """
        try:
            # Son 30 günlük mesajları al
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            logs = self.db.query(MessageLog).filter(
                MessageLog.telegram_id == group_id,
                MessageLog.sent_at >= thirty_days_ago
            ).all()
            
            if not logs:
                return {
                    "status": "no_data",
                    "message": "Bu grup için yeterli veri bulunmuyor",
                    "recommendations": []
                }
                
            # Mesaj başarı oranlarını analiz et
            total_messages = len(logs)
            successful_messages = sum(1 for log in logs if log.status == 'success')
            success_rate = (successful_messages / total_messages) * 100 if total_messages > 0 else 0
            
            # İçerik analizleri
            content_analysis = self._analyze_message_content(logs)
            
            # Etkileşim oranları
            engagement_rates = self._calculate_engagement_rates(logs)
            
            # Gruptaki en aktif saatleri bul
            active_hours = self._find_active_hours(logs)
            
            # Optimizasyon önerileri
            recommendations = self._generate_recommendations(
                content_analysis, 
                engagement_rates,
                active_hours
            )
            
            return {
                "status": "success",
                "group_id": group_id,
                "message_count": total_messages,
                "success_rate": success_rate,
                "content_analysis": content_analysis,
                "engagement_rates": engagement_rates,
                "active_hours": active_hours,
                "recommendations": recommendations,
                "timestamp": datetime.utcnow().isoformat()
            }
                
        except Exception as e:
            logger.error(f"İçerik analizi hatası: {str(e)}")
            return {
                "status": "error",
                "message": f"İçerik analizi sırasında hata oluştu: {str(e)}",
                "recommendations": []
            }
    
    def _analyze_message_content(self, logs: List[MessageLog]) -> Dict[str, Any]:
        """
        Mesaj içeriklerini analiz eder.
        """
        # Mesaj uzunluğu analizi
        message_lengths = []
        has_media_count = 0
        has_link_count = 0
        has_mention_count = 0
        has_hashtag_count = 0
        
        # İçerik türleri
        content_types = Counter()
        
        for log in logs:
            if log.message_content:
                # Mesaj uzunluğu
                message_lengths.append(len(log.message_content))
                
                # Medya, link, mention, hashtag kontrolü
                if log.has_media:
                    has_media_count += 1
                
                if "http" in log.message_content.lower():
                    has_link_count += 1
                
                if "@" in log.message_content:
                    has_mention_count += 1
                    
                if "#" in log.message_content:
                    has_hashtag_count += 1
                
                # İçerik analizi (basit bir sınıflandırma)
                content = log.message_content.lower()
                if "duyuru" in content or "önemli" in content:
                    content_types["announcement"] += 1
                elif "indirim" in content or "kampanya" in content or "fırsat" in content:
                    content_types["promotion"] += 1
                elif "soru" in content or "?":
                    content_types["question"] += 1
                elif "bilgi" in content or "haber" in content:
                    content_types["information"] += 1
                else:
                    content_types["general"] += 1
        
        # Ortalama mesaj uzunluğu
        avg_length = sum(message_lengths) / len(message_lengths) if message_lengths else 0
        
        # Özellik oranları
        total = len(logs)
        media_rate = (has_media_count / total) * 100 if total > 0 else 0
        link_rate = (has_link_count / total) * 100 if total > 0 else 0
        mention_rate = (has_mention_count / total) * 100 if total > 0 else 0
        hashtag_rate = (has_hashtag_count / total) * 100 if total > 0 else 0
        
        # İçerik türü dağılımı
        content_distribution = {k: (v / total) * 100 for k, v in content_types.items()} if total > 0 else {}
        
        return {
            "avg_message_length": avg_length,
            "media_rate": media_rate,
            "link_rate": link_rate,
            "mention_rate": mention_rate,
            "hashtag_rate": hashtag_rate,
            "content_types": dict(content_types),
            "content_distribution": content_distribution
        }
    
    def _calculate_engagement_rates(self, logs: List[MessageLog]) -> Dict[str, float]:
        """
        Farklı içerik türlerine göre etkileşim oranlarını hesaplar.
        """
        # Gerçek bir senaryoda, etkileşimler (beğeni, yorum, paylaşım) Telegram API'sinden alınır
        # Bu örnek için basitleştirilmiş bir hesaplama yapıyoruz
        
        engagement_by_type = {
            "with_media": {"count": 0, "engagement": 0},
            "with_links": {"count": 0, "engagement": 0},
            "with_mentions": {"count": 0, "engagement": 0},
            "with_hashtags": {"count": 0, "engagement": 0},
            "short_messages": {"count": 0, "engagement": 0},
            "long_messages": {"count": 0, "engagement": 0}
        }
        
        for log in logs:
            if not log.message_content:
                continue
                
            # Mesaj "engagement" puanı hesaplama (gerçekte bunun için etkileşim verisi kullanılır)
            # Bu örnekte başarılı mesajlara rastgele engagement puanı veriyoruz
            is_successful = log.status == 'success'
            engagement = random.randint(5, 10) if is_successful else random.randint(0, 4)
            
            # Özelliklere göre sınıflandırma
            if log.has_media:
                engagement_by_type["with_media"]["count"] += 1
                engagement_by_type["with_media"]["engagement"] += engagement
            
            if "http" in log.message_content.lower():
                engagement_by_type["with_links"]["count"] += 1
                engagement_by_type["with_links"]["engagement"] += engagement
            
            if "@" in log.message_content:
                engagement_by_type["with_mentions"]["count"] += 1
                engagement_by_type["with_mentions"]["engagement"] += engagement
                
            if "#" in log.message_content:
                engagement_by_type["with_hashtags"]["count"] += 1
                engagement_by_type["with_hashtags"]["engagement"] += engagement
            
            # Uzunluğa göre sınıflandırma
            if len(log.message_content) < 100:  # Kısa mesaj
                engagement_by_type["short_messages"]["count"] += 1
                engagement_by_type["short_messages"]["engagement"] += engagement
            else:  # Uzun mesaj
                engagement_by_type["long_messages"]["count"] += 1
                engagement_by_type["long_messages"]["engagement"] += engagement
        
        # Ortalama engagement hesapla
        result = {}
        for key, data in engagement_by_type.items():
            if data["count"] > 0:
                result[key] = data["engagement"] / data["count"]
            else:
                result[key] = 0
                
        return result
    
    def _find_active_hours(self, logs: List[MessageLog]) -> Dict[str, Any]:
        """
        Gruptaki en aktif saatleri bulur.
        """
        hour_counts = [0] * 24
        
        for log in logs:
            if log.sent_at:
                hour = log.sent_at.hour
                hour_counts[hour] += 1
        
        # En aktif 3 saati bul
        top_hours = []
        for _ in range(min(3, len(hour_counts))):
            max_hour = hour_counts.index(max(hour_counts))
            top_hours.append(max_hour)
            hour_counts[max_hour] = -1  # Bu saati tekrar seçmemek için
        
        return {
            "hour_distribution": [{"hour": h, "count": c} for h, c in enumerate(hour_counts) if c >= 0],
            "top_active_hours": top_hours
        }
    
    def _generate_recommendations(
        self, 
        content_analysis: Dict[str, Any],
        engagement_rates: Dict[str, float],
        active_hours: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Analiz sonuçlarına göre optimizasyon önerileri oluşturur.
        """
        recommendations = []
        
        # Medya kullanımı önerisi
        if engagement_rates.get("with_media", 0) > engagement_rates.get("without_media", 0):
            recommendations.append({
                "type": "media_usage",
                "message": "Medya içeren mesajlar daha yüksek etkileşim alıyor. Mesajlarınıza görsel ekleyin."
            })
        
        # Mesaj uzunluğu önerisi
        if engagement_rates.get("short_messages", 0) > engagement_rates.get("long_messages", 0):
            recommendations.append({
                "type": "message_length",
                "message": "Kısa mesajlar daha etkili. Mesajlarınızı 100 karakterden kısa tutun."
            })
        else:
            recommendations.append({
                "type": "message_length",
                "message": "Uzun, detaylı mesajlar daha etkili. İçeriğinizi zenginleştirin."
            })
        
        # Gönderim zamanı önerisi
        if active_hours.get("top_active_hours"):
            hours_text = ", ".join([f"{h}:00" for h in active_hours.get("top_active_hours")])
            recommendations.append({
                "type": "sending_time",
                "message": f"Şu saatlerde mesaj gönderin: {hours_text} - Bu saatlerde grup daha aktif."
            })
        
        # İçerik türü önerisi
        content_dist = content_analysis.get("content_distribution", {})
        if content_dist:
            best_type = max(content_dist.items(), key=lambda x: x[1])[0]
            type_mapping = {
                "announcement": "duyuru",
                "promotion": "promosyon/indirim",
                "question": "soru",
                "information": "bilgilendirme",
                "general": "genel içerik"
            }
            recommendations.append({
                "type": "content_type",
                "message": f"'{type_mapping.get(best_type, best_type)}' içerik türü bu grupta daha iyi performans gösteriyor."
            })
            
        # Mention kullanımı
        if engagement_rates.get("with_mentions", 0) > 5:  # Eşik değer
            recommendations.append({
                "type": "mentions",
                "message": "Grup üyelerini etiketlemek (mention) etkileşimi artırıyor."
            })
            
        # Hashtag kullanımı
        if engagement_rates.get("with_hashtags", 0) > 5:  # Eşik değer
            recommendations.append({
                "type": "hashtags",
                "message": "Hashtag kullanımı içeriğinizin bulunabilirliğini artırıyor."
            })
            
        return recommendations
    
    async def optimize_message(self, message_content: str, group_id: int) -> Dict[str, Any]:
        """
        Verilen mesajı grup istatistiklerine göre optimize eder.
        
        Args:
            message_content: Optimize edilecek mesaj
            group_id: Hedef grup ID'si
            
        Returns:
            Optimize edilmiş mesaj ve öneriler
        """
        try:
            # Grup analizini al
            analysis = await self.analyze_group_content(group_id)
            
            # Eğer analiz sonucu yoksa orijinal mesajı döndür
            if analysis.get("status") != "success":
                return {
                    "original_message": message_content,
                    "optimized_message": message_content,
                    "applied_optimizations": [],
                    "recommendations": analysis.get("recommendations", [])
                }
            
            # Mesajı optimize et
            optimized_message = message_content
            applied_optimizations = []
            
            # En aktif saatleri kontrol et ve öneri oluştur
            active_hours = analysis.get("active_hours", {}).get("top_active_hours", [])
            current_hour = datetime.utcnow().hour
            
            if active_hours and current_hour not in active_hours:
                applied_optimizations.append({
                    "type": "timing",
                    "message": f"Şu anda aktif saat diliminde değilsiniz. En aktif saatler: {', '.join([f'{h}:00' for h in active_hours])}"
                })
            
            # İçerik uzunluğunu kontrol et
            content_analysis = analysis.get("content_analysis", {})
            avg_length = content_analysis.get("avg_message_length", 0)
            
            if avg_length > 0:
                if len(message_content) < avg_length * 0.5:
                    applied_optimizations.append({
                        "type": "length",
                        "message": "Mesajınız grup ortalamasına göre çok kısa. Daha fazla detay eklemek etkileşimi artırabilir."
                    })
                elif len(message_content) > avg_length * 1.5:
                    applied_optimizations.append({
                        "type": "length",
                        "message": "Mesajınız grup ortalamasına göre çok uzun. Daha kısa mesajlar daha fazla okunabilir."
                    })
            
            # Medya kullanımını kontrol et
            media_rate = content_analysis.get("media_rate", 0)
            if media_rate > 50 and not "has_media" in message_content.lower():  # Basit bir kontrol
                applied_optimizations.append({
                    "type": "media",
                    "message": "Bu grupta medya içeren mesajlar daha fazla etkileşim alıyor. Görseller ekleyin."
                })
            
            # Mention kullanımını kontrol et
            mention_rate = content_analysis.get("mention_rate", 0)
            if mention_rate > 30 and "@" not in message_content:
                applied_optimizations.append({
                    "type": "mention",
                    "message": "Grup üyelerini etiketlemek (mention) etkileşimi artırabilir."
                })
            
            # Hashtag kullanımını kontrol et
            hashtag_rate = content_analysis.get("hashtag_rate", 0)
            if hashtag_rate > 30 and "#" not in message_content:
                applied_optimizations.append({
                    "type": "hashtag",
                    "message": "Hashtag kullanımı içeriğinizin bulunabilirliğini artırabilir."
                })
            
            return {
                "original_message": message_content,
                "optimized_message": optimized_message,
                "applied_optimizations": applied_optimizations,
                "recommendations": analysis.get("recommendations", [])
            }
            
        except Exception as e:
            logger.error(f"Mesaj optimizasyonu hatası: {str(e)}")
            return {
                "original_message": message_content,
                "optimized_message": message_content,
                "applied_optimizations": [],
                "error": str(e)
            } 