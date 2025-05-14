from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from pydantic import BaseModel
import json

from app.database import get_db
from app.models import AdminUser, AdminRole
from app.config import settings
from app.services.auth_service import get_current_user, require_auth
from app.services.admin_service import get_current_admin_user, require_admin_auth, require_superadmin_auth

router = APIRouter(prefix="/admin", tags=["Admin Management"])

# Şifre hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic modelleri
class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    success: bool
    token: str
    role: str
    username: str

class AdminChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class AdminResponse(BaseModel):
    id: int
    username: str
    role: str
    permissions: List[str]
    created_at: datetime
    last_login: Optional[datetime]

class AdminCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    permissions: Optional[List[str]] = []

class AdminRoleUpdateRequest(BaseModel):
    role: str
    permissions: Optional[List[str]] = []

# JWT token oluşturma
def create_admin_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

# Şifre doğrulama
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Şifre hash'leme
def get_password_hash(password):
    return pwd_context.hash(password)

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(login_data: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Admin kullanıcılar için giriş endpoint'i.
    
    Kullanıcı adı ve şifre doğrulaması yapar ve JWT token üretir.
    """
    # Eğer bu ilk admin ise ve .env dosyasındaki ROOT_ADMIN ile eşleşirse
    if login_data.username == settings.ROOT_ADMIN_USERNAME:
        if not verify_password(login_data.password, settings.ROOT_ADMIN_PASSWORD_HASH):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kullanıcı adı veya şifre hatalı"
            )
        
        # Root admin için token oluştur
        token_data = {
            "sub": "root",
            "username": login_data.username,
            "role": "superadmin"
        }
        token = create_admin_token(token_data)
        
        return {
            "success": True,
            "token": token,
            "role": "superadmin",
            "username": login_data.username
        }
    
    # Normal admin kullanıcıları için veritabanı kontrolü
    admin = db.query(AdminUser).filter(AdminUser.username == login_data.username).first()
    
    if not admin or not verify_password(login_data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı"
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap aktif değil"
        )
    
    # Son giriş tarihini güncelle
    admin.last_login = datetime.utcnow()
    db.commit()
    
    # Token oluştur
    token_data = {
        "sub": str(admin.id),
        "username": admin.username,
        "role": admin.role.value
    }
    token = create_admin_token(token_data)
    
    return {
        "success": True,
        "token": token,
        "role": admin.role.value,
        "username": admin.username
    }

@router.get("/validate")
def validate_admin_token(admin: AdminUser = Depends(get_current_admin_user)):
    """
    Admin token'ının geçerliliğini doğrular.
    
    Geçerli bir token ile istek yapıldığında 200 OK döner.
    """
    if admin:
        return {"valid": True, "username": admin.username, "role": admin.role.value}
    return {"valid": False}

@router.get("/me", response_model=AdminResponse)
def get_current_admin_info(admin: AdminUser = Depends(require_admin_auth)):
    """
    Giriş yapan admin kullanıcının bilgilerini döndürür.
    """
    # JSON string olarak saklanan izinleri listeye dönüştür
    permissions = []
    if admin.permissions:
        try:
            permissions = json.loads(admin.permissions)
        except:
            permissions = []
    
    return {
        "id": admin.id,
        "username": admin.username,
        "role": admin.role.value,
        "permissions": permissions,
        "created_at": admin.created_at,
        "last_login": admin.last_login
    }

@router.post("/change-password")
def change_admin_password(
    password_data: AdminChangePasswordRequest,
    admin: AdminUser = Depends(require_admin_auth),
    db: Session = Depends(get_db)
):
    """
    Admin kullanıcının şifresini değiştirir.
    
    Mevcut şifreyi doğrular ve yeni şifreyi hash'leyerek kaydeder.
    """
    # Root admin için şifre değişikliği yapılamaz
    if admin.username == settings.ROOT_ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Root admin şifresi bu endpoint üzerinden değiştirilemez"
        )
    
    # Mevcut şifreyi doğrula
    if not verify_password(password_data.current_password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mevcut şifre hatalı"
        )
    
    # Yeni şifreyi hash'le ve kaydet
    admin.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"success": True, "message": "Şifre başarıyla değiştirildi"}

@router.get("/users", response_model=List[AdminResponse])
def list_admin_users(
    admin: AdminUser = Depends(require_superadmin_auth),
    db: Session = Depends(get_db)
):
    """
    Tüm admin kullanıcıları listeler.
    
    Yalnızca superadmin rolündeki kullanıcılar bu endpoint'e erişebilir.
    """
    admin_users = db.query(AdminUser).all()
    
    admin_list = []
    for user in admin_users:
        permissions = []
        if user.permissions:
            try:
                permissions = json.loads(user.permissions)
            except:
                permissions = []
        
        admin_list.append({
            "id": user.id,
            "username": user.username,
            "role": user.role.value,
            "permissions": permissions,
            "created_at": user.created_at,
            "last_login": user.last_login
        })
    
    return admin_list

@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=AdminResponse)
def create_admin_user(
    user_data: AdminCreateRequest,
    admin: AdminUser = Depends(require_superadmin_auth),
    db: Session = Depends(get_db)
):
    """
    Yeni bir admin kullanıcı oluşturur.
    
    Yalnızca superadmin rolündeki kullanıcılar bu endpoint'e erişebilir.
    """
    # Kullanıcı adı kontrolü
    existing_user = db.query(AdminUser).filter(AdminUser.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu kullanıcı adı zaten kullanılıyor"
        )
    
    # Rol kontrolü
    try:
        role = AdminRole(user_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz rol. Kullanılabilir roller: admin, superadmin"
        )
    
    # İzinleri JSON olarak kaydet
    permissions_json = json.dumps(user_data.permissions) if user_data.permissions else None
    
    # Yeni admin kullanıcı oluştur
    new_admin = AdminUser(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=role,
        permissions=permissions_json,
        created_at=datetime.utcnow(),
        is_active=True
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    # Yanıt için izinleri listeye dönüştür
    permissions = []
    if new_admin.permissions:
        try:
            permissions = json.loads(new_admin.permissions)
        except:
            permissions = []
    
    return {
        "id": new_admin.id,
        "username": new_admin.username,
        "role": new_admin.role.value,
        "permissions": permissions,
        "created_at": new_admin.created_at,
        "last_login": new_admin.last_login
    }

@router.put("/users/{user_id}/role")
def update_admin_role(
    user_id: int,
    role_data: AdminRoleUpdateRequest,
    admin: AdminUser = Depends(require_superadmin_auth),
    db: Session = Depends(get_db)
):
    """
    Admin kullanıcının rolünü ve izinlerini günceller.
    
    Yalnızca superadmin rolündeki kullanıcılar bu endpoint'e erişebilir.
    """
    # Kullanıcıyı bul
    target_admin = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not target_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {user_id} olan admin kullanıcı bulunamadı"
        )
    
    # Root admin güncellenemez
    if target_admin.username == settings.ROOT_ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Root admin rolü değiştirilemez"
        )
    
    # Rol kontrolü
    try:
        role = AdminRole(role_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz rol. Kullanılabilir roller: admin, superadmin"
        )
    
    # İzinleri JSON olarak kaydet
    permissions_json = json.dumps(role_data.permissions) if role_data.permissions else None
    
    # Rol ve izinleri güncelle
    target_admin.role = role
    target_admin.permissions = permissions_json
    
    db.commit()
    
    return {"success": True, "message": "Admin kullanıcı rolü güncellendi"} 