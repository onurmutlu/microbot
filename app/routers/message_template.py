from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import User, MessageTemplate
from app.services.auth_service import get_current_active_user
from app.crud import message_template as template_crud

router = APIRouter()

# Pydantic modelleri
class MessageTemplateBase(BaseModel):
    name: str
    content: str
    interval_minutes: int = 60
    message_type: str = "broadcast"  # broadcast, reply, mention

class MessageTemplateCreate(MessageTemplateBase):
    pass

class MessageTemplateUpdate(MessageTemplateBase):
    pass

class MessageTemplateToggle(BaseModel):
    is_active: bool

class MessageTemplateResponse(MessageTemplateBase):
    id: int
    is_active: bool
    created_at: str
    
    class Config:
        orm_mode = True

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
    return templates

@router.post("", response_model=MessageTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_message_template(
    template: MessageTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Yeni bir mesaj şablonu oluşturur"""
    new_template = template_crud.create_template(
        db=db,
        user_id=current_user.id,
        name=template.name,
        content=template.content,
        interval_minutes=template.interval_minutes
    )
    return new_template

@router.put("/{template_id}", response_model=MessageTemplateResponse)
async def update_message_template(
    template_id: int,
    template: MessageTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mevcut bir mesaj şablonunu günceller"""
    # Önce şablonun varlığını ve sahipliğini kontrol et
    existing_template = template_crud.get_template_by_id(db, template_id)
    if not existing_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şablon bulunamadı"
        )
    
    if existing_template.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu şablon üzerinde işlem yapamazsınız"
        )
    
    # Şablonu güncelle
    updated_template = template_crud.update_template(
        db=db,
        template_id=template_id,
        name=template.name,
        content=template.content,
        interval_minutes=template.interval_minutes
    )
    return updated_template

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şablon bulunamadı"
        )
    
    if existing_template.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu şablon üzerinde işlem yapamazsınız"
        )
    
    # Şablonun durumunu tersine çevir
    new_status = not existing_template.is_active
    updated_template = template_crud.update_template_status(
        db=db,
        template_id=template_id,
        is_active=new_status
    )
    return updated_template

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Şablon bulunamadı"
        )
    
    if existing_template.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu şablon üzerinde işlem yapamazsınız"
        )
    
    # Şablonu sil
    result = template_crud.delete_template(db, template_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Şablon silinirken bir hata oluştu"
        ) 