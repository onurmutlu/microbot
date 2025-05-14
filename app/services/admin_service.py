from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models import AdminUser
from app.config import settings

async def get_current_admin_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[AdminUser]:
    """
    JWT token ile kimliği doğrulanmış admin kullanıcısını döndürür.
    Doğrulama başarısız olursa None döndürür.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulama başarısız",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Authorization header'dan token al
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
            
        token = auth_header.split(" ")[1]
        
        # Token'ı doğrula
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        
        # Kullanıcı ID'sini al
        user_id = payload.get("sub")
        username = payload.get("username")
        role = payload.get("role")
        
        if not user_id or not username or not role:
            return None
            
        # Root admin kontrolü
        if user_id == "root" and username == settings.ROOT_ADMIN_USERNAME:
            # Root admin için sahte bir AdminUser nesnesi oluştur
            root_admin = AdminUser(
                id=0,
                username=settings.ROOT_ADMIN_USERNAME,
                role="superadmin",
                permissions='["*"]',  # Tüm izinler
                created_at=datetime.utcnow(),
                is_active=True
            )
            return root_admin
            
        # Veritabanından admin kullanıcıyı al
        admin = db.query(AdminUser).filter(AdminUser.id == int(user_id)).first()
        if not admin or not admin.is_active:
            return None
            
        return admin
            
    except JWTError:
        return None
    except Exception:
        return None

def require_admin_auth(
    current_admin: Optional[AdminUser] = Depends(get_current_admin_user)
) -> AdminUser:
    """
    Admin yetkisi gerektiren endpoint'ler için kimlik doğrulama.
    Geçerli bir admin yoksa 401 hatası fırlatır.
    """
    if not current_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_admin

def require_superadmin_auth(
    current_admin: AdminUser = Depends(require_admin_auth)
) -> AdminUser:
    """
    Süper admin yetkisi gerektiren endpoint'ler için kimlik doğrulama.
    Kullanıcı süper admin değilse 403 hatası fırlatır.
    """
    if current_admin.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için süper admin yetkisi gerekli"
        )
    return current_admin

def has_permission(admin: AdminUser, permission: str) -> bool:
    """
    Admin kullanıcının belirli bir izne sahip olup olmadığını kontrol eder.
    """
    # Süper admin her zaman tüm izinlere sahiptir
    if admin.role == "superadmin":
        return True
        
    try:
        import json
        permissions = json.loads(admin.permissions) if admin.permissions else []
        return permission in permissions or "*" in permissions
    except:
        return False

def require_permission(permission: str):
    """
    Belirli bir izin gerektiren endpoint'ler için decorator.
    """
    def dependency(admin: AdminUser = Depends(require_admin_auth)):
        if not has_permission(admin, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için '{permission}' izni gerekli"
            )
        return admin
    
    return dependency 