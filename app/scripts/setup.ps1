# scripts/setup.ps1

Write-Host "`n▶ Yeni MicroBot kurulumu başlatılıyor..." -ForegroundColor Cyan

$clients = Get-ChildItem -Directory | Where-Object { $_.Name -like "client_*" }
$clientId = ($clients.Count + 1).ToString("000")
$folderName = "client_$clientId"

New-Item -ItemType Directory -Name $folderName
Copy-Item -Recurse -Path .\template\* -Destination .\$folderName

Set-Location $folderName

$api_id = Read-Host "API ID"
$api_hash = Read-Host "API HASH"
$phone = Read-Host "Telefon (+90...)"
$container_name = "microbot-client-$clientId"
$port = 5000 + [int]$clientId

@"
API_ID=$api_id
API_HASH=$api_hash
PHONE_NUMBER=$phone
"@ | Out-File -Encoding utf8 .env

@"
version: '3.9'
services:
  microbot:
    build: .
    container_name: $container_name
    env_file:
      - .env
    volumes:
      - ./sessions:/app/sessions
    ports:
      - '$port:80'
    restart: unless-stopped
"@ | Out-File -Encoding utf8 docker-compose.yml

docker-compose up --build -d
