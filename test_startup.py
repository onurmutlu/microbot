#!/usr/bin/env python3
"""
MicroBot başlatma testi

Bu script, MicroBot uygulamasının WebSocket ve SSE Manager'larını güvenli şekilde başlatır.
"""

import asyncio
import logging
import sys
import os

# Temel logging ayarlarını yap
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("test_startup")

async def main():
    logger.info("Test başlatılıyor...")
    
    try:
        # app modülünü import et
        from app.services.sse_manager import sse_manager
        from app.services.websocket_manager import websocket_manager
        
        logger.info("SSE ve WebSocket Manager'lar yüklendi")
        
        # Temizlik görevlerini başlat
        sse_manager.start_cleanup_task()
        websocket_manager.start_cleanup_task()
        
        logger.info("Temizlik görevleri başlatıldı")
        
        # Bir süre bekle
        await asyncio.sleep(2)
        
        # Temizlik görevlerini durdur
        sse_manager.stop_cleanup_task()
        websocket_manager.stop_cleanup_task()
        
        logger.info("Temizlik görevleri durduruldu")
        
        logger.info("Test başarılı!")
        return True
    except Exception as e:
        logger.error(f"Test hatası: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 