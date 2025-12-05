param(
  [string]$Python = "python",
  [string]$ApiId = "",
  [string]$ApiHash = "",
  [string]$Phone = "",
  [string]$PostgresDsn = "postgresql://user:password@localhost:5432/telegram_parser_db",
  [string]$PostgresCustomerDsn = "postgresql://user:password@localhost:5432/telegram_data_customer"
)

# Определяем корни проекта
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageDir = Split-Path -Parent $scriptDir              # ...\telegram_parser
$projectRoot = Split-Path -Parent $packageDir            # ...\PythonProject

# Создание .env (в корне проекта, чтобы load_dotenv() его нашёл)
$envPath = Join-Path $projectRoot ".env"
@"
TELEGRAM_API_ID=$($ApiId.Trim())
TELEGRAM_API_HASH=$($ApiHash.Trim())
TELEGRAM_PHONE_NUMBER=$($Phone.Trim())
POSTGRES_DSN=$($PostgresDsn.Trim())
POSTGRES_CUSTOMER_DSN=$($PostgresCustomerDsn.Trim())
"@ | Out-File -Encoding UTF8 $envPath

Write-Host ".env создан: $envPath" -ForegroundColor Green

# Инициализация БД (нужно запускать из родительской для пакета директории)
$old = Get-Location
try {
  Set-Location $projectRoot
  & $Python -m telegram_parser.init_db
  # Авторизация Telegram (создаст telegram_parser.session)
  & $Python -m telegram_parser.setup_main_session
}
finally {
  Set-Location $old
}

