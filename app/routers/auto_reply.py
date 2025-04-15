from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import User, AutoReplyRule
from app.services.auth_service import get_current_active_user
from app.crud import auto_reply_rule as rule_crud

router = APIRouter(
    prefix="/api",
    tags=["auto-reply"]
)

# Pydantic modelleri
class AutoReplyRuleBase(BaseModel):
    trigger_keywords: str
    response_text: str
    is_active: bool = True

class AutoReplyRuleCreate(AutoReplyRuleBase):
    pass

class AutoReplyRuleUpdate(AutoReplyRuleBase):
    id: Optional[int] = None

class AutoReplyRuleResponse(AutoReplyRuleBase):
    id: int
    created_at: str
    
    class Config:
        orm_mode = True

@router.get("/auto-replies", response_model=List[AutoReplyRuleResponse])
async def get_auto_replies(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    """Kullanıcının tüm otomatik yanıt kurallarını getirir"""
    rules = rule_crud.get_reply_rules_by_user(db, current_user.id)
    return rules

@router.post("/auto-replies", response_model=AutoReplyRuleResponse)
async def create_or_update_auto_reply(
    rule: AutoReplyRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Yeni bir otomatik yanıt kuralı oluşturur veya var olanı günceller"""
    if rule.id:
        # Önce kuralın varlığını ve sahipliğini kontrol et
        existing_rule = rule_crud.get_rule_by_id(db, rule.id)
        if not existing_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kural bulunamadı"
            )
        
        if existing_rule.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu kural üzerinde işlem yapamazsınız"
            )
        
        # Kuralı güncelle
        updated_rule = rule_crud.update_reply_rule(
            db,
            rule.id,
            trigger_keywords=rule.trigger_keywords,
            response_text=rule.response_text,
            is_active=rule.is_active
        )
        return updated_rule
    else:
        # Yeni kural oluştur
        new_rule = rule_crud.create_reply_rule(
            db,
            current_user.id,
            rule.trigger_keywords,
            rule.response_text
        )
        return new_rule

@router.delete("/auto-replies/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auto_reply(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Otomatik yanıt kuralını siler"""
    # Önce kuralın varlığını ve sahipliğini kontrol et
    existing_rule = rule_crud.get_rule_by_id(db, rule_id)
    if not existing_rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kural bulunamadı"
        )
    
    if existing_rule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu kural üzerinde işlem yapamazsınız"
        )
    
    # Kuralı sil
    result = rule_crud.delete_reply_rule(db, rule_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kural silinirken bir hata oluştu"
        ) 