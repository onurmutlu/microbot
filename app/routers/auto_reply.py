from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import User, AutoReplyRule
from app.services.auth_service import get_current_active_user
from app.crud import auto_reply_rule as rule_crud
from app.services.auto_reply_service import get_best_reply, find_regex_matches

router = APIRouter(
    prefix="/api",
    tags=["auto-reply"]
)

# Pydantic modelleri
class AutoReplyRuleBase(BaseModel):
    trigger_keywords: str = Field(..., description="Virgülle ayrılmış tetikleyici kelimeler. Regex için 'r:' öneki kullanın.")
    response_text: str = Field(..., description="Yanıt metni. Değişken kullanımı için {değişken} formatını kullanabilirsiniz.")
    is_active: bool = Field(True, description="Kuralın aktif olup olmadığı")

class AutoReplyRuleCreate(AutoReplyRuleBase):
    pass

class AutoReplyRuleUpdate(AutoReplyRuleBase):
    id: Optional[int] = Field(None, description="Güncellenmek istenen kuralın ID'si. Yoksa yeni kural oluşturulur.")

class AutoReplyRuleResponse(AutoReplyRuleBase):
    id: int
    created_at: str
    
    class Config:
        orm_mode = True

class AutoReplyTest(BaseModel):
    message: str = Field(..., description="Test edilecek mesaj metni")

class RegexTest(BaseModel):
    pattern: str = Field(..., description="Test edilecek regex ifadesi")
    test_text: str = Field(..., description="Regex'in test edileceği metin")

@router.get("/auto-replies", response_model=List[AutoReplyRuleResponse])
async def get_auto_replies(
    is_active: Optional[bool] = Query(None, description="Aktif kuralları filtrele (True/False)"),
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    """
    Kullanıcının tüm otomatik yanıt kurallarını getirir.
    
    - **is_active**: İsteğe bağlı olarak sadece aktif (True) veya pasif (False) kuralları getirir.
    """
    rules = rule_crud.get_reply_rules_by_user(db, current_user.id)
    
    if is_active is not None:
        rules = [rule for rule in rules if rule.is_active == is_active]
        
    return rules

@router.post("/auto-replies", response_model=AutoReplyRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_auto_reply(
    rule: AutoReplyRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Yeni bir otomatik yanıt kuralı oluşturur.
    
    - **trigger_keywords**: Virgülle ayrılmış tetikleyici kelimeler. Örn: "merhaba,selam,hello"
    - **response_text**: Gönderilecek yanıt metni. Değişken kullanımı desteklenir: {name}, {username}, {group}
    - **is_active**: Kural aktif mi (varsayılan: True)
    
    **Regex Kullanımı**: Tetikleyici kelimede regex kullanmak için "r:" öneki ile başlayın:
    ```
    r:merhaba.*dünya
    ```
    
    **Değişken Kullanımı**:
    ```
    Merhaba {name}, yardımcı olabilirim!
    ```
    """
    # Yeni kural oluştur
    new_rule = rule_crud.create_reply_rule(
        db,
        current_user.id,
        rule.trigger_keywords,
        rule.response_text
    )
    
    if not rule.is_active:
        # Varsayılan olarak aktif, ama pasif olarak ayarlanmışsa güncelle
        rule_crud.update_reply_rule(db, new_rule.id, is_active=rule.is_active)
        new_rule.is_active = rule.is_active
    
    return new_rule

@router.put("/auto-replies/{rule_id}", response_model=AutoReplyRuleResponse)
async def update_auto_reply(
    rule_id: int,
    rule: AutoReplyRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Mevcut bir otomatik yanıt kuralını günceller.
    
    - **rule_id**: Güncellenecek kuralın ID'si
    - **trigger_keywords**: Virgülle ayrılmış tetikleyici kelimeler
    - **response_text**: Gönderilecek yanıt metni
    - **is_active**: Kural aktif mi
    """
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
    
    # Kuralı güncelle
    updated_rule = rule_crud.update_reply_rule(
        db,
        rule_id,
        trigger_keywords=rule.trigger_keywords,
        response_text=rule.response_text,
        is_active=rule.is_active
    )
    return updated_rule

@router.patch("/auto-replies/{rule_id}/toggle", response_model=AutoReplyRuleResponse)
async def toggle_auto_reply_status(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Otomatik yanıt kuralının aktif/pasif durumunu değiştirir.
    
    - **rule_id**: Değiştirilecek kuralın ID'si
    """
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
    
    # Durumu tersine çevir
    new_status = not existing_rule.is_active
    
    # Kuralı güncelle
    updated_rule = rule_crud.update_reply_rule(
        db,
        rule_id,
        is_active=new_status
    )
    return updated_rule

@router.delete("/auto-replies/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auto_reply(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Otomatik yanıt kuralını siler.
    
    - **rule_id**: Silinecek kuralın ID'si
    """
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

@router.post("/auto-replies/test", response_model=Dict[str, Any])
async def test_auto_reply(
    test_data: AutoReplyTest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Bir mesajı, kullanıcının mevcut otomatik yanıt kurallarına karşı test eder.
    
    - **message**: Test edilecek mesaj metni
    
    Bu endpoint, bir mesajın hangi kuralla eşleşeceğini ve nasıl bir yanıt üretileceğini test etmenizi sağlar.
    """
    # En iyi eşleşmeyi bul
    reply, meta = get_best_reply(db, current_user.id, test_data.message)
    
    if reply:
        return {
            "has_match": True,
            "response": reply,
            "match_details": meta
        }
    else:
        return {
            "has_match": False,
            "message": "Bu mesaj için eşleşen kural bulunamadı."
        }

@router.post("/auto-replies/test-regex", response_model=Dict[str, Any])
async def test_regex_pattern(
    test_data: RegexTest
):
    """
    Bir regex ifadesini test eder.
    
    - **pattern**: Test edilecek regex ifadesi
    - **test_text**: Regex'in test edileceği metin
    
    Bu endpoint, bir regex ifadesinin çalışıp çalışmadığını ve hangi grupları yakaladığını test etmenizi sağlar.
    """
    import re
    
    try:
        # Regex ifadesini derle
        regex = re.compile(test_data.pattern, re.IGNORECASE)
        
        # Metinde ara
        match = regex.search(test_data.test_text)
        
        if match:
            # Yakalanan grupları dönüştür
            groups = match.groups()
            named_groups = match.groupdict()
            
            return {
                "is_valid": True,
                "has_match": True,
                "match_text": match.group(0),
                "groups": groups,
                "named_groups": named_groups
            }
        else:
            return {
                "is_valid": True,
                "has_match": False,
                "message": "Eşleşme bulunamadı"
            }
    except re.error as e:
        return {
            "is_valid": False,
            "has_match": False,
            "error": str(e),
            "message": "Geçersiz regex ifadesi"
        } 