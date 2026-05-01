# 00 — Track 0: Foundation *(приоритет №1)*

**Зависит от:** —
**Разблокирует:** все остальные треки
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 0 — Foundation»

## Контекст

Сейчас в репо ARGUS есть только `CLAUDE.md`, `README.md` и эта папка `docs/`.
Никакого Python-кода, конфигурации Docker или окружения нет. Чтобы остальные
треки могли стартовать, нужен пустой, но связный монорепо: пакеты
`backend` и `packages/sage`, инфра-стек через `docker-compose`, конфиг через
`pydantic-settings`, плейсхолдер C4-диаграммы.

## Целевое состояние

```
ARGUS/
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── core/{__init__.py, domain/__init__.py, ports/__init__.py}
│       ├── features/{ingest,contractors,search,documents}/__init__.py
│       ├── adapters/{sqlalchemy,qdrant,celery,sage,llm}/__init__.py
│       └── entrypoints/{http,celery}/__init__.py
├── packages/
│   └── sage/
│       ├── pyproject.toml
│       └── sage/__init__.py
├── docs/architecture/
│   ├── README.md
│   └── c4-container.puml         # placeholder
├── docker-compose.yml
├── .env.example
├── .gitignore
└── .editorconfig
```

`docker-compose up postgres redis qdrant` поднимает три инфра-сервиса.
`Settings()` валидирует обязательные env-переменные при старте.

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 0.1 | Monorepo skeleton | `backend/pyproject.toml`, `packages/sage/pyproject.toml`, все `__init__.py`, `.gitignore`, `.editorconfig`, `README.md` |
| 0.2 | docker-compose stack | `docker-compose.yml`, `backend/Dockerfile`, `.env.example` |
| 0.3 | Config | `backend/app/config.py`, `backend/tests/test_config.py` |
| 0.4 | Architecture docs placeholder | `docs/architecture/c4-container.puml`, `docs/architecture/README.md` |

## Критерии приёмки трека

- [ ] `pip install -e backend && pip install -e packages/sage` работает в чистом venv.
- [ ] `python -c "import sage; from app import core, features, adapters"` не падает.
- [ ] `docker-compose up -d postgres redis qdrant` поднимает три healthy-контейнера.
- [ ] `pytest backend/tests/test_config.py` зелёный.
- [ ] `docs/architecture/c4-container.puml` существует с TODO-плейсхолдером.

## Что НЕ делаем

* Никакого бизнес-кода (моделей, портов, use case'ов, адаптеров).
* Никакой схемы БД, миграций Alembic — это Track 3.
* Никаких FastAPI-роутеров и Celery-тасков — это Track 9.
* Никаких CI-конфигов (`.github/workflows`) — это post-MVP.

## Тесты

* `backend/tests/test_config.py` — единственный тест в этом треке. Проверяет:
  * парсинг env через `monkeypatch.setenv`;
  * дефолты (`embedding_dim=768`, `qdrant_collection="document_chunks"`,
    `lm_studio_embedding_model="nomic-embed-text-v1.5"`);
  * `ValidationError` при отсутствии `DATABASE_URL` или `LM_STUDIO_URL`.

## Verification checklist

- [ ] `pip install -e backend && pip install -e packages/sage`
- [ ] `python -c "import sage; from app import core, features, adapters, entrypoints"`
- [ ] `docker compose config -q` (валиден)
- [ ] `docker compose up -d postgres redis qdrant && docker compose ps`
- [ ] `pytest backend/tests/test_config.py -v`
- [ ] `ls docs/architecture/c4-container.puml`

---

## Промпты для агента

### PR 0.1 — Monorepo skeleton

```text
Role: ты — backend-инженер проекта ARGUS, готовишь пустой монорепо для
последующей разработки.

# Goal
Создать скелет монорепозитория ARGUS: пакеты `backend` и `packages/sage`,
все пустые `__init__.py` для подпакетов из CLAUDE.md «Repository layout»,
`pyproject.toml` для обоих пакетов, корневой `.gitignore`, `.editorconfig`,
короткий `README.md`. Никакого бизнес-кода.

# Context
- Корневой план: `ARCHITECTURE_ROADMAP.md`.
- Этот трек: `docs/architecture/roadmap/00-track-0-foundation.md`.
- Структура монорепо: `CLAUDE.md` → раздел «Repository layout».
- Стек: Python 3.13+, FastAPI, Celery, SQLAlchemy 2.x async, Qdrant, Pydantic-V2

# Success criteria
- `backend/pyproject.toml` с зависимостями: fastapi, uvicorn[standard],
  sqlalchemy[asyncio], asyncpg, alembic, celery[redis], redis,
  qdrant-client, httpx, rapidfuzz, pydantic, pydantic-settings, python-multipart.
  Dev: pytest, pytest-asyncio.
- `packages/sage/pyproject.toml` с зависимостями: pymupdf, pytesseract,
  pillow, httpx, pydantic.
- Созданы пустые `__init__.py` для каждого подпакета из CLAUDE.md.
- `pip install -e backend && pip install -e packages/sage` проходит в чистом venv.
- `python -c "import sage; from app import core, features, adapters, entrypoints"` без ошибок.
- `.gitignore` покрывает Python (`__pycache__`, `.venv`, `*.egg-info`),
  `.env`, локальный `data/`.
- `README.md` ссылается на `CLAUDE.md` и `ARCHITECTURE_ROADMAP.md`.

# Constraints
- НЕ создавать никакого Python-кода кроме `__init__.py` (пустые) и
  `pyproject.toml`.
- НЕ создавать `Dockerfile`, `docker-compose.yml`, `config.py` — это PR 0.2 и 0.3.
- НЕ менять `CLAUDE.md`.
- Использовать build-system `setuptools` (или `hatchling`) — на ваше усмотрение,
  но согласованно в обоих пакетах.

# Output
В финальном ответе укажи:
- Список созданных файлов.
- Содержимое обоих `pyproject.toml`.
- Команды и их вывод: `pip install -e backend`, `pip install -e packages/sage`,
  `python -c "..."`.

# Stop rules
- Если CLAUDE.md и ARCHITECTURE_ROADMAP.md расходятся в названии папки —
  следуй CLAUDE.md и зафиксируй расхождение в Output.
- Не добавляй зависимостей, не указанных в Success criteria, без обоснования.
```

### PR 0.2 — docker-compose stack

```text
Role: ты — DevOps-инженер проекта ARGUS, разворачиваешь локальный стек.

# Goal
Создать `docker-compose.yml`, `backend/Dockerfile` и `.env.example` так,
чтобы команда `docker compose up -d postgres redis qdrant` поднимала все
три инфраструктурных сервиса healthy, а образы `api` и `celery-worker`
успешно билдились.

# Context
- План трека: `docs/architecture/roadmap/00-track-0-foundation.md`.
- Точная спецификация compose: `CLAUDE.md` → раздел «Infrastructure —
  docker-compose».
- Скелет монорепо уже создан в PR 0.1.
- Embeddings будут считаться через LM Studio (`nomic-embed-text-v1.5`).
  LM Studio запускается на хосте, не в Docker.

# Success criteria
- `docker-compose.yml` содержит сервисы `api`, `celery-worker`, `postgres:16`,
  `redis:7-alpine`, `qdrant/qdrant:latest`, named-volumes `pg_data`, `qdrant_data`,
  bind-mount `./data/uploads -> /data/uploads` для api и worker.
- `backend/Dockerfile`: base `python:3.12-slim`; устанавливает системные пакеты
  `libreoffice`, `tesseract-ocr`, `tesseract-ocr-rus`, `tesseract-ocr-eng`,
  `poppler-utils`; `pip install -e .`; `CMD` запускает `uvicorn app.main:app
  --host 0.0.0.0 --port 8000` (для api). Worker запускается через `command:`
  в compose.
- `.env.example` содержит все ключи: `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`,
  `LM_STUDIO_URL=http://host.docker.internal:1234/v1`,
  `LM_STUDIO_EMBEDDING_MODEL=nomic-embed-text-v1.5`,
  `LM_STUDIO_LLM_MODEL=` (пустой).
- `docker compose config -q` валиден.
- `docker compose up -d postgres redis qdrant` стартует три сервиса; через
  10 секунд все три имеют статус `running`.

# Constraints
- НЕ запускать LM Studio в Docker.
- Worker и api используют один и тот же образ (build context `./backend`).
- НЕ добавлять nginx, traefik, prometheus и прочее — это post-MVP.
- НЕ менять состав зависимостей `pyproject.toml` из PR 0.1.

# Output
- Полное содержимое `docker-compose.yml`, `backend/Dockerfile`, `.env.example`.
- Вывод `docker compose config -q` и `docker compose up -d postgres redis qdrant`.
- Заметки про любые системные пакеты, которые потребовались сверх ожидаемых.

# Stop rules
- Если LibreOffice/tesseract нельзя установить из стандартных репозиториев
  python:3.13-slim — остановись и опиши вариант с другим базовым образом
  (например `python:3.13-bookworm`).
- Не вшивай secret-ы в `.env.example`. Все значения — placeholder'ы.
```

### PR 0.3 — Config

```text
Role: ты — backend-инженер проекта ARGUS, настраиваешь типобезопасную
загрузку конфигурации.

# Goal
Реализовать `backend/app/config.py` с pydantic-settings и unit-тест в
`backend/tests/test_config.py`, проверяющий парсинг env и обязательные поля.

# Context
- План трека: `docs/architecture/roadmap/00-track-0-foundation.md`.
- Скелет монорепо: PR 0.1. Compose-стек: PR 0.2.
- Embeddings: `nomic-embed-text-v1.5` (768 измерений) через LM Studio.

# Success criteria
- `Settings(BaseSettings)` поля:
  * `database_url: str` — обязательно.
  * `redis_url: str` — обязательно.
  * `qdrant_url: str` — обязательно.
  * `lm_studio_url: str` — обязательно.
  * `lm_studio_embedding_model: str = "nomic-embed-text-v1.5"`.
  * `lm_studio_llm_model: str` — обязательно.
  * `upload_dir: Path = Path("/data/uploads")`.
  * `qdrant_collection: str = "document_chunks"`.
  * `embedding_dim: int = 768`.
- `model_config = SettingsConfigDict(env_file=".env", env_prefix="",
  case_sensitive=False)`.
- `get_settings() -> Settings` обёрнуто в `functools.lru_cache`.
- Тест `test_config.py` покрывает:
  * успешный парсинг с `monkeypatch.setenv` — все обязательные + проверка дефолтов;
  * `ValidationError` при отсутствии `DATABASE_URL` (и отдельно — `LM_STUDIO_URL`);
  * `lru_cache` действительно кеширует (повторный вызов возвращает тот же объект).
- `pytest backend/tests/test_config.py -v` зелёный.

# Constraints
- НЕ читать env напрямую через `os.getenv` в продовом коде — только через
  `Settings`.
- НЕ добавлять полей сверх перечисленных.
- НЕ хардкодить значения — только дефолты, перечисленные в Success criteria.

# Output
- Полное содержимое `backend/app/config.py` и `backend/tests/test_config.py`.
- Вывод `pytest backend/tests/test_config.py -v`.

# Stop rules
- Если pydantic v2 требует другого названия `SettingsConfigDict` —
  адаптируй и зафиксируй версию `pydantic-settings` в `pyproject.toml`.
- Если `lru_cache` мешает тестированию — используй `cache_clear()` в фикстуре,
  не убирай кеш.
```

### PR 0.4 — Architecture docs placeholder

```text
Role: ты — backend-инженер проекта ARGUS, готовишь точку для C4-диаграммы.

# Goal
Создать `docs/architecture/c4-container.puml` с плейсхолдером и
`docs/architecture/README.md` с инструкцией по рендерингу и ссылкой на роадмап.

# Context
- Финальный PlantUML будет вставлен пользователем в отдельном PR.
- Корневой план: `ARCHITECTURE_ROADMAP.md`.
- Папка `docs/architecture/` уже существует (создана в этом треке).

# Success criteria
- `docs/architecture/c4-container.puml` содержит однострочный комментарий-
  плейсхолдер: `' TODO: paste C4 container diagram source (see
  ARCHITECTURE_ROADMAP.md and docs/architecture/roadmap/README.md)`.
- `docs/architecture/README.md` ≤ 30 строк: инструкция `plantuml -tsvg
  c4-container.puml`, ссылка на корневой `../../ARCHITECTURE_ROADMAP.md` и
  на `roadmap/README.md`.

# Constraints
- НЕ генерировать произвольный диаграмм-код. Только плейсхолдер.
- НЕ редактировать `ARCHITECTURE_ROADMAP.md` и `CLAUDE.md`.

# Output
- Содержимое обоих файлов.

# Stop rules
- Никаких. PR тривиален.
```
