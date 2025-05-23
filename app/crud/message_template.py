from sqlalchemy.orm import Session
from typing import Optional, List

from app.models import MessageTemplate
from datetime import datetime

def get_templates_by_user(db: Session, user_id: int) -> List[MessageTemplate]:
    """
    Kullanıcıya ait tüm mesaj şablonlarını getirir
    """
    return db.query(MessageTemplate).filter(MessageTemplate.user_id == user_id).all()

def get_templates_by_type(db: Session, user_id: int, message_type: str) -> List[MessageTemplate]:
    """
    Kullanıcıya ait belirli türdeki aktif mesaj şablonlarını getirir
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID'si
        message_type: Şablon türü (broadcast, mention, reply)
        
    Returns:
        Eşleşen mesaj şablonlarının listesi
    """
    return db.query(MessageTemplate).filter(
        MessageTemplate.user_id == user_id,
        MessageTemplate.message_type == message_type,
        MessageTemplate.is_active == True
    ).all()

def get_template_by_id(db: Session, template_id: int) -> Optional[MessageTemplate]:
    """
    ID'ye göre mesaj şablonunu bulur
    """
    return db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()

def create_template(
    db: Session, 
    user_id: int, 
    name: str, 
    content: str, 
    interval_minutes: int = 60,
    cron_expression: Optional[str] = None
) -> MessageTemplate:
    """
    Yeni bir mesaj şablonu oluşturur
    
    Args:
        db: Veritabanı oturumu
        user_id: Kullanıcı ID
        name: Şablon adı
        content: Mesaj içeriği
        interval_minutes: Gönderim sıklığı (dakika)
        cron_expression: Cron formatında zamanlama ifadesi (opsiyonel)
        
    Returns:
        Oluşturulan mesaj şablonu
    """
    db_template = MessageTemplate(
        name=name, 
        content=content, 
        interval_minutes=interval_minutes,
        cron_expression=cron_expression,
        user_id=user_id,
        is_active=True
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_template(
    db: Session, 
    template_id: int, 
    name: Optional[str] = None, 
    content: Optional[str] = None, 
    interval_minutes: Optional[int] = None,
    cron_expression: Optional[str] = None
) -> Optional[MessageTemplate]:
    """
    Mesaj şablonunu günceller
    
    Args:
        db: Veritabanı oturumu
        template_id: Şablon ID
        name: Yeni şablon adı (opsiyonel)
        content: Yeni içerik (opsiyonel)
        interval_minutes: Yeni gönderim sıklığı (opsiyonel)
        cron_expression: Yeni cron ifadesi (opsiyonel)
        
    Returns:
        Güncellenen şablon veya None
    """
    db_template = get_template_by_id(db, template_id)
    if db_template:
        if name is not None:
            db_template.name = name
        if content is not None:
            db_template.content = content
        if interval_minutes is not None:
            db_template.interval_minutes = interval_minutes
        if cron_expression is not None:
            db_template.cron_expression = cron_expression
        db.commit()
        db.refresh(db_template)
    return db_template

def update_template_status(db: Session, template_id: int, is_active: bool) -> Optional[MessageTemplate]:
    """
    Mesaj şablonu durumunu günceller (aktif/pasif)
    """
    db_template = get_template_by_id(db, template_id)
    if db_template:
        db_template.is_active = is_active
        db.commit()
        db.refresh(db_template)
    return db_template

def delete_template(db: Session, template_id: int) -> bool:
    """
    Mesaj şablonunu siler
    """
    db_template = get_template_by_id(db, template_id)
    if db_template:
        db.delete(db_template)
        db.commit()
        return True
    return False 