#!/bin/bash

# MicroBot Geliştirme Ortamı Kurulum Scripti
# Bu script, MicroBot projesinin geliştirme ortamını otomatik olarak hazırlar

set -e  # Hata durumunda scripti durdur

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}  Telegram MicroBot - Geliştirme Ortamı Kurulumu  ${NC}"
echo -e "${CYAN}================================================${NC}"

# Docker kurulumunu kontrol et
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null
then
    echo -e "${RED}Hata: Docker ve Docker Compose kurulu olmalıdır.${NC}"
    echo -e "Docker kurulum talimatları: https://docs.docker.com/get-docker/"
    echo -e "Docker Compose kurulum talimatları: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker ve Docker Compose kurulu${NC}"

# .env.dev dosyasını oluştur
if [ ! -f .env.dev ]; then
    echo -e "${YELLOW}⚠ .env.dev dosyası bulunamadı, örnek dosyadan kopyalanıyor...${NC}"
    if [ -f .env.dev.example ]; then
        cp .env.dev.example .env.dev
        echo -e "${GREEN}✓ .env.dev oluşturuldu. Lütfen içindeki değerleri düzenleyin!${NC}"
    else
        echo -e "${RED}Hata: .env.dev.example dosyası bulunamadı!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env.dev dosyası zaten mevcut${NC}"
fi

# Gerekli dizinleri oluştur
mkdir -p logs sessions

echo -e "${GREEN}✓ logs ve sessions dizinleri oluşturuldu${NC}"

# Docker imajlarını oluştur
echo -e "${YELLOW}🔄 Docker imajları oluşturuluyor...${NC}"
docker-compose -f docker-compose.dev.yml build
echo -e "${GREEN}✓ Docker imajları oluşturuldu${NC}"

# Container'ları başlat
echo -e "${YELLOW}🔄 Container'lar başlatılıyor...${NC}"
docker-compose -f docker-compose.dev.yml up -d
echo -e "${GREEN}✓ Container'lar başlatıldı${NC}"

# Veritabanı migrasyonlarını çalıştır
echo -e "${YELLOW}🔄 Veritabanı migrasyonları çalıştırılıyor...${NC}"
sleep 5  # Veritabanının başlaması için biraz bekle
docker-compose -f docker-compose.dev.yml exec app alembic upgrade head
echo -e "${GREEN}✓ Veritabanı migrasyonları tamamlandı${NC}"

# VS Code devcontainer.json dosyasını oluştur
if [ ! -f .devcontainer/devcontainer.json ]; then
    echo -e "${YELLOW}⚠ VS Code devcontainer.json dosyası bulunamadı, oluşturuluyor...${NC}"
    mkdir -p .devcontainer
    cat > .devcontainer/devcontainer.json << 'EOF'
{
    "name": "MicroBot Development",
    "dockerComposeFile": "../docker-compose.dev.yml",
    "service": "app",
    "workspaceFolder": "/microbot",
    "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-azuretools.vscode-docker",
        "cweijan.vscode-database-client2"
    ],
    "settings": {
        "python.linting.enabled": true,
        "python.linting.pylintEnabled": false,
        "python.linting.flake8Enabled": true,
        "python.formatting.provider": "black",
        "editor.formatOnSave": true,
        "python.testing.pytestEnabled": true
    }
}
EOF
    echo -e "${GREEN}✓ VS Code devcontainer.json oluşturuldu${NC}"
else
    echo -e "${GREEN}✓ VS Code devcontainer.json zaten mevcut${NC}"
fi

# Launch.json dosyasını oluştur
if [ ! -f .vscode/launch.json ]; then
    echo -e "${YELLOW}⚠ VS Code launch.json dosyası bulunamadı, oluşturuluyor...${NC}"
    mkdir -p .vscode
    cat > .vscode/launch.json << 'EOF'
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: MicroBot Remote",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "/microbot"
        }
      ]
    }
  ]
}
EOF
    echo -e "${GREEN}✓ VS Code launch.json oluşturuldu${NC}"
else
    echo -e "${GREEN}✓ VS Code launch.json zaten mevcut${NC}"
fi

# Pre-commit hook oluştur
if [ ! -f .git/hooks/pre-commit ]; then
    echo -e "${YELLOW}⚠ Git pre-commit hook bulunamadı, oluşturuluyor...${NC}"
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "🔍 Kod kalitesi kontrol ediliyor..."
docker-compose -f docker-compose.dev.yml exec -T app black --check app/
docker-compose -f docker-compose.dev.yml exec -T app isort --check app/
docker-compose -f docker-compose.dev.yml exec -T app flake8 app/
if [ $? -ne 0 ]; then
  echo "❌ Kod kalitesi kontrolü başarısız oldu. Lütfen hataları düzeltin."
  exit 1
fi
echo "✅ Kod kalitesi kontrolü başarılı."
EOF
    chmod +x .git/hooks/pre-commit
    echo -e "${GREEN}✓ Git pre-commit hook oluşturuldu${NC}"
else
    echo -e "${GREEN}✓ Git pre-commit hook zaten mevcut${NC}"
fi

echo -e "${CYAN}================================================${NC}"
echo -e "${GREEN}✓ Geliştirme ortamı kurulumu tamamlandı!${NC}"
echo -e "${CYAN}================================================${NC}"
echo -e "API: http://localhost:8000"
echo -e "Swagger: http://localhost:8000/docs"
echo -e "Adminer: http://localhost:8080"
echo -e ""
echo -e "Container loglarını görmek için:"
echo -e "  ${YELLOW}docker-compose -f docker-compose.dev.yml logs -f${NC}"
echo -e ""
echo -e "Ortamı durdurmak için:"
echo -e "  ${YELLOW}docker-compose -f docker-compose.dev.yml down${NC}"
echo -e ""
echo -e "Uygulamayı başlatmak için:"
echo -e "  ${YELLOW}python -m app.main${NC}"
echo -e ""
echo -e "Daha fazla bilgi için: ${YELLOW}docs/QUICK_START.md${NC}"
echo -e "${CYAN}================================================${NC}" 