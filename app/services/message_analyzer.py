from typing import Dict, List, Any, Optional
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Message
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.response_template import ResponseTemplate
import re
import json

class MessageAnalyzer:
    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self.db: Session = SessionLocal()
        
    async def analyze_message(self, message: Message) -> Dict[str, Any]:
        """Gelen mesajı analiz et"""
        try:
            # Temel mesaj bilgileri
            analysis = {
                "message_id": message.id,
                "chat_id": message.chat_id,
                "sender_id": message.sender_id,
                "text": message.text,
                "timestamp": message.date,
                "is_private": message.is_private,
                "keywords": [],
                "sentiment": "neutral",
                "category": "other",
                "requires_response": False
            }
            
            # Anahtar kelimeleri çıkar
            analysis["keywords"] = self._extract_keywords(message.text)
            
            # Duygu analizi yap
            analysis["sentiment"] = self._analyze_sentiment(message.text)
            
            # Mesaj kategorisini belirle
            analysis["category"] = self._categorize_message(message.text)
            
            # Yanıt gerekip gerekmediğini belirle
            analysis["requires_response"] = self._requires_response(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing message: {str(e)}")
            return {}

    def _extract_keywords(self, text: str) -> List[str]:
        """Metinden anahtar kelimeleri çıkar"""
        if not text:
            return []
            
        # Basit anahtar kelime çıkarma
        words = text.lower().split()
        keywords = []
        
        # Önemli kelimeleri belirle
        important_words = ["soru", "yardım", "destek", "problem", "hata", 
                         "teşekkür", "öneri", "şikayet", "bilgi"]
                         
        for word in words:
            if word in important_words:
                keywords.append(word)
                
        return keywords

    def _analyze_sentiment(self, text: str) -> str:
        """Metnin duygusal tonunu analiz et"""
        if not text:
            return "neutral"
            
        text = text.lower()
        
        # Olumlu kelimeler
        positive_words = ["teşekkür", "harika", "mükemmel", "güzel", "iyi"]
        
        # Olumsuz kelimeler
        negative_words = ["kötü", "berbat", "hata", "problem", "şikayet"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _categorize_message(self, text: str) -> str:
        """Mesajı kategorilere ayır"""
        if not text:
            return "other"
            
        text = text.lower()
        
        categories = {
            "question": ["soru", "nasıl", "neden", "ne zaman"],
            "support": ["yardım", "destek", "problem", "hata"],
            "feedback": ["teşekkür", "öneri", "şikayet"],
            "information": ["bilgi", "açıklama", "detay"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                return category
                
        return "other"

    def _requires_response(self, analysis: Dict[str, Any]) -> bool:
        """Mesajın yanıt gerektirip gerektirmediğini belirle"""
        if analysis["category"] in ["question", "support"]:
            return True
            
        if analysis["sentiment"] == "negative":
            return True
            
        return False

    async def generate_response(self, analysis: Dict[str, Any]) -> Optional[str]:
        """Uygun yanıtı oluştur"""
        try:
            # Şablonu seç
            template = self.db.query(ResponseTemplate).filter_by(
                category=analysis["category"],
                sentiment=analysis["sentiment"]
            ).first()
            
            if not template:
                return None
                
            # Yanıtı özelleştir
            response = template.content
            
            # Dinamik değişkenleri ekle
            variables = {
                "{user}": str(analysis["sender_id"]),
                "{date}": datetime.now().strftime("%d.%m.%Y"),
                "{time}": datetime.now().strftime("%H:%M")
            }
            
            for var, value in variables.items():
                response = response.replace(var, value)
                
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return None

    async def save_analysis(self, analysis: Dict[str, Any]) -> bool:
        """Analiz sonuçlarını kaydet"""
        try:
            # Analiz sonuçlarını JSON olarak kaydet
            analysis_json = json.dumps(analysis, default=str)
            
            # Veritabanına kaydet
            # TODO: Analiz modeli oluştur ve kaydet
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis: {str(e)}")
            return False 