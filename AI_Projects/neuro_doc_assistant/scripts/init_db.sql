-- Инициализация базы данных для метаданных документов
-- Этот скрипт выполняется автоматически при первом запуске PostgreSQL контейнера

-- Расширение для UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблица документов
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path VARCHAR(500) NOT NULL,
    s3_key VARCHAR(500),  -- Ключ в Object Storage
    category VARCHAR(50),  -- hr, it, compliance, onboarding
    filename VARCHAR(255) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    indexed_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    metadata JSONB,  -- Дополнительные метаданные
    embedding_mode VARCHAR(50),  -- gigachat_api, mock
    embedding_dim INTEGER  -- Размерность embeddings
);

-- Таблица чанков (связь с Qdrant)
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,  -- ID в Qdrant
    chunk_index INTEGER,  -- Порядковый номер чанка в документе
    text_preview TEXT,  -- Первые 200 символов для быстрого просмотра
    text_length INTEGER,
    embedding_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица экспериментов
CREATE TABLE IF NOT EXISTS experiments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255),
    config JSONB NOT NULL,  -- Конфигурация эксперимента (chunk_size, K, etc.)
    metrics JSONB,  -- Метрики качества (faithfulness, relevancy, precision@k)
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_indexed_at ON documents(indexed_at);
CREATE INDEX IF NOT EXISTS idx_documents_s3_key ON documents(s3_key);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_experiments_created_at ON experiments(created_at);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для автоматического обновления updated_at
CREATE TRIGGER update_documents_updated_at 
    BEFORE UPDATE ON documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

