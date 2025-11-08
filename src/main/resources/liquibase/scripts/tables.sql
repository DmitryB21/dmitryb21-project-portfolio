-- liquibase formatted sql

-- changeset dblyukherov:1
CREATE TABLE IF NOT EXISTS avatar(
    id              SERIAL PRIMARY KEY,
    media_type      VARCHAR(255),
    file_size       BIGINT,
    data            BYTEA
);

CREATE TABLE IF NOT EXISTS image(
    id              SERIAL PRIMARY KEY,
    media_type      VARCHAR(255),
    file_size       BIGINT,
    data            BYTEA
);

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    first_name      VARCHAR(25) NOT NULL,
    last_name       VARCHAR(25) NOT NULL,
    phone           VARCHAR(15) NOT NULL,
    password        VARCHAR(255) NOT NULL,
    role            VARCHAR(10),
    avatar_id       INTEGER REFERENCES avatar(id)

);

CREATE TABLE IF NOT EXISTS ad(
    id              SERIAL PRIMARY KEY,
    title           VARCHAR (100) NOT NULL,
    description     TEXT,
    price           INTEGER NOT NULL,
    author_id       INT REFERENCES users(id),
    image_id        INTEGER REFERENCES image(id)
);

CREATE TABLE IF NOT EXISTS comment(
    id              SERIAL PRIMARY KEY,
    created_at      BIGINT NOT NULL,
    text            TEXT NOT NULL,
    ads_id          INTEGER REFERENCES ad(id),
    author_id       INTEGER REFERENCES users(id)

);