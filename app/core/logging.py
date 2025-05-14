import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

# Log dizini oluştur
log_dir = os.getenv("LOG_DIR", "/app/logs")
os.makedirs(log_dir, exist_ok=True)

# Loglama seviyesi ayarları
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
LEVEL = log_levels.get(LOG_LEVEL, logging.INFO)

# Log formatı
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(LOG_FORMAT)

# Konsol handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(LEVEL)

# Dosya handler (rotasyonlu)
file_handler = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=10_000_000, backupCount=3)
file_handler.setFormatter(formatter)
file_handler.setLevel(LEVEL)

# Hata dosya handler
error_log_dir = os.path.join(log_dir, "errors")
os.makedirs(error_log_dir, exist_ok=True)
error_handler = RotatingFileHandler(os.path.join(error_log_dir, "errors.log"), maxBytes=10_000_000, backupCount=5)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

# Kök logger'ı temizle ve yeniden yapılandır
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Ana logger
logger = logging.getLogger("app")
logger.setLevel(LEVEL)
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.addHandler(error_handler)
logger.propagate = False

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Belirtilen isimle bir logger döndürür.
    
    Args:
        name: Logger ismi. None ise ana logger döner.
        
    Returns:
        Yapılandırılmış logger nesnesi
    """
    if name is None:
        return logger
    
    child_logger = logging.getLogger(f"app.{name}")
    child_logger.setLevel(LEVEL)
    # Handler'lar ana logger'dan miras alınacak
    child_logger.propagate = True
    
    return child_logger 