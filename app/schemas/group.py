from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.group import GroupType, GroupStatus

class GroupBase(BaseModel):
    title: str
    description: Optional[str] = None
    type: GroupType = GroupType.PUBLIC
    status: GroupStatus = GroupStatus.ACTIVE

class GroupCreate(GroupBase):
    pass

class GroupUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[GroupType] = None
    status: Optional[GroupStatus] = None

class GroupResponse(GroupBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Grup listesi için şema (router'da Group olarak içe aktarılıyor)
class Group(GroupBase):
    id: int
    user_id: int
    group_id: Optional[str] = None  # Telegram grup ID'si
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Grup seçme işlemi için şema
class GroupSelect(BaseModel):
    group_ids: List[int] 