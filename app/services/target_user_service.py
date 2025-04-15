from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models import TargetUser

def create_target_user(
    db: Session, 
    owner_id: int, 
    telegram_user_id: str, 
    group_id: str, 
    username: Optional[str] = None, 
    full_name: Optional[str] = None
) -> TargetUser:
    """
    Yeni bir hedef kullanıcı oluşturur
    """
    db_target = TargetUser(
        owner_id=owner_id,
        telegram_user_id=telegram_user_id,
        group_id=group_id,
        username=username,
        full_name=full_name,
        is_dm_sent=False,
        created_at=datetime.utcnow()
    )
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    return db_target

def get_targets_by_owner(db: Session, owner_id: int) -> List[TargetUser]:
    """
    Kullanıcıya ait tüm hedefleri getirir
    """
    return db.query(TargetUser).filter(TargetUser.owner_id == owner_id).all()

def get_targets_by_telegram_id(db: Session, telegram_user_id: str) -> List[TargetUser]:
    """
    Telegram ID'sine göre hedef kullanıcıları bulur
    """
    return db.query(TargetUser).filter(TargetUser.telegram_user_id == telegram_user_id).all()

def mark_dm_sent(db: Session, target_id: int) -> Optional[TargetUser]:
    """
    Hedef kullanıcıya DM gönderildiğini işaretler
    """
    db_target = db.query(TargetUser).filter(TargetUser.id == target_id).first()
    if db_target:
        db_target.is_dm_sent = True
        db.commit()
        db.refresh(db_target)
    return db_target

def mark_dm_sent_by_telegram_id(db: Session, telegram_user_id: str, owner_id: int) -> List[TargetUser]:
    """
    Belirli bir kullanıcının Telegram ID'sine sahip tüm hedefleri için DM gönderildiğini işaretler
    """
    targets = db.query(TargetUser).filter(
        TargetUser.telegram_user_id == telegram_user_id,
        TargetUser.owner_id == owner_id
    ).all()
    
    for target in targets:
        target.is_dm_sent = True
    
    if targets:
        db.commit()
    
    return targets

def delete_target_user(db: Session, id: int) -> bool:
    """
    Hedef kullanıcıyı siler
    """
    db_target = db.query(TargetUser).filter(TargetUser.id == id).first()
    if db_target:
        db.delete(db_target)
        db.commit()
        return True
    return False 