# Prometheus ve Grafana Kurulum Kılavuzu

Bu rehber, Telegram MicroBot API projesine Prometheus ve Grafana eklemek için adım adım talimatlar içerir.

## 1. Prometheus ve Grafana için Docker Compose Yapılandırması

Öncelikle, mevcut `docker-compose.prod.yml` dosyanızı düzenleyin ve aşağıdaki servisleri ekleyin:

```yaml
# docker-compose.prod.yml dosyasına ekleyin
services:
  # Mevcut servisler (app, db, vb.)
  # ...

  prometheus:
    image: prom/prometheus:v2.46.0
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    ports:
      - "9090:9090"
    restart: unless-stopped
    networks:
      - microbot-network

  grafana:
    image: grafana/grafana:10.2.0
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=secure_password
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    restart: unless-stopped
    networks:
      - microbot-network
    depends_on:
      - prometheus

volumes:
  # Mevcut volumes (postgres_data, vb.)
  # ...
  prometheus_data:
  grafana_data:

networks:
  microbot-network:
    driver: bridge
```

## 2. Prometheus için Yapılandırma Dosyalarını Oluşturma

Prometheus yapılandırma dosyalarını oluşturun:

```bash
# Prometheus konfigürasyon dizini oluştur
mkdir -p prometheus

# prometheus.yml dosyasını oluştur
cat > prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          # - alertmanager:9093

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'microbot'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['app:8000']
EOF

# Kurallar dizini oluştur
mkdir -p prometheus/rules

# Örnek bir alert kuralı ekle
cat > prometheus/rules/alerts.yml << 'EOF'
groups:
- name: microbot_alerts
  rules:
  - alert: HighCpuUsage
    expr: process_cpu_seconds_total{job="microbot"} > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage detected"
      description: "CPU usage is above 80% for 5 minutes on {{ $labels.instance }}"
EOF
```

## 3. Grafana için Yapılandırma

Grafana ayarları için gerekli dizinleri ve dosyaları oluşturun:

```bash
# Grafana provisioning dizinleri
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards

# Prometheus datasource yapılandırması
cat > grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    orgId: 1
    url: http://prometheus:9090
    basicAuth: false
    isDefault: true
    editable: false
EOF

# Dashboard yapılandırması
cat > grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

# Örnek bir dashboard ekle
cat > grafana/provisioning/dashboards/microbot.json << 'EOF'
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": "-- Grafana --",
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": 1,
  "links": [],
  "panels": [
    {
      "aliasColors": {},
      "bars": false,
      "dashLength": 10,
      "dashes": false,
      "datasource": "Prometheus",
      "fill": 1,
      "fillGradient": 0,
      "gridPos": {
        "h": 9,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "hiddenSeries": false,
      "id": 2,
      "legend": {
        "avg": false,
        "current": false,
        "max": false,
        "min": false,
        "show": true,
        "total": false,
        "values": false
      },
      "lines": true,
      "linewidth": 1,
      "nullPointMode": "null",
      "options": {
        "dataLinks": []
      },
      "percentage": false,
      "pointradius": 2,
      "points": false,
      "renderer": "flot",
      "seriesOverrides": [],
      "spaceLength": 10,
      "stack": false,
      "steppedLine": false,
      "targets": [
        {
          "expr": "up",
          "legendFormat": "Status",
          "refId": "A"
        }
      ],
      "thresholds": [],
      "timeFrom": null,
      "timeRegions": [],
      "timeShift": null,
      "title": "MicroBot API Status",
      "tooltip": {
        "shared": true,
        "sort": 0,
        "value_type": "individual"
      },
      "type": "graph",
      "xaxis": {
        "buckets": null,
        "mode": "time",
        "name": null,
        "show": true,
        "values": []
      },
      "yaxes": [
        {
          "format": "short",
          "label": null,
          "logBase": 1,
          "max": null,
          "min": null,
          "show": true
        },
        {
          "format": "short",
          "label": null,
          "logBase": 1,
          "max": null,
          "min": null,
          "show": true
        }
      ],
      "yaxis": {
        "align": false,
        "alignLevel": null
      }
    }
  ],
  "schemaVersion": 22,
  "style": "dark",
  "tags": [],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-6h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "MicroBot Dashboard",
  "uid": "microbot",
  "variables": {
    "list": []
  },
  "version": 1
}
EOF
```

## 4. FastAPI Uygulamasına Prometheus Metrics Ekleme

FastAPI uygulamanıza Prometheus metriklerini ekleyin. Bunun için `prometheus-fastapi-instrumentator` kütüphanesini kullanabilirsiniz.

İlk olarak, `requirements.prod.txt` dosyanıza bu kütüphaneyi ekleyin:

```bash
echo "prometheus-fastapi-instrumentator==6.1.0" >> requirements.prod.txt
```

Ardından, `app/main.py` dosyasında metrics endpoint'i ekleyin:

```python
# app/main.py dosyasına eklenecek kod (import kısmı)
from prometheus_fastapi_instrumentator import Instrumentator

# Uygulama başlangıç olayına eklenecek kod
@app.on_event("startup")
async def startup_event():
    # ... mevcut kod ...
    
    # Prometheus metrics endpoint'i ekle
    Instrumentator().instrument(app).expose(app)
    
    logger.info("Prometheus metrics endpoint'i etkinleştirildi")
```

## 5. Servisleri Çalıştırma

Tüm değişiklikleri yaptıktan sonra servisleri çalıştırın:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 6. Erişim

Aşağıdaki URL'leri kullanarak izleme arayüzlerine erişebilirsiniz:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (kullanıcı adı: admin, şifre: secure_password)

## 7. Güvenlik Önlemleri

Prometheus ve Grafana'ya erişimin güvenli olduğundan emin olun:

- İnternete açık bir ortamda bu servisleri reverse proxy arkasında çalıştırın
- Güçlü şifreler kullanın
- IP tabanlı erişim kısıtlamaları ekleyin
- SSL/TLS ile şifreleyin

```bash
# Nginx ile güvenli erişim için örnek yapılandırma
cat > nginx/monitoring.conf << 'EOF'
server {
    listen 80;
    server_name monitoring.your-domain.com;
    
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name monitoring.your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/monitoring.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/monitoring.your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://grafana:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # IP tabanlı erişim kısıtlaması
    allow 192.168.1.0/24;  # İç ağ
    allow 203.0.113.0/24;  # VPN ağı
    deny all;
}
EOF
```

## 8. Özel Metrikler Ekleme

MicroBot API'ye özel metrikler eklemek için:

```python
# app/metrics.py dosyası oluşturun
from prometheus_client import Counter, Histogram, Gauge
import time

# Telegram API çağrı sayaçları
telegram_api_calls = Counter(
    'telegram_api_calls_total', 
    'Total number of Telegram API calls',
    ['method', 'status']
)

# Mesaj gönderme süresi histogramı
message_send_duration = Histogram(
    'message_send_duration_seconds',
    'Time taken to send a message',
    ['group_type']
)

# Aktif zamanlayıcı sayısı
active_schedulers = Gauge(
    'active_schedulers',
    'Number of active schedulers',
    ['user_id']
)

# Kullanım örneği (app/services/telegram_service.py içinde)
def track_telegram_api_call(method, status):
    telegram_api_calls.labels(method=method, status=status).inc()

def track_message_send_time(group_type, func):
    start = time.time()
    result = func()
    duration = time.time() - start
    message_send_duration.labels(group_type=group_type).observe(duration)
    return result

def set_active_schedulers(user_id, count):
    active_schedulers.labels(user_id=user_id).set(count)
```

Bu yapılandırmalar ile Microbot projenizde Prometheus ve Grafana'yı kullanarak kapsamlı izleme yapabilirsiniz. 