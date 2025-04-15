from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.crud import group as group_crud
from app.models import Group
from app.database import get_db

def fetch_user_groups(db: Session, user_id: int) -> List[Group]:
    """
    Kullanıcıya ait tüm grupları getirir
    """
    return group_crud.get_groups_by_user(db, user_id)

def get_selected_groups(db: Session, user_id: int) -> List[Group]:
    """
    Kullanıcının seçili gruplarını getirir
    """
    return group_crud.get_selected_groups(db, user_id)

def toggle_group_selection(db: Session, group_id: int, is_selected: bool) -> Group:
    """
    Grup seçimini açar/kapatır
    """
    return group_crud.update_group_selection(db, group_id, is_selected)

def sync_groups_with_telegram(db: Session, user_id: int, external_group_list: List[Dict[str, Any]]) -> List[Group]:
    """
    Telegram'dan gelen grup listesini veritabanı ile senkronize eder
    
    external_group_list örnek format:
    [
        {
            "group_id": "123456789",
            "title": "Grup Adı",
            "username": "grupkullaniciadi",
            "member_count": 100
        },
        ...
    ]
    """
    # Tüm grupları daha sonra aktif/pasif işaretlemek için alalım
    existing_groups = {group.group_id: group for group in fetch_user_groups(db, user_id)}
    updated_groups = []
    
    # Dışarıdan gelen grupları veritabanına ekleyelim veya güncelleyelim
    for group_data in external_group_list:
        db_group = group_crud.create_or_update_group(db, group_data, user_id)
        updated_groups.append(db_group)
    
    # Telegram'dan gelmeyen grupları pasif olarak işaretleyelim
    updated_group_ids = [group.group_id for group in updated_groups]
    for group_id, group in existing_groups.items():
        if group_id not in updated_group_ids and group.is_active:
            # delete_group fonksiyonu aslında grubu silmeyip pasif olarak işaretliyor
            group_crud.delete_group(db, group.id)
    
    return updated_groups

def create_group(db: Session, user_id: int, group_data: Dict[str, Any]) -> Group:
    """
    Yeni bir grup oluşturur
    """
    return group_crud.create_or_update_group(db, group_data, user_id)

def mark_message_sent(db: Session, group_id: int) -> Group:
    """
    Gruba mesaj gönderildiğini işaretler
    """
    return group_crud.update_group_message_sent(db, group_id) 