import asyncio
import asyncpg
import os
import sys
from telegram_parser.config_utils import get_config

async def main():
    # Используем функцию get_config() из config_utils.py для получения конфигурации
    config = get_config()
    
    # Проверка наличия необходимых настроек
    if 'postgresql' not in config or 'dsn' not in config['postgresql']:
        print("Ошибка: В файле config.ini отсутствует секция [postgresql] или параметр dsn.")
        print("Пожалуйста, убедитесь, что файл содержит правильные настройки.")
        sys.exit(1)
    
    POSTGRES_DSN = config['postgresql']['dsn']
    
    try:
        # Скрываем пароль при выводе строки подключения
        display_dsn = POSTGRES_DSN.split('@')[1] if '@' in POSTGRES_DSN else POSTGRES_DSN
        print(f"Подключение к PostgreSQL: {display_dsn}")
        conn = await asyncpg.connect(dsn=POSTGRES_DSN)
        print("Успешное подключение к PostgreSQL.")

        # Создание таблицы каналов
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id BIGINT PRIMARY KEY,
            name TEXT,
            description TEXT,
            username VARCHAR(255),
            last_parsed_at TIMESTAMPTZ
        );
        """)
        print("Таблица 'channels' создана или уже существует.")
        
        # Создание таблицы сообщений
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            message_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            text_content TEXT,
            published_at TIMESTAMPTZ,
            content_type VARCHAR(50),
            views_count INTEGER,
            forwards_count INTEGER,
            reactions JSONB,
            comments_count INTEGER,
            raw_message JSONB,
            UNIQUE (channel_id, message_id)
        );
        """)
        print("Таблица 'messages' создана или уже существует.")

        # Создание индексов для ускорения запросов
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages (channel_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_published_at ON messages (published_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_channels_username ON channels (username);")
        print("Индексы созданы или уже существуют.")

    except asyncpg.exceptions.ConnectionDoesNotExistError:
        print("Ошибка: Соединение с базой данных было прервано.")
        print("Проверьте, что PostgreSQL запущен и доступен по указанному адресу.")
    except asyncpg.exceptions.InvalidPasswordError:
        print("Ошибка: Неверный пароль для подключения к PostgreSQL.")
    except asyncpg.exceptions.InvalidCatalogNameError:
        print("Ошибка: Указанная база данных не существует.")
        print("Создайте базу данных или укажите существующую в config.ini")
    except Exception as e:
        print(f"Ошибка при подключении к PostgreSQL: {e}")
        print(f"Тип ошибки: {type(e).__name__}")
    finally:
        if 'conn' in locals() and conn is not None:
            await conn.close()
            print("Соединение с PostgreSQL закрыто.")

if __name__ == "__main__":
    asyncio.run(main())