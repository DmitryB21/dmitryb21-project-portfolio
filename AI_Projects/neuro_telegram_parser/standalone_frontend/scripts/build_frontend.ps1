$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$ProjectRoot = Join-Path $ProjectRoot ".."
$BuildDir = Join-Path $ProjectRoot "../build_frontend"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchiveName = "standalone_frontend_$Timestamp.zip"

Write-Host "==> Preparing build directory: $BuildDir"
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Write-Host "==> Copying frontend files"
Copy-Item -Recurse -Force (Join-Path $ProjectRoot "*") $BuildDir

Write-Host "==> Creating archive: $ArchiveName"
$ArchivePath = Join-Path (Split-Path $BuildDir -Parent) $ArchiveName
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }
Compress-Archive -Path (Join-Path $BuildDir "*") -DestinationPath $ArchivePath

Write-Host "==> Done"
Write-Host "Archive path: $ArchivePath"


