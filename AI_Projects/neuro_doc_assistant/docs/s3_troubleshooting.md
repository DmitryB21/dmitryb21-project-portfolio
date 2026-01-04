# Устранение неполадок S3 хранилища

## Проблема: "boto3 is not installed"

### Описание
При запуске индексации появляется ошибка:
```
boto3 is not installed. Install it with: pip install boto3
```

### Причины

1. **boto3 не установлен в текущем окружении Python**
2. **Используется другое окружение Python** при запуске через subprocess
3. **Виртуальное окружение не активировано**

### Решения

#### Решение 1: Установка boto3

```bash
pip install boto3
```

Или установите все зависимости из `requirements.txt`:
```bash
pip install -r requirements.txt
```

#### Решение 2: Проверка окружения Python

Убедитесь, что используется правильное окружение:

```bash
# Проверка текущего Python
python --version
which python  # Linux/Mac
where python  # Windows

# Проверка установленных пакетов
pip list | grep boto3
```

#### Решение 3: Активация виртуального окружения

Если используется виртуальное окружение:

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

Затем установите зависимости:
```bash
pip install -r requirements.txt
```

#### Решение 4: Проверка при запуске через subprocess

При запуске индексации через API (subprocess) убедитесь, что:
- Используется тот же Python интерпретатор, что и основной процесс
- Переменные окружения правильно передаются
- Все зависимости установлены в том же окружении

### Диагностика

#### Проверка установки boto3

```python
python -c "import boto3; print('boto3 version:', boto3.__version__)"
```

#### Проверка доступности S3

```python
from app.storage.s3_storage import S3DocumentStorage
s = S3DocumentStorage()
print(f'Документов в S3: {len(s.list_documents())}')
```

#### Проверка переменных окружения

```python
import os
from dotenv import load_dotenv
load_dotenv()

print('S3_ENDPOINT:', os.getenv('S3_ENDPOINT'))
print('S3_ACCESS_KEY:', 'SET' if os.getenv('S3_ACCESS_KEY') else 'NOT SET')
print('S3_SECRET_KEY:', 'SET' if os.getenv('S3_SECRET_KEY') else 'NOT SET')
print('S3_BUCKET:', os.getenv('S3_BUCKET'))
```

### Автоматическая проверка

Скрипт `run_ingestion.py` теперь автоматически:
1. Проверяет наличие boto3 перед попыткой использования S3
2. Выводит понятные сообщения об ошибках
3. Автоматически переключается на локальную файловую систему, если S3 недоступен

### Рекомендации

1. **Всегда используйте виртуальное окружение** для изоляции зависимостей
2. **Установите все зависимости** из `requirements.txt` перед запуском
3. **Проверьте переменные окружения** в `.env` файле
4. **Убедитесь, что MinIO запущен** (если используется локальный MinIO):
   ```bash
   docker ps | grep minio
   ```

### Дополнительная информация

- [Документация boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Настройка MinIO](docs/storage_quick_start.md)
- [Миграция в S3](docs/migration_summary.md)

