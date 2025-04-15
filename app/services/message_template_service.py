from sqlalchemy.orm import Session
from typing import List, Optional

from app.crud import message_template as template_crud
from app.models import MessageTemplate

def list_templates_for_user(db: Session, user_id: int) -> List[MessageTemplate]:
    """
    Kullanıcıya ait tüm mesaj şablonlarını listeler
    """
    return template_crud.get_templates_by_user(db, user_id)

def create_new_template(db: Session, user_id: int, name: str, content: str, interval_minutes: int = 60) -> MessageTemplate:
    """
    Kullanıcı için yeni bir mesaj şablonu oluşturur
    
    Parametreler:
    - user_id: Şablonu oluşturacak kullanıcı ID'si
    - name: Şablon adı
    - content: Mesaj içeriği
    - interval_minutes: Gönderim sıklığı (dakika) (varsayılan: 60)
    """
    return template_crud.create_template(db, user_id, name, content, interval_minutes)

def enable_disable_template(db: Session, template_id: int, is_active: bool) -> Optional[MessageTemplate]:
    """
    Mesaj şablonunu aktifleştirir veya devre dışı bırakır
    
    Parametreler:
    - template_id: Şablon ID'si
    - is_active: True - Aktif, False - Pasif
    """
    return template_crud.update_template_status(db, template_id, is_active)

def update_template_content(db: Session, template_id: int, name: str = None, content: str = None, interval_minutes: int = None) -> Optional[MessageTemplate]:
    """
    Mesaj şablonu içeriğini günceller
    """
    return template_crud.update_template(db, template_id, name, content, interval_minutes)

def get_template_by_id(db: Session, template_id: int) -> Optional[MessageTemplate]:
    """
    ID'ye göre mesaj şablonunu getirir
    """
    return template_crud.get_template_by_id(db, template_id)

def remove_template(db: Session, template_id: int) -> bool:
    """
    Mesaj şablonunu siler
    """
    return template_crud.delete_template(db, template_id) 