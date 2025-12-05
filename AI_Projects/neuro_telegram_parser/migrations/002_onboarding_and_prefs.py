"""
Миграция для онбординга: таблица user_preferences и индексы
"""

import psycopg2
from telegram_parser.config_utils import get_config


def run_migration():
    config = get_config()
    dsn = config['postgresql']['dsn'] if 'postgresql' in config and 'dsn' in config['postgresql'] else None
    if not dsn:
        raise RuntimeError("PostgreSQL DSN is not configured")

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # user_preferences: хранит интересы и выбранные пользователем seed-каналы
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id VARCHAR(255) PRIMARY KEY,
            selected_topics INTEGER[] DEFAULT '{}',
            seed_channels BIGINT[] DEFAULT '{}',
            blacklisted_topics INTEGER[] DEFAULT '{}',
            notification_settings JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    # Индексы для ускорения фильтрации
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_preferences_selected_topics
            ON user_preferences USING GIN (selected_topics);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_preferences_seed_channels
            ON user_preferences USING GIN (seed_channels);
        """
    )

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    run_migration()


