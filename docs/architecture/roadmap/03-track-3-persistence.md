# 03 — Track 3: Persistence baseline *(приоритет №1)*

**Зависит от:** Track 2
**Разблокирует:** Track 4, 5, 8
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 3 — Persistence baseline»

## Контекст

Все фичи в ARGUS работают с одной и той же PostgreSQL-схемой, описанной в
`CLAUDE.md` → «Data Model (PostgreSQL)». Нам нужен ровно один трек, после
которого:

- работает Alembic (`alembic upgrade head` создаёт всю схему);
- есть `SqlAlchemyUnitOfWork`, реализующий порт из Track 2;
- есть базовый `SqlAlchemyDocumentRepository` — первый репозиторий, который
  будут использовать ингест и поиск.

Всё остальное (репозитории контрагентов, чанков, фактов, summary) — в
своих фича-треках, чтобы ингест и контрагенты не блокировали друг друга.

## Целевое состояние

```
backend/
├── alembic.ini
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
└── app/adapters/sqlalchemy/
    ├── __init__.py
    ├── session.py            # make_engine, make_sessionmaker
    ├── unit_of_work.py       # SqlAlchemyUnitOfWork
    ├── models.py             # ORM модели всех таблиц
    └── documents.py          # SqlAlchemyDocumentRepository
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 3.1 | SQLAlchemy session + UoW + Alembic init | `session.py`, `unit_of_work.py`, `alembic.ini`, `migrations/{env.py, script.py.mako}` |
| 3.2 | Initial migration (full schema) | `migrations/versions/0001_initial.py`, `models.py` |
| 3.3 | Document repository | `documents.py`, заглушка `features/ingest/ports.py` (только `DocumentRepository` Protocol) |

## Критерии приёмки трека

- [ ] `alembic upgrade head` создаёт все таблицы из CLAUDE.md «Data Model».
- [ ] `alembic downgrade base` чистит схему без ошибок.
- [ ] `SqlAlchemyUnitOfWork` реализует `core.ports.UnitOfWork`.
- [ ] `SqlAlchemyDocumentRepository` имеет методы `add`, `get`, `list`,
  `update_status`, `set_error`.

## Что НЕ делаем

* Не пишем репозитории контрагентов / чанков / фактов / summary — они в
  своих треках.
* Не пишем интеграционные тесты на адаптеры (post-MVP).
* Не вводим миксины soft-delete, audit, RLS — это post-MVP.
* Не подключаем pgvector — векторы лежат в Qdrant.

## Тесты

* В этом треке тестов на адаптеры нет (по конвенции). Проверка ручная:
  `alembic upgrade head` против локального Postgres.

## Verification checklist

- [ ] `alembic upgrade head`
- [ ] `psql -h localhost -U argus -d argus -c '\dt'` показывает все 6 таблиц.
- [ ] `alembic downgrade base && alembic upgrade head` идемпотентен.
- [ ] `python -c "from app.adapters.sqlalchemy.unit_of_work import
  SqlAlchemyUnitOfWork; from app.core.ports import UnitOfWork; assert
  isinstance(SqlAlchemyUnitOfWork.__init__, object)"`.

---

## Промпты для агента

### PR 3.1 — SQLAlchemy session + UoW + Alembic init

```text
Role: ты — backend-инженер проекта ARGUS, поднимаешь базовую персистентность.

# Goal
Создать в `backend/app/adapters/sqlalchemy/` фабрики async-engine и
sessionmaker, реализацию `SqlAlchemyUnitOfWork` и инициализировать Alembic
(async-шаблон) для папки `backend/migrations/`. Без миграций (миграция —
PR 3.2).

# Context
- План трека: `docs/architecture/roadmap/03-track-3-persistence.md`.
- Порт `UnitOfWork`: `app.core.ports.unit_of_work` (Track 2).
- Конфиг: `app.config.Settings.database_url` (Track 0).
- `DATABASE_URL` всегда asyncpg-схема (`postgresql+asyncpg://...`).

# Success criteria
- `session.py`:
  * `def make_engine(database_url: str) -> AsyncEngine`.
  * `def make_sessionmaker(engine: AsyncEngine) ->
    async_sessionmaker[AsyncSession]` с `expire_on_commit=False`.
- `unit_of_work.py`:
  * `class SqlAlchemyUnitOfWork:` принимает `sessionmaker` в конструктор.
  * `__aenter__` открывает сессию, экспонирует `self.session: AsyncSession`.
  * `__aexit__` при exception → rollback; затем закрывает сессию.
  * `commit()`/`rollback()` проксируют в session.
  * Проходит `isinstance(uow, UnitOfWork)` (структурно, через Protocol).
- `alembic init backend/migrations` (template `async`); `alembic.ini`
  `script_location = migrations`, `sqlalchemy.url = ` пустое (читается из
  env).
- `migrations/env.py` берёт `DATABASE_URL` из env, использует
  `make_engine`. `target_metadata = None` пока (модели появятся в PR 3.2).
- `alembic current` (с пустой БД) проходит без ошибок.

# Constraints
- Только async-варианты SQLAlchemy.
- НЕ ставить `target_metadata` сейчас.
- НЕ создавать миграционных файлов.
- НЕ использовать sync-engine даже для миграций (Alembic поддерживает async).

# Output
- Содержимое `session.py`, `unit_of_work.py`, `alembic.ini`,
  `migrations/env.py`.
- Команды и вывод: `alembic current` против локального Postgres из
  docker-compose.

# Stop rules
- Если Alembic-async-шаблон требует пакета `aiosqlite` для тестов — не
  ставь, оставь только `asyncpg` в продовых зависимостях.
```

### PR 3.2 — Initial migration (full schema)

```text
Role: ты — backend-инженер проекта ARGUS, готовишь начальную миграцию БД.

# Goal
Создать ORM-модели в `backend/app/adapters/sqlalchemy/models.py` ровно по
схеме `CLAUDE.md` → «Data Model (PostgreSQL)» и одну Alembic-миграцию
`migrations/versions/0001_initial.py`, создающую все 6 таблиц.

# Context
- План трека: `docs/architecture/roadmap/03-track-3-persistence.md`.
- Источник схемы: `CLAUDE.md` → «Data Model (PostgreSQL)».
- Engine/Alembic уже настроены в PR 3.1.
- ID-типы: `app.core.domain.ids` (Track 2).

# Success criteria
- `models.py` использует `DeclarativeBase` (SQLAlchemy 2.x).
- Таблицы: `contractors`, `contractor_raw_mappings`, `documents`,
  `document_chunks`, `extracted_fields`, `document_summaries`.
- Колонки 1-в-1 как в CLAUDE.md, типы:
  * `UUID(as_uuid=True)` для PK/FK.
  * `JSONB` для `extracted_fields.fields`.
  * `ARRAY(Text)` для `document_summaries.key_points`.
  * `TIMESTAMP(timezone=True)` для `created_at` (default `func.now()`).
  * `Text` для всех string-полей (без varchar-лимитов).
- UNIQUE-ограничения:
  * `contractors.normalized_key`.
  * `extracted_fields.document_id`.
  * `document_summaries.document_id`.
- FK с `ondelete="CASCADE"` для всех ссылок на `documents.id` и
  `contractors.id`.
- В `migrations/env.py` поставить `target_metadata = Base.metadata`.
- Миграция `0001_initial.py` создаёт все таблицы; downgrade — дропает их в
  обратном порядке.
- `alembic upgrade head` и `alembic downgrade base` идемпотентны.

# Constraints
- НЕ добавлять колонок сверх CLAUDE.md.
- НЕ использовать SQLAlchemy `Enum` для `status` — оставь `Text` (значения
  валидируются в доменном слое).
- НЕ создавать индексов кроме тех, что подразумеваются UNIQUE и PK.
  (Производительные индексы — отдельная миграция post-MVP.)

# Output
- Содержимое `models.py`, `0001_initial.py`.
- Вывод `alembic upgrade head`, `\dt` из psql, `alembic downgrade base`.

# Stop rules
- Если CLAUDE.md и какой-то существующий тест расходятся в названии колонки —
  следуй CLAUDE.md и зафиксируй разницу в Output.
```

### PR 3.3 — Document repository

```text
Role: ты — backend-инженер проекта ARGUS, добавляешь первый репозиторий —
для агрегата `Document`.

# Goal
Реализовать `SqlAlchemyDocumentRepository` в
`backend/app/adapters/sqlalchemy/documents.py` с методами `add`, `get`,
`list`, `update_status`, `set_error`. Объявить только сигнатуру
`DocumentRepository` Protocol в `backend/app/features/ingest/ports.py`
(полный список портов — Track 4).

# Context
- План трека: `docs/architecture/roadmap/03-track-3-persistence.md`.
- ORM-модель `documents` уже есть (PR 3.2).
- Доменная сущность `Document` появится в Track 4 (PR 4.1). Здесь
  репозиторий мапит между ORM и домен-сущностью «вручную»; для
  компиляции — импортируй из `app.features.ingest.entities.document` с
  оговоркой `if TYPE_CHECKING:` или объяви временный stub-dataclass.

# Success criteria
- `DocumentRepository` Protocol в `features/ingest/ports.py` с методами:
  * `async def add(self, document: Document) -> None`.
  * `async def get(self, document_id: DocumentId) -> Document`.
  * `async def list(self, *, limit: int, offset: int) -> list[Document]`.
  * `async def update_status(self, document_id: DocumentId, status: str) ->
    None`.
  * `async def set_error(self, document_id: DocumentId, message: str) ->
    None`.
- `SqlAlchemyDocumentRepository(session: AsyncSession)`:
  * хранит ссылку на сессию;
  * каждый метод — один SQL-запрос (никаких raw `.execute("SELECT ...")`,
    только Core/ORM API);
  * `get` бросает `DocumentNotFound` (определи внутри `ports.py` или
    `entities/document.py`).
- НЕ коммитит — за коммит отвечает UoW.
- ORM↔domain маппинг — отдельная private-функция `_to_entity(row) ->
  Document`.
- Если `Document` ещё не создан в Track 4 — допускается временный
  dataclass-stub в `features/ingest/entities/document.py` (минимальный
  набор полей из ORM). В Track 4 он будет расширен поведением.

# Constraints
- НЕ писать в этом PR другие репозитории.
- НЕ использовать `session.commit()` внутри методов.
- НЕ возвращать ORM-объекты наружу.

# Output
- Содержимое `documents.py`, обновлённый `ports.py`, временный
  `entities/document.py` (если применимо).
- Команда импорт-смока: `python -c "from
  app.adapters.sqlalchemy.documents import SqlAlchemyDocumentRepository"`.

# Stop rules
- Если временный stub `Document` конфликтует с дизайном Track 4 — оставь
  только обязательные поля (id, title, status) и пометь TODO-комментарием,
  что Track 4 расширит.
```
