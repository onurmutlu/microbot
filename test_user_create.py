# test_user_create.py

from app.database import SessionLocal
from app.models import User
from app.services.auth_service import get_password_hash

db = SessionLocal()

username = "admin"
password = "admin123"

existing_user = db.query(User).filter(User.username == username).first()
if existing_user:
    print(f"⚠️ Kullanıcı zaten var: {username}")
else:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        is_active=True
    )
    db.add(user)
    db.commit()
    print(f"✅ Kullanıcı oluşturuldu: {username} / {password}")
