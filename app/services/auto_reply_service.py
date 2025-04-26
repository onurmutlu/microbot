from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Tuple, Any
import re
import logging

from app.crud import auto_reply_rule as rule_crud
from app.models import AutoReplyRule
from app.database import get_db

logger = logging.getLogger(__name__)

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
                return process_template_variables(rule.response_text, {
                    "keyword": keyword,
                    "message": incoming_text
                })
    
    # Eşleşme bulunamadı
    return None

def find_replies_for_message(db: Session, user_id: int, message_text: str) -> List[Dict[str, Any]]:
    """
    Bir mesaj için tüm eşleşen yanıtları bulur (birden fazla kural eşleşebilir)
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        message_text: Gelen mesaj metni
        
    Returns:
        Eşleşen yanıt metinleri ve ilgili bilgilerin listesi
    """
    active_rules = rule_crud.get_active_rules_by_user(db, user_id)
    matching_replies = []
    
    message_text_lower = message_text.lower()
    
    for rule in active_rules:
        trigger_keywords = [keyword.strip().lower() for keyword in rule.trigger_keywords.split(',')]
        
        for keyword in trigger_keywords:
            if keyword and keyword in message_text_lower:
                reply_text = process_template_variables(rule.response_text, {
                    "keyword": keyword,
                    "message": message_text
                })
                
                matching_replies.append({
                    "rule_id": rule.id,
                    "trigger_keyword": keyword,
                    "response_text": reply_text
                })
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

def process_template_variables(template: str, variables: Dict[str, str]) -> str:
    """
    Yanıt şablonunda değişkenleri değiştirir
    
    Args:
        template: Yanıt şablonu
        variables: Değiştirilecek değişkenler sözlüğü
        
    Returns:
        İşlenmiş yanıt metni
    """
    result = template
    
    # Temel değişken değiştirme - {değişken_adı} formatını kullanır
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    
    return result

def find_regex_matches(db: Session, user_id: int, message_text: str) -> List[Dict[str, Any]]:
    """
    Regex tabanlı gelişmiş eşleştirme yapar
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        message_text: Gelen mesaj metni
        
    Returns:
        Eşleşen yanıtların listesi ve yakalanan gruplar
    """
    active_rules = rule_crud.get_active_rules_by_user(db, user_id)
    matching_replies = []
    
    for rule in active_rules:
        # Regex olarak işaretlenmiş kuralları kontrol et (r: prefix ile)
        trigger_keywords = [k.strip() for k in rule.trigger_keywords.split(',')]
        
        for keyword in trigger_keywords:
            if keyword.startswith("r:"):
                # Regex modunda eşleştirme yap
                pattern = keyword[2:].strip()  # "r:" prefixini kaldır
                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                    match = regex.search(message_text)
                    
                    if match:
                        # Yakalanan grupları değişkenlere dönüştür
                        variables = {
                            "message": message_text,
                            "keyword": pattern
                        }
                        
                        # Yakalanan grupları ekle
                        if match.groups():
                            for i, group in enumerate(match.groups(), 1):
                                variables[f"group{i}"] = group
                        
                        # Named groups
                        variables.update(match.groupdict())
                        
                        reply_text = process_template_variables(rule.response_text, variables)
                        
                        matching_replies.append({
                            "rule_id": rule.id,
                            "trigger_pattern": pattern,
                            "response_text": reply_text,
                            "matches": match.groups(),
                            "named_matches": match.groupdict()
                        })
                        break
                except re.error as e:
                    logger.error(f"Geçersiz regex paterni: {pattern} - Hata: {str(e)}")
    
    return matching_replies

def get_best_reply(db: Session, user_id: int, message_text: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Bir mesaj için en iyi yanıtı ve meta verilerini döndürür
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        message_text: Gelen mesaj metni
        
    Returns:
        (yanıt metni, meta veriler) tuple'ı veya (None, {}) eşleşme yoksa
    """
    # Önce regex eşleşmeleri kontrol et (daha spesifik)
    regex_matches = find_regex_matches(db, user_id, message_text)
    if regex_matches:
        best_match = regex_matches[0]  # İlk eşleşmeyi al
        return best_match["response_text"], {
            "rule_id": best_match["rule_id"],
            "match_type": "regex",
            "pattern": best_match["trigger_pattern"],
            "captures": best_match.get("matches", []),
            "named_captures": best_match.get("named_matches", {})
        }
    
    # Sonra normal anahtar kelime eşleşmelerini kontrol et
    keyword_matches = find_replies_for_message(db, user_id, message_text)
    if keyword_matches:
        best_match = keyword_matches[0]  # İlk eşleşmeyi al
        return best_match["response_text"], {
            "rule_id": best_match["rule_id"],
            "match_type": "keyword",
            "keyword": best_match["trigger_keyword"]
        }
    
    # Eşleşme yoksa
    return None, {} 