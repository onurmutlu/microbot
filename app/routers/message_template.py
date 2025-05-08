from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import User, MessageTemplate
from app.services.auth_service import get_current_active_user
from app.crud import message_template as template_crud

router = APIRouter(
    prefix="/message-templates",
    tags=["templates"]
)

# Pydantic modelleri
class MessageTemplateBase(BaseModel):
    name: str
    content: str
    interval_minutes: int = 60
    message_type: str = "broadcast"  # broadcast, reply, mention

class MessageTemplateCreate(MessageTemplateBase):
    cron_expression: Optional[str] = None

class MessageTemplateUpdate(MessageTemplateBase):
    is_active: Optional[bool] = None

class MessageTemplateToggle(BaseModel):
    is_active: bool

class MessageTemplateResponse(MessageTemplateBase):
    id: int
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True

@router.get("", response_model=List[MessageTemplateResponse])
async def get_message_templates(
    message_type: Optional[str] = Query(None, description="Filtre: broadcast, reply, mention"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Kullanıcının tüm mesaj şablonlarını getirir. İsteğe bağlı olarak message_type ile filtrelenebilir."""
    if message_type:
        templates = template_crud.get_templates_by_type(db, current_user.id, message_type)
    else:
        templates = template_crud.get_templates_by_user(db, current_user.id)
    return {"success": True, "message": "Templates retrieved successfully", "data": templates}

@router.post("", response_model=MessageTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_message_template(
    template: MessageTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Yeni bir mesaj şablonu oluşturur.
    
    Parametreler:
    - **name**: Şablon adı
    - **content**: Mesaj içeriği
    - **interval_minutes**: Gönderim sıklığı (dakika olarak)
    - **cron_expression**: Cron formatında zamanlama ifadesi (opsiyonel)
    
    Cron formatı örneği: "0 9 * * 1-5" (Hafta içi her gün saat 9'da)
    """
    new_template = template_crud.create_template(
        db=db,
        user_id=current_user.id,
        name=template.name,
        content=template.content,
        interval_minutes=template.interval_minutes,
        cron_expression=template.cron_expression
    )
    return {"success": True, "message": "Template created successfully", "data": new_template}

@router.put("/{template_id}", response_model=MessageTemplateResponse)
async def update_message_template(
    template_id: int,
    template: MessageTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Bir mesaj şablonunu günceller.
    
    Parametreler:
    - **name**: Yeni şablon adı (opsiyonel)
    - **content**: Yeni mesaj içeriği (opsiyonel)
    - **interval_minutes**: Yeni gönderim sıklığı (opsiyonel)
    - **cron_expression**: Yeni cron ifadesi (opsiyonel)
    - **is_active**: Aktif/pasif durumu (opsiyonel)
    """
    # Şablonun kullanıcıya ait olup olmadığını kontrol et
    db_template = template_crud.get_template_by_id(db, template_id)
    if not db_template:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Şablon bulunamadı", "data": {}}
        )
    if db_template.user_id != current_user.id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": "Bu şablona erişim izniniz yok", "data": {}}
        )
    
    # Şablonu güncelle
    updated_template = template_crud.update_template(
        db=db,
        template_id=template_id,
        name=template.name,
        content=template.content,
        interval_minutes=template.interval_minutes,
        cron_expression=template.cron_expression
    )
    
    # is_active değeri verilmişse, durumu güncelle
    if template.is_active is not None:
        template_crud.update_template_status(db, template_id, template.is_active)
        updated_template = template_crud.get_template_by_id(db, template_id)
    
    return {"success": True, "message": "Template updated successfully", "data": updated_template}

@router.patch("/{template_id}/toggle", response_model=MessageTemplateResponse)
async def toggle_template_status(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Şablonun aktif/pasif durumunu değiştirir"""
    # Önce şablonun varlığını ve sahipliğini kontrol et
    existing_template = template_crud.get_template_by_id(db, template_id)
    if not existing_template:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Şablon bulunamadı", "data": {}}
        )
    
    if existing_template.user_id != current_user.id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": "Bu şablon üzerinde işlem yapamazsınız", "data": {}}
        )
    
    # Şablonun durumunu tersine çevir
    new_status = not existing_template.is_active
    updated_template = template_crud.update_template_status(
        db=db,
        template_id=template_id,
        is_active=new_status
    )
    return {"success": True, "message": "Template status toggled successfully", "data": updated_template}

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mesaj şablonunu siler"""
    # Önce şablonun varlığını ve sahipliğini kontrol et
    existing_template = template_crud.get_template_by_id(db, template_id)
    if not existing_template:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "Şablon bulunamadı", "data": {}}
        )
    
    if existing_template.user_id != current_user.id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": "Bu şablon üzerinde işlem yapamazsınız", "data": {}}
        )
    
    # Şablonu sil
    result = template_crud.delete_template(db, template_id)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Şablon silinirken bir hata oluştu", "data": {}}
        )
    
    return {"success": True, "message": "Template deleted successfully", "data": {}} 