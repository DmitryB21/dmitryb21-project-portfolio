# PowerShell script to start Flask app and Huey consumer in WSL
param(
    [string]$WslDistro = "Ubuntu-22.04",
    [string]$EnvPath = "~/tm-env",
    [switch]$AppOnly,
    [switch]$HueyOnly
)

$projectPathWsl = "/mnt/d/PythonProject/telegram_parser"

Write-Host "🚀 Запуск Pro Mode из WSL..." -ForegroundColor Green
Write-Host "📁 Проект: $projectPathWsl" -ForegroundColor Cyan
Write-Host "🐍 Окружение: $EnvPath" -ForegroundColor Cyan

function Start-WslProcess {
    param(
        [string]$ProcessName,
        [string]$Command,
        [string]$WslDistro,
        [string]$ProjectPath,
        [string]$EnvPath
    )
    
    # Формируем команду для выполнения в WSL
    $escapedCommand = $Command -replace '"', '\"'
    $bashArg = "cd $ProjectPath; source $EnvPath/bin/activate; echo '[$ProcessName] Окружение активировано'; echo '[$ProcessName] Запуск: $escapedCommand'; $escapedCommand"
    $bashArgEscaped = $bashArg -replace "'", "''"

    # Устанавливаем заголовок окна и запускаем команду
    $titleScript = "`$Host.UI.RawUI.WindowTitle = '$ProcessName (WSL)'"
    $fullCommand = "$titleScript; wsl -d $WslDistro bash -lc '$bashArgEscaped'"
    $scriptBlock = [scriptblock]::Create($fullCommand)
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $scriptBlock -WindowStyle Normal
}

if (-not $AppOnly -and -not $HueyOnly) {
    Write-Host "Запуск процессов в отдельных окнах PowerShell (WSL)." -ForegroundColor Yellow
    Start-WslProcess -ProcessName "APP-WSL" -Command "python -m app" -WslDistro $WslDistro -ProjectPath $projectPathWsl -EnvPath $EnvPath
    Start-Sleep -Seconds 2
    Start-WslProcess -ProcessName "HUEY-WSL" -Command "python -m huey_consumer" -WslDistro $WslDistro -ProjectPath $projectPathWsl -EnvPath $EnvPath
    Write-Host "✅ Процессы запущены в отдельных окнах." -ForegroundColor Green
} elseif ($AppOnly) {
    Write-Host "Запуск Flask приложения в отдельном окне PowerShell (WSL)." -ForegroundColor Yellow
    Start-WslProcess -ProcessName "APP-WSL" -Command "python -m app" -WslDistro $WslDistro -ProjectPath $projectPathWsl -EnvPath $EnvPath
} elseif ($HueyOnly) {
    Write-Host "Запуск Huey Consumer в отдельном окне PowerShell (WSL)." -ForegroundColor Yellow
    Start-WslProcess -ProcessName "HUEY-WSL" -Command "python -m huey_consumer" -WslDistro $WslDistro -ProjectPath $projectPathWsl -EnvPath $EnvPath
}

Write-Host ""
Write-Host "💡 Примечание: Приложение запущено из WSL для использования CUDA-ускорения llama-cpp-python" -ForegroundColor Cyan
Write-Host "💡 PostgreSQL подключение: 172.28.64.1:5432" -ForegroundColor Cyan

