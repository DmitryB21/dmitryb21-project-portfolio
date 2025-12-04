# syntax=docker/dockerfile:1.5

FROM node:20-alpine AS base

WORKDIR /app

# Установка pnpm
RUN npm install -g pnpm

# Копирование файлов зависимостей
COPY package.json pnpm-lock.yaml ./

# Установка зависимостей
RUN pnpm install --frozen-lockfile

# Копирование остальных файлов
COPY . .

EXPOSE 5173

CMD ["pnpm", "run", "dev", "--host", "0.0.0.0"]

