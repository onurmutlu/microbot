#!/usr/bin/env python
# Admin kullanıcısı oluşturma betiği
# Kullanım: python -m scripts.create_admin

import sys
import os
import getpass
import secrets
import string
from pathlib import Path
from sqlalchemy.orm import Session

# Ana uygulamayı içe aktarabilmek için ana dizini ekleyin
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import User, UserRole
from app.services.auth_service import AuthService

def generate_password(length=16):
    """Güçlü rastgele şifre oluşturur."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in string.punctuation for c in password)):
            return password

def create_admin_user(db: Session):
    """Admin kullanıcısı oluşturur."""
    print("\n" + "="*50)
    print("Telegram MicroBot - Admin Kullanıcı Oluşturma")
    print("="*50 + "\n")
    
    # Veritabanında admin kullanıcı sayısını kontrol et
    admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
    if admin_count > 0:
        print(f"Sistemde zaten {admin_count} admin kullanıcısı bulunuyor.")
        create_another = input("Başka bir admin kullanıcısı eklemek istiyor musunuz? (e/h): ").lower()
        if create_another != 'e':
            print("İptal edildi.")
            return
    
    # Kullanıcı bilgilerini al
    username = input("Kullanıcı adı: ")
    
    # Kullanıcı adının mevcut olup olmadığını kontrol et
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        print(f"Hata: '{username}' kullanıcı adı zaten kullanılıyor.")
        return
    
    # Şifre seçeneği
    password_choice = input("Rastgele güçlü şifre oluşturmak için 'r', kendi şifrenizi girmek için 'k' yazın: ").lower()
    
    if password_choice == 'r':
        password = generate_password()
        print(f"\nOluşturulan şifre: {password}")
        print("BU ŞİFREYİ GÜVENLİ BİR YERE KAYDEDİN - tekrar gösterilmeyecek!")
    else:
        password = getpass.getpass("Şifre: ")
        password_confirm = getpass.getpass("Şifreyi tekrar girin: ")
        
        if password != password_confirm:
            print("Hata: Şifreler eşleşmiyor.")
            return
        
        if len(password) < 8:
            print("Hata: Şifre en az 8 karakter olmalıdır.")
            return
    
    # Telegram API bilgileri
    print("\nTelegram API bilgileri gereklidir.")
    print("Bu bilgileri https://my.telegram.org/ adresinden alabilirsiniz.")
    
    api_id = input("Telegram API ID: ")
    api_hash = input("Telegram API Hash: ")
    phone = input("Telefon numarası (uluslararası format, örn: +901234567890): ")
    
    # Kullanıcı oluştur
    auth_service = AuthService(db)
    hashed_password = auth_service.get_password_hash(password)
    
    # Kullanıcı nesnesi oluştur
    new_user = User(
        username=username,
        password_hash=hashed_password,
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        is_active=True,
        role=UserRole.ADMIN
    )
    
    # Veritabanına kaydet
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print("\n" + "-"*50)
    print(f"Admin kullanıcısı başarıyla oluşturuldu!")
    print(f"Kullanıcı adı: {username}")
    if password_choice == 'r':
        print(f"Şifre: {password}")
    print("-"*50 + "\n")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        create_admin_user(db)
    except KeyboardInterrupt:
        print("\nİşlem iptal edildi.")
    except Exception as e:
        print(f"\nHata oluştu: {str(e)}")
    finally:
        db.close() 