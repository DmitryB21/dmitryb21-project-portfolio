param(
  [string]$Python = "python"
)

# Запуск Flask веб-приложения как пакетного модуля
& $Python -m telegram_parser.app

