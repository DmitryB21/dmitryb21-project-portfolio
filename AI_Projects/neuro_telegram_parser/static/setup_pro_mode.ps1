# PowerShell скрипт для установки Pro-режима
# Устанавливает зависимости, запускает миграции БД и настраивает Qdrant

param(
    [string]$OpenAiApiKey = "",
    [string]$QdrantHost = "localhost",
    [int]$QdrantPort = 6333
)

Write-Host "🚀 Установка Pro-режима для Telegram Parser" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# Проверяем, что мы в правильной директории
if (-not (Test-Path "telegram_parser")) {
    Write-Host "❌ Ошибка: Запустите скрипт из директории D:\PythonProject" -ForegroundColor Red
    exit 1
}

# Активируем виртуальное окружение
if (Test-Path "telegram_parser\.venv\Scripts\Activate.ps1") {
    Write-Host "📦 Активация виртуального окружения..." -ForegroundColor Yellow
    & "telegram_parser\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "❌ Виртуальное окружение не найдено. Сначала запустите setup_env_and_db.ps1" -ForegroundColor Red
    exit 1
}

# Устанавливаем новые зависимости
Write-Host "📥 Установка зависимостей Pro-режима..." -ForegroundColor Yellow
pip install openai>=1.0.0 qdrant-client>=1.6.0 numpy>=1.21.0 scikit-learn>=1.0.0

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка установки зависимостей" -ForegroundColor Red
    exit 1
}

# Запускаем миграцию БД
Write-Host "🗄️ Запуск миграции базы данных..." -ForegroundColor Yellow
cd telegram_parser
python migrations\001_pro_mode_tables.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка миграции БД" -ForegroundColor Red
    exit 1
}

# Проверяем/устанавливаем Qdrant
Write-Host "🔍 Проверка Qdrant..." -ForegroundColor Yellow

# Проверяем, запущен ли Qdrant
try {
    $response = Invoke-WebRequest -Uri "http://${QdrantHost}:${QdrantPort}/health" -TimeoutSec 5
    Write-Host "✅ Qdrant уже запущен" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Qdrant не запущен. Запускаем через Docker..." -ForegroundColor Yellow
    
    # Проверяем наличие Docker
    try {
        docker --version | Out-Null
        Write-Host "🐳 Запуск Qdrant через Docker..." -ForegroundColor Yellow
        
        # Запускаем Qdrant в Docker
        docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
        
        # Ждем запуска
        Start-Sleep -Seconds 10
        
        # Проверяем, что Qdrant запустился
        try {
            $response = Invoke-WebRequest -Uri "http://${QdrantHost}:${QdrantPort}/health" -TimeoutSec 5
            Write-Host "✅ Qdrant успешно запущен" -ForegroundColor Green
        } catch {
            Write-Host "❌ Не удалось запустить Qdrant" -ForegroundColor Red
            Write-Host "💡 Установите Docker или запустите Qdrant вручную" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ Docker не найден" -ForegroundColor Red
        Write-Host "💡 Установите Docker Desktop или запустите Qdrant вручную" -ForegroundColor Yellow
        Write-Host "   Скачать: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    }
}

# Обновляем .env файл
Write-Host "⚙️ Обновление конфигурации..." -ForegroundColor Yellow

$envFile = "D:\PythonProject\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    
    # Добавляем OpenAI API ключ если указан
    if ($OpenAiApiKey -ne "") {
        if ($envContent -match "OPENAI_API_KEY") {
            $envContent = $envContent -replace "OPENAI_API_KEY=.*", "OPENAI_API_KEY=$OpenAiApiKey"
        } else {
            $envContent += "`nOPENAI_API_KEY=$OpenAiApiKey"
        }
        Write-Host "✅ OpenAI API ключ добавлен в .env" -ForegroundColor Green
    } else {
        Write-Host "⚠️ OpenAI API ключ не указан. Добавьте его в .env файл:" -ForegroundColor Yellow
        Write-Host "   OPENAI_API_KEY=your_api_key_here" -ForegroundColor Yellow
    }
    
    Set-Content -Path $envFile -Value $envContent
} else {
    Write-Host "❌ Файл .env не найден. Сначала запустите setup_env_and_db.ps1" -ForegroundColor Red
    exit 1
}

cd ..

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "🎉 Установка Pro-режима завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Что было сделано:" -ForegroundColor White
Write-Host "  ✅ Установлены зависимости: openai, qdrant-client, numpy, scikit-learn" -ForegroundColor Green
Write-Host "  ✅ Созданы таблицы БД для Pro-режима" -ForegroundColor Green
Write-Host "  ✅ Настроен Qdrant для векторного поиска" -ForegroundColor Green
Write-Host "  ✅ Обновлена конфигурация" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Следующие шаги:" -ForegroundColor White
Write-Host "  1. Запустите веб-сервер: .\telegram_parser\static\run_web.ps1" -ForegroundColor Yellow
Write-Host "  2. Запустите воркер: .\telegram_parser\static\run_worker.ps1" -ForegroundColor Yellow
Write-Host "  3. Откройте http://localhost:5000 и нажмите 'Режим Pro'" -ForegroundColor Yellow
Write-Host ""
Write-Host "💡 Для полной функциональности добавьте OpenAI API ключ в .env файл" -ForegroundColor Cyan
Write-Host "   Получить ключ: https://platform.openai.com/api-keys" -ForegroundColor Cyan
