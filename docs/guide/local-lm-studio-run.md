# Локальный запуск с LM Studio

Инструкция для ручного тестирования ARGUS с локальным LM Studio.

## Что изменено для Alembic

Теперь миграции запускаются из директории `backend/` простой командой:

```bash
alembic upgrade head
```

Если работаешь через `uv`, используй:

```bash
uv run alembic upgrade head
```

Это работает потому что:

- `backend/alembic.ini` использует `script_location = %(here)s/migrations`, поэтому
  путь к миграциям считается относительно самого `alembic.ini`, а не текущей
  директории shell;
- `backend/migrations/env.py` сам читает URL базы из корневого `.env`;
- `backend/app/config.py` тоже читает корневой `.env`, поэтому API можно
  запускать и из корня проекта, и из директории `backend/`;
- для локального запуска Alembic используется `ALEMBIC_DATABASE_URL`, если он
  задан, иначе берется обычный `DATABASE_URL`;
- для миграций используется отдельная маленькая settings-модель только с
  URL базы, поэтому Alembic не требует LM Studio, Redis и Qdrant переменные просто
  для применения схемы БД.

Старые команды падали по двум причинам:

- из корня репозитория Alembic искал `migrations/` в `/ARGUS/migrations`, хотя
  реальные миграции лежат в `/ARGUS/backend/migrations`;
- после `cd backend` команда `uv run --project backend ...` указывала uv на
  несуществующий путь `backend/backend`.

## Требования

- Python 3.13+
- uv
- Docker Desktop
- Node.js и npm
- LM Studio с включенным Local Server

В LM Studio:

1. Запусти Local Server на `http://localhost:1234/v1`.
2. Загрузи embedding-модель `nomic-embed-text-v1.5`.
3. Загрузи chat-модель и укажи ее точное имя в `LM_STUDIO_LLM_MODEL`.

## .env

Создай `.env` в корне репозитория:

```bash
DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
ALEMBIC_DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_EMBEDDING_MODEL=nomic-embed-text-v1.5
LM_STUDIO_LLM_MODEL=<chat-model-name-from-lm-studio>
UPLOAD_DIR=./data/uploads
```

`.env.example` и локальный `.env` рассчитаны на запуск backend через `uv`.
Если `api` и `celery-worker` запускаются внутри Docker, `docker-compose.yml`
сам переопределяет адреса на имена сервисов docker-compose:

```bash
DATABASE_URL=postgresql+asyncpg://argus:argus@postgres:5432/argus
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
```

При этом локальный Alembic всё равно должен ходить на опубликованный порт
Postgres через `localhost`, поэтому `ALEMBIC_DATABASE_URL` оставляется в `.env`:

```bash
ALEMBIC_DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
```

Если в локальном `alembic upgrade head` появляется ошибка
`socket.gaierror: nodename nor servname provided, or not known`, почти всегда это
значит, что Alembic пытается подключиться к `postgres` как к локальному DNS-имени.
Проверь, что в `.env` задан `ALEMBIC_DATABASE_URL` с `localhost`.

Если запускаешь `api` или `celery-worker` внутри Docker, для контейнеров нужен
другой адрес LM Studio. Он уже задан в `docker-compose.yml`:

```bash
LM_STUDIO_URL=http://host.docker.internal:1234/v1
```

Для локального запуска через `uv` оставляй:

```bash
LM_STUDIO_URL=http://localhost:1234/v1
```

## Установка зависимостей

Из корня репозитория:

```bash
uv sync
```

Фронтенд:

```bash
cd frontend
npm ci
cd ..
```

## Инфраструктура

Из корня репозитория:

```bash
docker compose up -d postgres redis qdrant
```

## Миграции

Из директории `backend/`:

```bash
cd backend
uv run alembic upgrade head
cd ..
```

Если активировано окружение, где доступен `alembic`, можно короче:

```bash
cd backend
alembic upgrade head
cd ..
```

## Backend API

Из корня репозитория:

```bash
uv run --project backend uvicorn app.main:app --reload
```

Или из директории `backend/`:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

API будет доступен на:

```text
http://localhost:8000
```

## Celery Worker

В отдельном терминале, из корня репозитория:

```bash
uv run --project backend celery -A app.celery_app worker --loglevel=info
```

## Frontend

В отдельном терминале:

```bash
cd frontend
npm run dev
```

Фронтенд будет доступен на:

```text
http://localhost:5173
```

## Smoke Checks

Проверить LM Studio:

```bash
curl http://localhost:1234/v1/models
```

Проверить API:

```bash
curl http://localhost:8000/documents/?limit=1
```

Загрузить тестовый документ:

```bash
curl -F "file=@/absolute/path/to/document.pdf" \
  http://localhost:8000/documents/upload
```

Ответ содержит `document_id`. Дальше документ обрабатывается асинхронно в
Celery worker:

```text
QUEUED -> PROCESSING -> RESOLVING -> INDEXING -> INDEXED
```

Если обработка падает, сначала смотри логи API и Celery worker. Частые причины:
LM Studio server не запущен, неверно указаны имена моделей, или при запуске вне
Docker не установлены LibreOffice/Tesseract для обработки документов.

Если API падает на старте с ошибкой `Field required` для `database_url`,
`redis_url`, `qdrant_url` или `lm_studio_url`, значит приложение не прочитало
`.env`. В актуальной конфигурации backend читает `.env` из корня репозитория
абсолютным путем. Проверь, что файл действительно лежит в корне проекта, а не в
`backend/`.

Если API падает на startup с `qdrant_client... nodename nor servname provided`,
значит локально запущенный backend пытается открыть Docker hostname `qdrant`.
Для запуска через `uv` в `.env` должен быть `QDRANT_URL=http://localhost:6333`.
То же правило для Postgres и Redis: локальный backend использует `localhost`, а
контейнерный backend получает service names через `docker-compose.yml`.
