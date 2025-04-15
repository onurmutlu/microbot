from sqlalchemy.orm import Session
from typing import Optional, List

from app.models import User
from app.crud import user as user_crud

def get_user_by_phone(db: Session, phone_number: str) -> Optional[User]:
    """
    Telefon numarasına göre kullanıcıyı bulur
    """
    return user_crud.get_user_by_phone(db, phone_number)

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Kullanıcı adına göre kullanıcıyı bulur
    """
    # Bu fonksiyon şu anda crud'da yok, ama iş mantığı açısından gerekli
    return db.query(User).filter(User.username == username).first()

def get_user_by_telegram_id(db: Session, telegram_id: str) -> Optional[User]:
    """
    Telegram ID'sine göre kullanıcıyı bulur
    """
    return user_crud.get_user_by_telegram_id(db, telegram_id)

def create_user(db: Session, username: str, phone_number: str, api_id: str, api_hash: str, telegram_id: str = None, password_hash: str = None) -> User:
    """
    Yeni bir kullanıcı oluşturur
    """
    return user_crud.create_user(
        db=db, 
        username=username,
        phone_number=phone_number, 
        api_id=api_id, 
        api_hash=api_hash,
        telegram_id=telegram_id,
        password_hash=password_hash
    )

def update_user_session_string(db: Session, user_id: int, session_string: str) -> Optional[User]:
    """
    Kullanıcının oturum stringini günceller
    """
    return user_crud.update_session_string(db, user_id, session_string)

def set_user_telegram_id(db: Session, user_id: int, telegram_id: str) -> Optional[User]:
    """
    Kullanıcının Telegram ID'sini atar (ilk oturum veya eksik kayıt durumlarında)
    """
    return user_crud.update_telegram_id(db, user_id, telegram_id)

# İş mantığı gerektiren ek fonksiyonlar buraya eklenebilir
def register_and_authenticate_user(db: Session, username: str, phone_number: str, api_id: str, api_hash: str) -> User:
    """
    Kullanıcıyı kaydeder ve oturum açar (daha yüksek seviyeli iş mantığı)
    """
    # Önce kullanıcıyı kontrol et
    existing_user = get_user_by_phone(db, phone_number)
    if existing_user:
        # Kullanıcı zaten var, güncellenebilir veya hata döndürülebilir
        return existing_user
        
    # Yeni kullanıcı oluştur
    return create_user(db, username, phone_number, api_id, api_hash) 