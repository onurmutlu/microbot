from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.models import Group
from datetime import datetime

def get_groups_by_user(db: Session, user_id: int) -> List[Group]:
    """
    Kullanıcıya ait tüm grupları getirir
    """
    return db.query(Group).filter(Group.user_id == user_id).all()

def get_selected_groups(db: Session, user_id: int) -> List[Group]:
    """
    Kullanıcının seçtiği grupları getirir
    """
    return db.query(Group).filter(
        Group.user_id == user_id,
        Group.is_selected == True
    ).all()

def get_group_by_id(db: Session, group_id: int) -> Optional[Group]:
    """
    ID'ye göre grubu bulur
    """
    return db.query(Group).filter(Group.id == group_id).first()

def get_group_by_telegram_id(db: Session, group_id: str, user_id: int) -> Optional[Group]:
    """
    Telegram grup ID'sine göre grubu bulur
    """
    return db.query(Group).filter(
        Group.group_id == group_id,
        Group.user_id == user_id
    ).first()

def update_group_selection(db: Session, group_id: int, is_selected: bool) -> Optional[Group]:
    """
    Grup seçim durumunu günceller
    """
    db_group = get_group_by_id(db, group_id)
    if db_group:
        db_group.is_selected = is_selected
        db.commit()
        db.refresh(db_group)
    return db_group

def create_or_update_group(db: Session, group_data: Dict[str, Any], user_id: int) -> Group:
    """
    Grup ekler veya günceller
    
    group_data içerisinde beklenenler:
    - group_id: Telegram grup ID'si
    - title: Grup başlığı
    - username: Grup kullanıcı adı (opsiyonel)
    - member_count: Üye sayısı (opsiyonel)
    """
    # Var olan grubu kontrol et
    db_group = get_group_by_telegram_id(db, group_data.get("group_id"), user_id)
    
    if db_group:
        # Grup varsa güncelle
        db_group.title = group_data.get("title", db_group.title)
        db_group.username = group_data.get("username", db_group.username)
        db_group.member_count = group_data.get("member_count", db_group.member_count)
        db_group.is_active = True  # Grup aktif olarak işaretle
    else:
        # Yeni grup oluştur
        db_group = Group(
            group_id=group_data.get("group_id"),
            title=group_data.get("title"),
            username=group_data.get("username"),
            member_count=group_data.get("member_count"),
            user_id=user_id,
            is_selected=False,
            is_active=True,
            message_count=0
        )
        db.add(db_group)
    
    db.commit()
    db.refresh(db_group)
    return db_group

def update_group_message_sent(db: Session, group_id: int) -> Optional[Group]:
    """
    Gruba mesaj gönderildiğinde son gönderim zamanını ve sayacı günceller
    """
    db_group = get_group_by_id(db, group_id)
    if db_group:
        db_group.last_message = datetime.utcnow()
        db_group.message_count += 1
        db.commit()
        db.refresh(db_group)
    return db_group

def delete_group(db: Session, group_id: int) -> bool:
    """
    Grubu siler (veya pasif olarak işaretler)
    """
    db_group = get_group_by_id(db, group_id)
    if db_group:
        # Silmek yerine pasif olarak işaretle
        db_group.is_active = False
        db.commit()
        return True
    return False 