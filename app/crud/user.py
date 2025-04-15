from sqlalchemy.orm import Session
from typing import Optional

from app.models import User
from datetime import datetime

def create_user(
    db: Session, 
    phone_number: str, 
    api_id: str, 
    api_hash: str,
    username: str = None,
    telegram_id: str = None,
    password_hash: str = None
) -> User:
    """
    Yeni bir kullanıcı oluşturur
    """
    db_user = User(
        phone=phone_number, 
        api_id=api_id, 
        api_hash=api_hash,
        username=username,
        telegram_id=telegram_id,
        password_hash=password_hash,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_phone(db: Session, phone_number: str) -> Optional[User]:
    """
    Telefon numarasına göre kullanıcıyı bulur
    """
    return db.query(User).filter(User.phone == phone_number).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Kullanıcı adına göre kullanıcıyı bulur
    """
    return db.query(User).filter(User.username == username).first()

def get_user_by_telegram_id(db: Session, telegram_id: str) -> Optional[User]:
    """
    Telegram ID'sine göre kullanıcıyı bulur
    """
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    ID'ye göre kullanıcıyı bulur
    """
    return db.query(User).filter(User.id == user_id).first()

def update_session_string(db: Session, user_id: int, session_string: str) -> User:
    """
    Kullanıcının oturum string bilgisini günceller
    """
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.session_string = session_string
        db.commit()
        db.refresh(db_user)
    return db_user

def update_telegram_id(db: Session, user_id: int, telegram_id: str) -> User:
    """
    Kullanıcının Telegram ID'sini günceller
    """
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.telegram_id = telegram_id
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_session_string(db: Session, user_id: int) -> User:
    """
    Kullanıcının oturum string bilgisini siler
    """
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.session_string = None
        db.commit()
        db.refresh(db_user)
    return db_user

def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """
    Tüm kullanıcıları getirir
    """
    return db.query(User).offset(skip).limit(limit).all()
