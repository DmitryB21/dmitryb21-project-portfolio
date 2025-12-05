"""
Миграция 001: Создание таблиц для Pro-режима
Добавляет таблицы для семантического поиска, категоризации, дедупликации и аналитики
"""

import psycopg2
import os
import sys
from telegram_parser.config_utils import get_config

def create_pro_mode_tables():
    """Создание таблиц для Pro-режима"""
    config = get_config()
    
    if 'postgresql' not in config or 'dsn' not in config['postgresql']:
        print("Ошибка: В файле config.ini отсутствует секция [postgresql] или параметр dsn.")
        sys.exit(1)
    
    POSTGRES_DSN = config['postgresql']['dsn']
    
    try:
        display_dsn = POSTGRES_DSN.split('@')[1] if '@' in POSTGRES_DSN else POSTGRES_DSN
        print(f"Подключение к PostgreSQL: {display_dsn}")
        conn = psycopg2.connect(dsn=POSTGRES_DSN)
        cur = conn.cursor()
        print("Успешное подключение к PostgreSQL.")

        # 1. Таблица тем/категорий
        cur.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            synonyms TEXT[],
            parent_id INTEGER REFERENCES topics(id),
            description TEXT,
            color VARCHAR(7), -- hex color для UI
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        print("Таблица 'topics' создана или уже существует.")

        # 2. Таблица эмбеддингов (связь с Qdrant)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            model VARCHAR(100) NOT NULL, -- 'openai-text-embedding-3-large', 'bge-large', etc
            vector_id VARCHAR(255) NOT NULL, -- ID вектора в Qdrant
            embedding_dim INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(message_id, model)
        );
        """)
        print("Таблица 'embeddings' создана или уже существует.")

        # 3. Связь сообщений с темами (многозначная)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS message_topics (
            id SERIAL PRIMARY KEY,
            message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            score DECIMAL(5,4) NOT NULL DEFAULT 0.0, -- уверенность классификации 0-1
            method VARCHAR(50), -- 'ml_classifier', 'llm_zero_shot', 'manual'
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(message_id, topic_id)
        );
        """)
        print("Таблица 'message_topics' создана или уже существует.")

        # 4. Кластеры дедупликации (события)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS dedup_clusters (
            id SERIAL PRIMARY KEY,
            cluster_id VARCHAR(255) NOT NULL UNIQUE, -- UUID кластера
            title TEXT, -- заголовок события (LLM-generated)
            summary TEXT, -- краткое резюме события
            primary_topic_id INTEGER REFERENCES topics(id),
            sentiment_score DECIMAL(3,2), -- -1 to 1
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            stats JSONB DEFAULT '{}' -- количество сообщений, источников, etc
        );
        """)
        print("Таблица 'dedup_clusters' создана или уже существует.")

        # 5. Связь сообщений с кластерами дедупликации
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cluster_messages (
            id SERIAL PRIMARY KEY,
            cluster_id VARCHAR(255) NOT NULL REFERENCES dedup_clusters(cluster_id) ON DELETE CASCADE,
            message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            similarity_score DECIMAL(5,4) NOT NULL DEFAULT 0.0,
            is_primary BOOLEAN DEFAULT FALSE, -- основное сообщение кластера
            added_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(cluster_id, message_id)
        );
        """)
        print("Таблица 'cluster_messages' создана или уже существует.")

        # 6. Сохранённые поисковые запросы
        cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_searches (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255), -- для будущей мультипользовательской системы
            name VARCHAR(255) NOT NULL,
            query TEXT NOT NULL,
            filters JSONB DEFAULT '{}', -- даты, каналы, темы, тональность
            cadence VARCHAR(50), -- 'daily', 'weekly', 'manual'
            last_run_at TIMESTAMPTZ,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        print("Таблица 'saved_searches' создана или уже существует.")

        # 7. Тренды и метрики
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id SERIAL PRIMARY KEY,
            topic_id INTEGER REFERENCES topics(id),
            date DATE NOT NULL,
            period VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'monthly'
            metrics JSONB NOT NULL DEFAULT '{}', -- mentions_count, growth_rate, etc
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(topic_id, date, period)
        );
        """)
        print("Таблица 'trends' создана или уже существует.")

        # 8. Пользовательские предпочтения (онбординг)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL UNIQUE,
            selected_topics INTEGER[] DEFAULT '{}', -- массив topic_id
            seed_channels BIGINT[] DEFAULT '{}', -- массив channel_id
            blacklisted_topics INTEGER[] DEFAULT '{}', -- скрытые темы
            notification_settings JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        print("Таблица 'user_preferences' создана или уже существует.")

        # 9. Связи между темами (co-mentions)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS topic_connections (
            id SERIAL PRIMARY KEY,
            topic_a_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            topic_b_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            co_mention_count INTEGER NOT NULL DEFAULT 0,
            strength DECIMAL(5,4) NOT NULL DEFAULT 0.0, -- нормализованная сила связи
            last_calculated TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(topic_a_id, topic_b_id),
            CHECK(topic_a_id < topic_b_id) -- избегаем дублирования
        );
        """)
        print("Таблица 'topic_connections' создана или уже существует.")

        # Создание индексов для производительности
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_embeddings_message_id ON embeddings (message_id);",
            "CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings (model);",
            "CREATE INDEX IF NOT EXISTS idx_message_topics_message_id ON message_topics (message_id);",
            "CREATE INDEX IF NOT EXISTS idx_message_topics_topic_id ON message_topics (topic_id);",
            "CREATE INDEX IF NOT EXISTS idx_cluster_messages_cluster_id ON cluster_messages (cluster_id);",
            "CREATE INDEX IF NOT EXISTS idx_cluster_messages_message_id ON cluster_messages (message_id);",
            "CREATE INDEX IF NOT EXISTS idx_dedup_clusters_created_at ON dedup_clusters (created_at);",
            "CREATE INDEX IF NOT EXISTS idx_trends_date ON trends (date);",
            "CREATE INDEX IF NOT EXISTS idx_trends_topic_date ON trends (topic_id, date);",
            "CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id ON saved_searches (user_id);",
            "CREATE INDEX IF NOT EXISTS idx_topic_connections_topic_a ON topic_connections (topic_a_id);",
            "CREATE INDEX IF NOT EXISTS idx_topic_connections_topic_b ON topic_connections (topic_b_id);"
        ]

        for index_sql in indexes:
            cur.execute(index_sql)
        
        print("Индексы созданы или уже существуют.")

        # Заполнение базовых тем
        cur.execute("""
        INSERT INTO topics (name, synonyms, description, color) VALUES
        ('Политика', ARRAY['власть', 'правительство', 'выборы', 'парламент'], 'Политические новости и события', '#FF6B6B'),
        ('Экономика', ARRAY['финансы', 'бизнес', 'рынок', 'валюты'], 'Экономические новости и аналитика', '#4ECDC4'),
        ('IT', ARRAY['технологии', 'программирование', 'стартапы', 'инновации'], 'IT и технологические новости', '#45B7D1'),
        ('Искусство', ARRAY['культура', 'творчество', 'выставки', 'музеи'], 'Культурные события и искусство', '#96CEB4'),
        ('Спорт', ARRAY['футбол', 'хоккей', 'олимпиада', 'чемпионат'], 'Спортивные новости и события', '#FFEAA7'),
        ('Наука', ARRAY['исследования', 'открытия', 'медицина', 'космос'], 'Научные новости и открытия', '#DDA0DD'),
        ('Общество', ARRAY['социальные', 'общество', 'люди', 'жизнь'], 'Социальные темы и общество', '#98D8C8'),
        ('Криминал', ARRAY['преступления', 'суд', 'правоохранительные'], 'Криминальные новости', '#F7DC6F'),
        ('Международные отношения', ARRAY['дипломатия', 'международные', 'страны', 'мир'], 'Международные новости', '#BB8FCE'),
        ('Экология', ARRAY['природа', 'окружающая среда', 'климат', 'экология'], 'Экологические темы', '#85C1E9')
        ON CONFLICT (name) DO NOTHING;
        """)
        print("Базовые темы добавлены.")
        
        conn.commit()

    except Exception as e:
        print(f"Ошибка при создании таблиц Pro-режима: {e}")
        raise
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()
            print("Соединение с PostgreSQL закрыто.")

if __name__ == "__main__":
    create_pro_mode_tables()
