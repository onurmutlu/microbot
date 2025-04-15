from sqlalchemy.orm import Session
from typing import Optional, List

from app.crud import auto_reply_rule as rule_crud
from app.models import AutoReplyRule
from app.database import get_db

def get_matching_reply(db: Session, user_id: int, incoming_text: str) -> Optional[str]:
    """
    Gelen metne göre kullanıcının tanımladığı otomatik yanıt kurallarından eşleşen varsa yanıtı döndürür
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        incoming_text: Gelen mesaj metni
        
    Returns:
        Eşleşen yanıt metni veya eşleşme yoksa None
    """
    # Kullanıcının aktif kurallarını al
    active_rules = rule_crud.get_active_rules_by_user(db, user_id)
    
    # Gelen metni küçük harfe çevir (case-insensitive karşılaştırma için)
    incoming_text_lower = incoming_text.lower()
    
    # Kuralları kontrol et
    for rule in active_rules:
        # Tetikleyici kelimeleri virgüle göre ayır ve her birini kontrol et
        trigger_keywords = [keyword.strip().lower() for keyword in rule.trigger_keywords.split(',')]
        
        # Herhangi bir tetikleyici kelime metinde varsa
        for keyword in trigger_keywords:
            if keyword and keyword in incoming_text_lower:
                return rule.response_text
    
    # Eşleşme bulunamadı
    return None

def find_replies_for_message(db: Session, user_id: int, message_text: str) -> List[str]:
    """
    Bir mesaj için tüm eşleşen yanıtları bulur (birden fazla kural eşleşebilir)
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        message_text: Gelen mesaj metni
        
    Returns:
        Eşleşen yanıt metinlerinin listesi
    """
    active_rules = rule_crud.get_active_rules_by_user(db, user_id)
    matching_replies = []
    
    message_text_lower = message_text.lower()
    
    for rule in active_rules:
        trigger_keywords = [keyword.strip().lower() for keyword in rule.trigger_keywords.split(',')]
        
        for keyword in trigger_keywords:
            if keyword and keyword in message_text_lower:
                matching_replies.append(rule.response_text)
                break  # Aynı kural için bir kez ekle
    
    return matching_replies

def check_message_has_reply(db: Session, user_id: int, message_text: str) -> bool:
    """
    Bir mesajın yanıta sahip olup olmadığını kontrol eder
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        message_text: Gelen mesaj metni
        
    Returns:
        Eşleşme varsa True, yoksa False
    """
    reply = get_matching_reply(db, user_id, message_text)
    return reply is not None 