from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models import MessageLog

def create_log(
    db: Session, 
    user_id: int, 
    group_id: str, 
    group_title: str, 
    template_id: int, 
    status: str, 
    error_message: Optional[str] = None
) -> MessageLog:
    """
    Yeni bir mesaj log kaydı oluşturur
    
    Status değerleri:
    - success: Başarılı gönderim
    - error: Gönderim hatası
    """
    db_log = MessageLog(
        user_id=user_id,
        group_id=group_id,
        group_title=group_title,
        message_template_id=template_id,
        status=status,
        error_message=error_message,
        sent_at=datetime.utcnow()
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_logs_by_user(db: Session, user_id: int) -> List[MessageLog]:
    """
    Kullanıcının tüm log kayıtlarını getirir
    """
    return db.query(MessageLog).filter(MessageLog.user_id == user_id).all()

def get_recent_logs(db: Session, user_id: int, limit: int = 10) -> List[MessageLog]:
    """
    Kullanıcının en son log kayıtlarını getirir
    """
    return db.query(MessageLog).filter(
        MessageLog.user_id == user_id
    ).order_by(
        MessageLog.sent_at.desc()
    ).limit(limit).all()

def get_log_by_id(db: Session, log_id: int) -> Optional[MessageLog]:
    """
    ID'ye göre log kaydını bulur
    """
    return db.query(MessageLog).filter(MessageLog.id == log_id).first()

def get_logs_by_template(db: Session, template_id: int) -> List[MessageLog]:
    """
    Belirli bir şablona ait log kayıtlarını getirir
    """
    return db.query(MessageLog).filter(
        MessageLog.message_template_id == template_id
    ).order_by(
        MessageLog.sent_at.desc()
    ).all()

def get_logs_by_group(db: Session, group_id: str, user_id: int) -> List[MessageLog]:
    """
    Belirli bir gruba ait log kayıtlarını getirir
    """
    return db.query(MessageLog).filter(
        MessageLog.group_id == group_id,
        MessageLog.user_id == user_id
    ).order_by(
        MessageLog.sent_at.desc()
    ).all()

def get_error_logs(db: Session, user_id: int) -> List[MessageLog]:
    """
    Kullanıcının hatalı log kayıtlarını getirir
    """
    return db.query(MessageLog).filter(
        MessageLog.user_id == user_id,
        MessageLog.status == "error"
    ).order_by(
        MessageLog.sent_at.desc()
    ).all() 