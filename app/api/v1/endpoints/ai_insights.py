from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timedelta
import time
import hashlib

from app.db.database import get_db
from app.services.auth_service import get_current_user
from app.services.ai.content_optimizer import ContentOptimizer
from app.models.user import User
from app.services.cache_service import cache_service
from app.config import settings

router = APIRouter(
    prefix="/ai",
    tags=["AI Insights"],
    responses={404: {"description": "Not found"}},
)

# Basit rate limiting için helper fonksiyon
async def check_rate_limit(request: Request, limit_key: str, max_requests: int = 10, window_seconds: int = 60):
    """
    Basit bir rate limiting kontrolü yapar
    
    Args:
        request: HTTP isteği
        limit_key: Limit için anahtar (endpoint ismi gibi)
        max_requests: İzin verilen maksimum istek sayısı
        window_seconds: Zaman penceresi (saniye)
        
    Raises:
        HTTPException: Rate limit aşıldığında
    """
    if not settings.CACHE_ENABLED:
        return  # Cache yoksa rate limiting çalışmaz
        
    # İstemci IP adresi veya kullanıcı kimliği alınır
    client_id = request.client.host
    
    # Rate limit anahtarı oluştur
    rl_key = f"ratelimit:{client_id}:{limit_key}"
    
    # Mevcut sayacı kontrol et
    current_count = await cache_service.get(rl_key, 0)
    
    if current_count >= max_requests:
        # Rate limit aşıldı
        retry_after = await cache_service.ttl(rl_key)
        if retry_after <= 0:
            # Anahtarın TTL'i sona ermiş, sıfırla
            await cache_service.set(rl_key, 1, expire=window_seconds)
            return
            
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit aşıldı. {retry_after} saniye sonra tekrar deneyin",
            headers={"Retry-After": str(retry_after)}
        )
    
    # Sayacı artır
    if current_count == 0:
        # İlk istek, sayacı başlat
        await cache_service.set(rl_key, 1, expire=window_seconds)
    else:
        # Sayacı artır
        await cache_service.increment(rl_key)

@router.get("/group-insights/{group_id}", operation_id="get_group_content_insights")
async def get_group_insights(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Bir grubun içerik analizini ve performans önerilerini döndürür.
    
    Args:
        group_id: Analiz edilecek grubun ID'si
        
    Returns:
        Grup için içerik analizi ve öneriler
    """
    # Rate limit kontrolü
    await check_rate_limit(request, "group_insights", max_requests=5, window_seconds=60)
    
    try:
        # Önbellekten kontrol et
        cache_key = f"group_insights:{group_id}"
        if settings.CACHE_ENABLED:
            cached_analysis = await cache_service.get(cache_key)
            if cached_analysis:
                return cached_analysis
        
        # ContentOptimizer servisini başlat
        optimizer = ContentOptimizer(db)
        
        # Grup analizini yap
        analysis = await optimizer.analyze_group_content(group_id)
        
        # Önbelleğe al
        if settings.CACHE_ENABLED and analysis.get("status") == "success":
            await cache_service.set(
                cache_key, 
                analysis, 
                expire=settings.CONTENT_ANALYSIS_CACHE_TTL
            )
        
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Grup analizi sırasında hata oluştu: {str(e)}"
        )
        
@router.post("/optimize-message", operation_id="optimize_message_for_group")
async def optimize_message(
    request: Request,
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Verilen mesajı belirtilen grup için optimize eder.
    
    Args:
        data: İçerisinde message ve group_id olan dictionary
            - message: Optimize edilecek mesaj metni
            - group_id: Hedef grup ID'si
            
    Returns:
        Optimize edilmiş mesaj ve öneriler
    """
    # Rate limit kontrolü
    await check_rate_limit(request, "optimize_message", max_requests=10, window_seconds=60)
    
    try:
        # Gerekli alanların var olduğunu kontrol et
        if "message" not in data or "group_id" not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gerekli alanlar eksik: 'message' ve 'group_id' gerekli"
            )
            
        message = data["message"]
        group_id = data["group_id"]
        
        # Önbellekten kontrol et
        cache_key = f"optimized_message:{group_id}:{hashlib.md5(message.encode()).hexdigest()}"
        if settings.CACHE_ENABLED:
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return {
                    "success": True,
                    "data": cached_result,
                    "cache_hit": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # ContentOptimizer servisini başlat
        optimizer = ContentOptimizer(db)
        
        # Mesajı optimize et
        result = await optimizer.optimize_message(message, group_id)
        
        # Önbelleğe al (30 dakika)
        if settings.CACHE_ENABLED:
            await cache_service.set(cache_key, result, expire=1800)
        
        return {
            "success": True,
            "data": result,
            "cache_hit": False,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mesaj optimizasyonu sırasında hata oluştu: {str(e)}"
        )

@router.post("/batch-analyze", operation_id="batch_analyze_groups")
async def batch_analyze_groups(
    request: Request,
    group_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Birden fazla grubu toplu olarak analiz eder.
    
    Args:
        group_ids: Analiz edilecek grup ID'leri listesi
        
    Returns:
        Her grup için analiz sonuçları
    """
    # Rate limit kontrolü - bu işlem yoğun kaynak kullandığı için daha sıkı limit
    await check_rate_limit(request, "batch_analyze", max_requests=2, window_seconds=300)
    
    try:
        # Grup sayısı sınırlaması
        if len(group_ids) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tek seferde en fazla 10 grup analiz edilebilir"
            )
        
        # ContentOptimizer servisini başlat
        optimizer = ContentOptimizer(db)
        
        # Her grup için analiz yap
        results = {}
        for group_id in group_ids:
            try:
                # Önbellekten kontrol et
                cache_key = f"group_insights:{group_id}"
                cached_analysis = None
                if settings.CACHE_ENABLED:
                    cached_analysis = await cache_service.get(cache_key)
                
                if cached_analysis:
                    results[str(group_id)] = cached_analysis
                else:
                    # Analiz yap
                    analysis = await optimizer.analyze_group_content(group_id)
                    results[str(group_id)] = analysis
                    
                    # Önbelleğe al
                    if settings.CACHE_ENABLED and analysis.get("status") == "success":
                        await cache_service.set(
                            cache_key, 
                            analysis, 
                            expire=settings.CONTENT_ANALYSIS_CACHE_TTL
                        )
            except Exception as group_e:
                results[str(group_id)] = {
                    "status": "error",
                    "message": f"Grup analizi sırasında hata: {str(group_e)}"
                }
                
        return {
            "success": True,
            "data": results,
            "count": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Toplu analiz sırasında hata oluştu: {str(e)}"
        ) 