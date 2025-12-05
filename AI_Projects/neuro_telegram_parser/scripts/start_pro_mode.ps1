Param(
    [switch]$AppOnly,
    [switch]$HueyOnly,
    [string]$EnvPath = ".venv311"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$activatePath = Join-Path $projectRoot "$EnvPath\Scripts\Activate.ps1"

if (-not (Test-Path $activatePath)) {
    Write-Error "Не найден файл активации виртуального окружения по пути '$activatePath'. Укажи корректное окружение через параметр -EnvPath."
    exit 1
}

function Start-ProModeProcess {
    param(
        [string]$DisplayName,
        [string]$Command
    )

    $psArgs = @(
        "-NoExit",
        "-Command",
        "`$ErrorActionPreference='Stop'; Set-Location '$projectRoot'; . '$activatePath'; Write-Host '[$DisplayName] окружение активировано'; $Command"
    )

    Start-Process powershell -ArgumentList $psArgs
}

$runApp = -not $HueyOnly
$runHuey = -not $AppOnly

if (-not $runApp -and -not $runHuey) {
    Write-Host "Ничего не запущено (используй флаги -AppOnly или -HueyOnly при необходимости)."
    exit 0
}

if ($runApp) {
    Start-ProModeProcess -DisplayName "APP" -Command "python -m app"
}

if ($runHuey) {
    Start-ProModeProcess -DisplayName "HUEY" -Command "python -m huey_consumer"
}

Write-Host "Процессы запущены в отдельных окнах PowerShell."

