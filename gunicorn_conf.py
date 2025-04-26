import os
import multiprocessing

# Sunucu bağlantı ayarları
bind = "0.0.0.0:8000"
backlog = 2048

# İşçi süreçleri
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 60
keepalive = 5

# Süreç ismi
proc_name = "microbot_api"

# Sunucu mekanizması
daemon = False
raw_env = []

# Loglama
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "/var/log/gunicorn/access.log" if os.getenv("PRODUCTION", "false") == "true" else "-"
errorlog = "/var/log/gunicorn/error.log" if os.getenv("PRODUCTION", "false") == "true" else "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Graceful yeniden başlatma
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50

# SSL (gerekirse açılabilir)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Ek özellikler
reload = os.getenv("GUNICORN_RELOAD", "false").lower() == "true"
reload_engine = "auto"

# Durum izleme
statsd_host = os.getenv("STATSD_HOST", None)
statsd_prefix = "microbot" 