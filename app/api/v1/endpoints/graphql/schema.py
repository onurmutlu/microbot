import strawberry
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import Depends
import logging

from app.db.database import get_db
from app.models.user import User
from app.models.group import Group
from app.models.message import Message
from app.services.ai.content_optimizer import ContentOptimizer
from app.services.auth_service import get_optional_user
from app.services.cache_service import cache_service
from app.config import settings

logger = logging.getLogger(__name__)

# GraphQL Tipler

@strawberry.type
class GroupType:
    id: int
    telegram_id: int
    title: str
    description: Optional[str] = None
    member_count: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool
    
@strawberry.type
class MessageType:
    id: int
    telegram_id: int
    content: str
    sent_at: datetime
    group_id: int
    user_id: int
    
@strawberry.type
class EngagementRateType:
    with_media: float
    with_links: float
    with_mentions: float
    with_hashtags: float
    short_messages: float
    long_messages: float

@strawberry.type
class ContentAnalysisType:
    avg_message_length: float
    media_rate: float
    link_rate: float
    mention_rate: float
    hashtag_rate: float
    
@strawberry.type
class RecommendationType:
    type: str
    message: str
    
@strawberry.type
class ActiveHourType:
    hour: int
    count: int

@strawberry.type
class ActiveHoursType:
    hour_distribution: List[ActiveHourType]
    top_active_hours: List[int]
    
@strawberry.type
class ContentInsightType:
    status: str
    group_id: Optional[int] = None
    message_count: Optional[int] = None
    success_rate: Optional[float] = None
    content_analysis: Optional[ContentAnalysisType] = None
    engagement_rates: Optional[EngagementRateType] = None
    active_hours: Optional[ActiveHoursType] = None
    recommendations: List[RecommendationType]
    message: Optional[str] = None
    timestamp: Optional[str] = None

@strawberry.type
class OptimizedMessageType:
    original_message: str
    optimized_message: str
    applied_optimizations: List[RecommendationType]
    recommendations: List[RecommendationType]
    error: Optional[str] = None

# Context sınıfı
class Context:
    def __init__(self, db: Session, user: Optional[User] = None):
        self.db = db
        self.user = user

# Resolver fonksiyonları
async def get_group(group_id: int, info) -> Optional[GroupType]:
    db = info.context.db
    try:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return None
        return GroupType(
            id=group.id,
            telegram_id=group.telegram_id,
            title=group.title,
            description=group.description,
            member_count=group.member_count,
            created_at=group.created_at,
            updated_at=group.updated_at,
            is_active=group.is_active
        )
    except Exception as e:
        logger.error(f"GraphQL grup sorgulama hatası: {str(e)}")
        return None

async def get_groups(info) -> List[GroupType]:
    db = info.context.db
    try:
        groups = db.query(Group).all()
        return [
            GroupType(
                id=group.id,
                telegram_id=group.telegram_id,
                title=group.title,
                description=group.description,
                member_count=group.member_count,
                created_at=group.created_at,
                updated_at=group.updated_at,
                is_active=group.is_active
            )
            for group in groups
        ]
    except Exception as e:
        logger.error(f"GraphQL grupları listeleme hatası: {str(e)}")
        return []

async def get_group_content_insights(group_id: int, info) -> ContentInsightType:
    db = info.context.db
    try:
        # Önbellekten kontrol et
        if settings.CACHE_ENABLED:
            cache_key = f"group_insights:{group_id}"
            cached_insight = await cache_service.get(cache_key)
            if cached_insight:
                # Önbellekten alınan veriyi ContentInsightType'a dönüştür
                return _convert_to_content_insight_type(cached_insight)
        
        optimizer = ContentOptimizer(db)
        analysis = await optimizer.analyze_group_content(group_id)
        
        # Önbelleğe kaydet
        if settings.CACHE_ENABLED and analysis.get("status") == "success":
            await cache_service.set(
                f"group_insights:{group_id}", 
                analysis, 
                expire=settings.CONTENT_ANALYSIS_CACHE_TTL
            )
        
        # Dönen sonucu ContentInsightType'a dönüştür
        return _convert_to_content_insight_type(analysis)
    except Exception as e:
        logger.error(f"GraphQL içerik analizi hatası: {str(e)}")
        return ContentInsightType(
            status="error",
            message=f"İçerik analizi sırasında hata oluştu: {str(e)}",
            recommendations=[]
        )

# Yardımcı fonksiyon: Dict'ten ContentInsightType oluşturur
def _convert_to_content_insight_type(analysis: Dict[str, Any]) -> ContentInsightType:
    recommendations = [
        RecommendationType(type=rec["type"], message=rec["message"])
        for rec in analysis.get("recommendations", [])
    ]
    
    content_analysis = None
    if "content_analysis" in analysis:
        content_analysis = ContentAnalysisType(
            avg_message_length=analysis["content_analysis"].get("avg_message_length", 0),
            media_rate=analysis["content_analysis"].get("media_rate", 0),
            link_rate=analysis["content_analysis"].get("link_rate", 0),
            mention_rate=analysis["content_analysis"].get("mention_rate", 0),
            hashtag_rate=analysis["content_analysis"].get("hashtag_rate", 0)
        )
        
    engagement_rates = None
    if "engagement_rates" in analysis:
        engagement_rates = EngagementRateType(
            with_media=analysis["engagement_rates"].get("with_media", 0),
            with_links=analysis["engagement_rates"].get("with_links", 0),
            with_mentions=analysis["engagement_rates"].get("with_mentions", 0),
            with_hashtags=analysis["engagement_rates"].get("with_hashtags", 0),
            short_messages=analysis["engagement_rates"].get("short_messages", 0),
            long_messages=analysis["engagement_rates"].get("long_messages", 0)
        )
        
    active_hours = None
    if "active_hours" in analysis:
        hour_distribution = [
            ActiveHourType(hour=item["hour"], count=item["count"])
            for item in analysis["active_hours"].get("hour_distribution", [])
        ]
        
        active_hours = ActiveHoursType(
            hour_distribution=hour_distribution,
            top_active_hours=analysis["active_hours"].get("top_active_hours", [])
        )
        
    return ContentInsightType(
        status=analysis.get("status", "error"),
        group_id=analysis.get("group_id"),
        message_count=analysis.get("message_count"),
        success_rate=analysis.get("success_rate"),
        content_analysis=content_analysis,
        engagement_rates=engagement_rates,
        active_hours=active_hours,
        recommendations=recommendations,
        message=analysis.get("message"),
        timestamp=analysis.get("timestamp")
    )

async def optimize_message(message: str, group_id: int, info) -> OptimizedMessageType:
    db = info.context.db
    try:
        optimizer = ContentOptimizer(db)
        result = await optimizer.optimize_message(message, group_id)
        
        applied_optimizations = [
            RecommendationType(type=opt["type"], message=opt["message"])
            for opt in result.get("applied_optimizations", [])
        ]
        
        recommendations = [
            RecommendationType(type=rec["type"], message=rec["message"])
            for rec in result.get("recommendations", [])
        ]
        
        return OptimizedMessageType(
            original_message=result.get("original_message", ""),
            optimized_message=result.get("optimized_message", ""),
            applied_optimizations=applied_optimizations,
            recommendations=recommendations,
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"GraphQL mesaj optimizasyonu hatası: {str(e)}")
        return OptimizedMessageType(
            original_message=message,
            optimized_message=message,
            applied_optimizations=[],
            recommendations=[],
            error=str(e)
        )

# Query ve Mutation sınıfları
@strawberry.type
class Query:
    @strawberry.field
    async def group(self, group_id: int, info) -> Optional[GroupType]:
        return await get_group(group_id, info)
    
    @strawberry.field
    async def groups(self, info) -> List[GroupType]:
        return await get_groups(info)
    
    @strawberry.field
    async def group_content_insights(self, group_id: int, info) -> ContentInsightType:
        return await get_group_content_insights(group_id, info)
    
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def optimize_message(self, message: str, group_id: int, info) -> OptimizedMessageType:
        return await optimize_message(message, group_id, info)

# Ana GraphQL şeması
schema = strawberry.Schema(query=Query, mutation=Mutation)

# FastAPI bağlantısı için
async def get_context(db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    return Context(db=db, user=user) 