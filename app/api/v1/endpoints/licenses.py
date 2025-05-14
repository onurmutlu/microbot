from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import secrets
import string

from app.database import get_db
from app.models import License, LicenseType, User
from app.config import settings
from app.services.auth_service import get_current_user, require_auth
from app.services.admin_service import require_admin_auth, require_superadmin_auth

router = APIRouter(tags=["License Management"])

# Pydantic modelleri
class LicenseBase(BaseModel):
    type: str
    validityDays: int

class LicenseResponse(BaseModel):
    id: int
    key: str
    type: str
    expiry_date: datetime
    is_active: bool
    created_at: datetime
    used_by: Optional[str] = None

class LicenseValidateRequest(BaseModel):
    license_key: str

class LicenseValidateResponse(BaseModel):
    valid: bool
    message: str
    licenseData: Optional[LicenseResponse] = None

class LicenseAssignRequest(BaseModel):
    license_key: str
    user_identifier: str  # E-posta veya telefon

def generate_license_key(license_type: str) -> str:
    """
    Benzersiz bir lisans anahtarı oluşturur.
    Format: {LICENSE_TYPE}-XXXX-XXXX (örn: PRO-1234-ABCD)
    """
    prefix = license_type
    chars = string.ascii_uppercase + string.digits
    segment1 = ''.join(secrets.choice(chars) for _ in range(4))
    segment2 = ''.join(secrets.choice(chars) for _ in range(4))
    
    return f"{prefix}-{segment1}-{segment2}"

@router.get("/admin/licenses", response_model=List[LicenseResponse])
def list_licenses(
    admin=Depends(require_admin_auth),
    db: Session = Depends(get_db)
):
    """
    Tüm lisansları listeler.
    
    Bu endpoint'e yalnızca admin kullanıcılar erişebilir.
    """
    licenses = db.query(License).all()
    
    return [
        {
            "id": license.id,
            "key": license.key,
            "type": license.type.value,
            "expiry_date": license.expiry_date,
            "is_active": license.is_active,
            "created_at": license.created_at,
            "used_by": license.used_by
        }
        for license in licenses
    ]

@router.post("/admin/licenses", status_code=status.HTTP_201_CREATED, response_model=LicenseResponse)
def create_license(
    license_data: LicenseBase,
    admin=Depends(require_admin_auth),
    db: Session = Depends(get_db)
):
    """
    Yeni bir lisans oluşturur.
    
    Bu endpoint'e yalnızca admin kullanıcılar erişebilir.
    """
    # Lisans tipini kontrol et
    try:
        license_type = LicenseType(license_data.type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geçersiz lisans tipi. Kullanılabilir tipler: {[t.value for t in LicenseType]}"
        )
    
    # Yeni bir lisans anahtarı oluştur
    key = generate_license_key(license_data.type)
    
    # Geçerlilik süresini hesapla
    expiry_date = datetime.utcnow() + timedelta(days=license_data.validityDays)
    
    # Yeni lisans oluştur
    new_license = License(
        key=key,
        type=license_type,
        expiry_date=expiry_date,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(new_license)
    db.commit()
    db.refresh(new_license)
    
    return {
        "id": new_license.id,
        "key": new_license.key,
        "type": new_license.type.value,
        "expiry_date": new_license.expiry_date,
        "is_active": new_license.is_active,
        "created_at": new_license.created_at,
        "used_by": new_license.used_by
    }

@router.delete("/admin/licenses/{license_id}", status_code=status.HTTP_200_OK)
def delete_license(
    license_id: int,
    admin=Depends(require_admin_auth),
    db: Session = Depends(get_db)
):
    """
    Lisansı siler.
    
    Bu endpoint'e yalnızca admin kullanıcılar erişebilir.
    """
    # Lisansı bul
    license = db.query(License).filter(License.id == license_id).first()
    
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {license_id} olan lisans bulunamadı"
        )
    
    # Lisans kullanımda mı kontrol et
    if license.user_id or license.used_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu lisans kullanımda olduğu için silinemez"
        )
    
    # Lisansı sil
    db.delete(license)
    db.commit()
    
    return {"success": True, "message": "Lisans başarıyla silindi"}

@router.get("/licenses/user", response_model=List[LicenseResponse])
def get_user_licenses(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Giriş yapmış kullanıcının lisanslarını getirir.
    """
    # Kullanıcıya ait lisansları bul
    user_licenses = db.query(License).filter(License.user_id == current_user.id).all()
    
    return [
        {
            "id": license.id,
            "key": license.key,
            "type": license.type.value,
            "expiry_date": license.expiry_date,
            "is_active": license.is_active,
            "created_at": license.created_at,
            "used_by": license.used_by
        }
        for license in user_licenses
    ]

@router.post("/licenses/validate", response_model=LicenseValidateResponse)
def validate_license(
    license_data: LicenseValidateRequest,
    db: Session = Depends(get_db)
):
    """
    Lisans anahtarını doğrular.
    """
    # Lisansı bul
    license = db.query(License).filter(License.key == license_data.license_key).first()
    
    # Lisans bulunamadı
    if not license:
        return {
            "valid": False,
            "message": "Geçersiz lisans anahtarı",
            "licenseData": None
        }
    
    # Lisans aktif değil
    if not license.is_active:
        return {
            "valid": False,
            "message": "Lisans aktif değil",
            "licenseData": None
        }
    
    # Lisans süresi dolmuş
    if license.expiry_date < datetime.utcnow():
        # Süresi dolan lisansı otomatik devre dışı bırak
        license.is_active = False
        db.commit()
        
        return {
            "valid": False,
            "message": "Lisans süresi dolmuş",
            "licenseData": None
        }
    
    # Lisans geçerli
    return {
        "valid": True,
        "message": "Lisans geçerli",
        "licenseData": {
            "id": license.id,
            "key": license.key,
            "type": license.type.value,
            "expiry_date": license.expiry_date,
            "is_active": license.is_active,
            "created_at": license.created_at,
            "used_by": license.used_by
        }
    }

@router.post("/licenses/assign", response_model=LicenseValidateResponse)
def assign_license(
    assign_data: LicenseAssignRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Lisans anahtarını kullanıcıya atar.
    """
    # Lisansı bul
    license = db.query(License).filter(License.key == assign_data.license_key).first()
    
    # Lisans bulunamadı
    if not license:
        return {
            "valid": False,
            "message": "Geçersiz lisans anahtarı",
            "licenseData": None
        }
    
    # Lisans aktif değil
    if not license.is_active:
        return {
            "valid": False,
            "message": "Lisans aktif değil",
            "licenseData": None
        }
    
    # Lisans süresi dolmuş
    if license.expiry_date < datetime.utcnow():
        # Süresi dolan lisansı otomatik devre dışı bırak
        license.is_active = False
        db.commit()
        
        return {
            "valid": False,
            "message": "Lisans süresi dolmuş",
            "licenseData": None
        }
    
    # Lisans zaten kullanımda
    if license.user_id and license.user_id != current_user.id:
        return {
            "valid": False,
            "message": "Bu lisans başka bir kullanıcı tarafından kullanılıyor",
            "licenseData": None
        }
    
    # Lisansı kullanıcıya ata
    license.user_id = current_user.id
    license.used_by = assign_data.user_identifier
    
    db.commit()
    db.refresh(license)
    
    return {
        "valid": True,
        "message": "Lisans başarıyla atandı",
        "licenseData": {
            "id": license.id,
            "key": license.key,
            "type": license.type.value,
            "expiry_date": license.expiry_date,
            "is_active": license.is_active,
            "created_at": license.created_at,
            "used_by": license.used_by
        }
    } 