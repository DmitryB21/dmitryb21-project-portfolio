param(
  [string]$Python = "python"
)

# Запуск Huey worker как пакетного модуля
& $Python -m telegram_parser.huey_consumer

