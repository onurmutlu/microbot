from sqlalchemy.orm import Session
from typing import Optional, List

from app.models import TargetUser
from datetime import datetime

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

def get_target_by_id(db: Session, target_id: int) -> Optional[TargetUser]:
    """
    ID'ye göre hedef kullanıcıyı bulur
    """
    return db.query(TargetUser).filter(TargetUser.id == target_id).first()

def get_target_by_telegram_id(db: Session, telegram_user_id: str) -> Optional[TargetUser]:
    """
    Telegram kullanıcı ID'sine göre hedef kullanıcıyı bulur
    """
    return db.query(TargetUser).filter(TargetUser.telegram_user_id == telegram_user_id).first()

def mark_dm_sent(db: Session, telegram_user_id: str) -> None:
    """
    Belirli bir Telegram kullanıcı ID'sine sahip tüm hedeflerin DM gönderildi durumunu işaretler
    """
    targets = db.query(TargetUser).filter(TargetUser.telegram_user_id == telegram_user_id).all()
    
    for target in targets:
        target.is_dm_sent = True
    
    if targets:
        db.commit()

def delete_target_user(db: Session, target_user_id: int) -> None:
    """
    Belirli bir ID'ye sahip hedef kullanıcıyı siler
    """
    db_target = db.query(TargetUser).filter(TargetUser.id == target_user_id).first()
    if db_target:
        db.delete(db_target)
        db.commit()

def list_targets(db: Session, skip: int = 0, limit: int = 100) -> List[TargetUser]:
    """
    Tüm hedef kullanıcıları listeler (sayfalama ile)
    """
    return db.query(TargetUser).offset(skip).limit(limit).all() 