from sqlalchemy.orm import Session
from typing import Optional, List

from app.models import AutoReplyRule
from datetime import datetime

def get_reply_rules_by_user(db: Session, user_id: int) -> List[AutoReplyRule]:
    """
    Kullanıcıya ait tüm otomatik yanıt kurallarını getirir
    """
    return db.query(AutoReplyRule).filter(AutoReplyRule.user_id == user_id).all()

def get_active_rules_by_user(db: Session, user_id: int) -> List[AutoReplyRule]:
    """
    Kullanıcıya ait aktif otomatik yanıt kurallarını getirir
    """
    return db.query(AutoReplyRule).filter(
        AutoReplyRule.user_id == user_id,
        AutoReplyRule.is_active == True
    ).all()

def get_rule_by_id(db: Session, rule_id: int) -> Optional[AutoReplyRule]:
    """
    ID'ye göre kuralı bulur
    """
    return db.query(AutoReplyRule).filter(AutoReplyRule.id == rule_id).first()

def create_reply_rule(
    db: Session,
    user_id: int,
    trigger_keywords: str,
    response_text: str
) -> AutoReplyRule:
    """
    Yeni bir otomatik yanıt kuralı oluşturur
    """
    db_rule = AutoReplyRule(
        user_id=user_id,
        trigger_keywords=trigger_keywords,
        response_text=response_text,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

def update_reply_rule(
    db: Session,
    rule_id: int,
    trigger_keywords: Optional[str] = None,
    response_text: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Optional[AutoReplyRule]:
    """
    Var olan bir otomatik yanıt kuralını günceller
    """
    db_rule = get_rule_by_id(db, rule_id)
    if db_rule:
        if trigger_keywords is not None:
            db_rule.trigger_keywords = trigger_keywords
        if response_text is not None:
            db_rule.response_text = response_text
        if is_active is not None:
            db_rule.is_active = is_active
            
        db.commit()
        db.refresh(db_rule)
    return db_rule

def create_or_update_reply_rule(
    db: Session,
    user_id: int,
    rule_id: Optional[int] = None,
    trigger_keywords: Optional[str] = None,
    response_text: Optional[str] = None
) -> AutoReplyRule:
    """
    Yeni bir otomatik yanıt kuralı oluşturur veya var olanı günceller
    """
    if rule_id:
        db_rule = get_rule_by_id(db, rule_id)
        if db_rule and db_rule.user_id == user_id:
            # Kuralı güncelle
            if trigger_keywords is not None:
                db_rule.trigger_keywords = trigger_keywords
            if response_text is not None:
                db_rule.response_text = response_text
                
            db.commit()
            db.refresh(db_rule)
            return db_rule
    
    # Yeni kural oluştur
    return create_reply_rule(db, user_id, trigger_keywords, response_text)

def enable_disable_rule(db: Session, rule_id: int, is_active: bool) -> Optional[AutoReplyRule]:
    """
    Kuralın aktif/pasif durumunu değiştirir
    """
    return update_reply_rule(db, rule_id, is_active=is_active)

def delete_reply_rule(db: Session, rule_id: int) -> bool:
    """
    Otomatik yanıt kuralını siler
    """
    db_rule = get_rule_by_id(db, rule_id)
    if db_rule:
        db.delete(db_rule)
        db.commit()
        return True
    return False 