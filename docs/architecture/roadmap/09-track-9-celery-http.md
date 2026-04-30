# 09 — Track 9: Celery & HTTP entrypoints *(приоритет №3)*

**Зависит от:** Track 4, 5, 6, 7, 8
**Разблокирует:** Track 10 (frontend)
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 9 — Celery & HTTP entrypoints»

## Контекст

Все use case'ы написаны и протестированы. Этот трек — связующий слой:
- Celery-app, конфиг, цепочка `process → resolve → index` через
  `apply_async`.
- FastAPI-роутеры с тонкими хендлерами поверх use case'ов.
- SSE-стрим прогресса по документу.

Celery-обёртки отвечают за:
- вызов `mark_processing`/`mark_resolving`/`mark_indexing` ДО use case'а
  (use case делает всё сам, но обёртка ставит следующий таск через
  `apply_async`);
- chain'инг через `apply_async`, без `chain()` объекта Celery (видно
  явно).

## Целевое состояние

```
backend/app/
├── celery_app.py
├── main.py                       # FastAPI app, startup hooks
├── adapters/celery/
│   ├── __init__.py
│   └── task_queue.py             # CeleryIngestionTaskQueue
└── entrypoints/
    ├── celery/
    │   ├── __init__.py
    │   ├── composition.py        # build_*_uc() — DI factories
    │   └── tasks/
    │       ├── __init__.py
    │       └── ingest.py         # process_document, resolve_contractor, index_document
    └── http/
        ├── __init__.py
        ├── dependencies.py       # FastAPI Depends factories
        ├── documents.py          # роутер
        ├── contractors.py        # роутер
        ├── search.py             # роутер
        └── streams.py            # SSE
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 9.1 | Celery app + task queue adapter | `celery_app.py`, `adapters/celery/task_queue.py` |
| 9.2 | Celery tasks (chain) | `entrypoints/celery/composition.py`, `entrypoints/celery/tasks/ingest.py` |
| 9.3 | FastAPI routers | `main.py`, `entrypoints/http/{dependencies, documents, contractors, search}.py` |
| 9.4 | SSE status stream | `entrypoints/http/streams.py` |

## Критерии приёмки трека

- [ ] `docker compose up` поднимает api+worker+postgres+redis+qdrant и
  весь happy path работает: загрузка → SAGE → resolve → index → INDEXED.
- [ ] SSE-эндпоинт отдаёт прогресс и закрывается на терминальном статусе.
- [ ] Все эндпоинты задокументированы FastAPI (OpenAPI на /docs).

## Что НЕ делаем

* Не пишем auth-middleware (post-MVP).
* Не пишем CSRF/CORS-политику строже, чем dev-режим (`http://localhost:5173`).
* Не пишем rate-limiting (post-MVP).

## Тесты

| Слой | Что покрыть |
|------|-------------|
| HTTP | Smoke на каждый роутер с моком use case'ов через `app.dependency_overrides` (один тест на эндпоинт). |
| SSE | Smoke с моком репозитория: статусы PROCESSING → INDEXED, поток закрывается. |
| Celery | Юнит-тест на `composition.build_*_uc()` (создание use case'а без падений). Real-execution — ручное smoke-тестирование. |

## Verification checklist

- [ ] `docker compose up -d`
- [ ] `curl -X POST -F "file=@sample.pdf" http://localhost:8000/documents/upload`
  возвращает 202 + `document_id`.
- [ ] `curl -N http://localhost:8000/documents/{id}/stream` показывает
  переходы статусов.
- [ ] `curl http://localhost:8000/search?q=поставщики` возвращает 200.
- [ ] `pytest backend/tests/entrypoints -v`.

---

## Промпты для агента

### PR 9.1 — Celery app + task queue adapter

```text
Role: ты — backend-инженер проекта ARGUS, поднимаешь Celery.

# Goal
Создать `backend/app/celery_app.py` с конфигом из CLAUDE.md и
`CeleryIngestionTaskQueue` в `backend/app/adapters/celery/task_queue.py`,
реализующий `IngestionTaskQueue`.

# Context
- План трека: `docs/architecture/roadmap/09-track-9-celery-http.md`.
- Конфиг Celery: `CLAUDE.md` → «Celery Setup».
- Порт `IngestionTaskQueue`: `app.features.ingest.ports`.

# Success criteria
- `celery_app.py`:
  * `celery_app = Celery("argus", broker=settings.redis_url + "/0",
    backend=settings.redis_url + "/1")`.
  * `task_serializer="json"`, `result_serializer="json"`,
    `task_acks_late=True`, `worker_prefetch_multiplier=1`.
  * `celery_app.autodiscover_tasks(["app.entrypoints.celery.tasks"])`.
- `adapters/celery/task_queue.py`:
  * `class CeleryIngestionTaskQueue:` (реализует `IngestionTaskQueue`):
    * `async enqueue_process(document_id)` →
      `celery_app.send_task("ingest.process_document",
      args=[str(document_id)])`. (Через `send_task`, не импортируя сами
      task-функции — чтобы api-контейнер не тянул pymupdf/pytesseract.)
    * Аналогично для `enqueue_resolve` и `enqueue_index`.

# Constraints
- НЕ импортировать task-функции напрямую в `task_queue.py`.
- НЕ использовать `chain()` Celery — таски будут чейниться явно через
  `apply_async` в самом таске.
- НЕ блокировать (использовать `send_task` синхронно — он быстрый и
  неблокирующий по факту, оборачивать в `asyncio.to_thread` не нужно).

# Output
- Содержимое обоих файлов.
- Импорт-смок: `python -c "from app.celery_app import celery_app; from
  app.adapters.celery.task_queue import CeleryIngestionTaskQueue"`.

# Stop rules
- Если `redis_url` в settings уже содержит `/0` — извлеки db-индекс через
  `urllib.parse` и используй как есть; не дублируй.
```

### PR 9.2 — Celery tasks (chain)

```text
Role: ты — backend-инженер проекта ARGUS, оборачиваешь use case'ы в Celery-
таски и собираешь цепочку.

# Goal
Создать `composition.py` с DI-фабриками use case'ов (для процесса worker'а)
и `tasks/ingest.py` с тремя тасками, которые явно чейнятся через
`apply_async`.

# Context
- План трека: `docs/architecture/roadmap/09-track-9-celery-http.md`.
- Порядок: `process_document → resolve_contractor → index_document`.
- Конкретный код тасков: `CLAUDE.md` → «Celery Setup» (раздел про
  `tasks/ingest.py`).

# Success criteria
- `composition.py`:
  * `build_process_uc() -> ProcessDocumentUseCase` собирает engine,
    sessionmaker, репозитории, SAGE-адаптер, UoW.
  * `build_resolve_uc() -> ResolveContractorUseCase`.
  * `build_index_uc() -> IndexDocumentUseCase`.
  * Все берут конфиг из `get_settings()`.
  * Engine/sessionmaker создаются один раз на процесс через
    `functools.lru_cache`.
- `tasks/ingest.py`:
  * `from app.celery_app import celery_app`.
  * Таски (`bind=True`, `max_retries=3`):
    ```python
    @celery_app.task(bind=True, name="ingest.process_document",
                     default_retry_delay=30)
    def process_document(self, document_id: str) -> None:
        run_async(build_process_uc().execute(DocumentId(UUID(document_id))))
        celery_app.send_task("ingest.resolve_contractor",
                             args=[document_id])

    @celery_app.task(bind=True, name="ingest.resolve_contractor",
                     default_retry_delay=30)
    def resolve_contractor(self, document_id: str) -> None:
        # обёртка ставит status=RESOLVING ДО вызова use case'а,
        # use case апдейтит contractor_entity_id и НЕ трогает status.
        run_async(_mark_status(document_id, "RESOLVING"))
        run_async(build_resolve_uc().execute(DocumentId(UUID(document_id))))
        celery_app.send_task("ingest.index_document",
                             args=[document_id])

    @celery_app.task(bind=True, name="ingest.index_document",
                     default_retry_delay=30)
    def index_document(self, document_id: str) -> None:
        run_async(build_index_uc().execute(DocumentId(UUID(document_id))))
    ```
  * `_mark_status` — приватный async-helper, обновляющий статус через
    `DocumentRepository.update_status`. (Альтернатива: пусть
    ResolveContractorUseCase сам делает mark_resolving в начале — выбери
    один путь и зафиксируй.)
  * `run_async(coro)` — обёртка `asyncio.new_event_loop().run_until_
    complete(coro)`; новый loop на каждый таск (worker — sync).
- На любом исключении внутри `execute(...)` use case уже пометил
  документ FAILED. Таск пробрасывает исключение, чтобы Celery залогировал
  и попробовал retry.

# Constraints
- НЕ запускать таски через `chain()` или `link` — только явный
  `send_task` в конце.
- НЕ использовать общий event loop между тасками — Celery worker может
  переиспользовать процесс.
- НЕ менять контракт use case'ов.

# Output
- Содержимое обоих файлов.
- Заметка о том, как валидировать локально: `celery -A app.celery_app
  worker --loglevel=info` + ручной `enqueue_process` через `python -c`.

# Stop rules
- Если `mark_resolving`/`mark_indexing` остаются ответственностью use
  case'ов (и таски только пробрасывают document_id) — это допустимая
  альтернатива; если так — убери `_mark_status` и зафиксируй причину.
```

### PR 9.3 — FastAPI routers

```text
Role: ты — backend-инженер проекта ARGUS, поднимаешь HTTP API.

# Goal
Создать FastAPI-приложение и роутеры для всех эндпоинтов MVP. Хендлеры —
тонкие: только парсинг входа, вызов use case'а, маппинг ошибок в HTTP.

# Context
- План трека: `docs/architecture/roadmap/09-track-9-celery-http.md`.
- Список эндпоинтов: `CLAUDE.md` → «API Endpoints — Ingestion + Progress»
  и «Search — Drill-down UX».

# Success criteria
- `dependencies.py`:
  * `get_settings()` (re-export).
  * `get_sessionmaker()` (lru_cache на процесс).
  * `get_uow()` per-request: `SqlAlchemyUnitOfWork(sessionmaker)`.
  * Фабрики use case'ов: `Depends`-функции, собирающие use case с теми же
    адаптерами, что и в `composition.py` для Celery.
- `documents.py` (`prefix="/documents"`):
  * `POST /upload` (`UploadFile`, `content_type` из формы) → 202 `{
    "document_id": str}`. Маппит исключения SAGE/repo на 5xx.
  * `GET /{id}` → `DocumentDTO`. 404 на `DocumentNotFound`.
  * `GET /` (query `limit, offset, status, contractor_id`) →
    `list[DocumentDTO]`.
  * `GET /{id}/facts` → `DocumentFactsDTO`.
  * `GET /{id}/search?q=` → результаты `SearchWithinDocumentUseCase`.
- `contractors.py` (`prefix="/contractors"`):
  * `GET /{id}` → профиль.
  * `GET /{id}/documents` → список документов.
  * `GET /{id}/search?q=` → результаты `SearchDocumentsUseCase`.
- `search.py` (`prefix=""`):
  * `GET /search?q=&limit=` → результаты `SearchContractorsUseCase`.
- `main.py`:
  * Создаёт `FastAPI(...)`, подключает роутеры.
  * CORS с `allow_origins=["http://localhost:5173"]`,
    `allow_methods=["*"]`, `allow_headers=["*"]`.
  * `@app.on_event("startup")` (или `lifespan`): зовёт
    `bootstrap_collection(qdrant_client, settings.qdrant_collection,
    settings.embedding_dim)`.
- Smoke-тесты с `httpx.AsyncClient` и `app.dependency_overrides` на
  каждый эндпоинт (один happy-path тест на хендлер).

# Constraints
- НЕ класть бизнес-логику в хендлеры.
- НЕ возвращать ORM-объекты — только DTO/Pydantic-модели.
- НЕ ставить prefix `/api` — фронтенд ждёт корневые пути.
- НЕ держать одну сессию на всё время запроса — `async with uow:` внутри
  use case'а.

# Output
- Содержимое всех файлов.
- Вывод `pytest backend/tests/entrypoints/http -v`.
- Команды smoke: `uvicorn app.main:app --reload` и пара `curl`'ов.

# Stop rules
- Если CORS из `*` для dev-режима не подходит (например при включённом
  `allow_credentials=True`) — задай явно `localhost:5173` без credentials
  и зафиксируй.
```

### PR 9.4 — SSE status stream

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь Server-Sent Events
для прогресса документа.

# Goal
Реализовать `GET /documents/{id}/stream` (text/event-stream): поллит
`document.status` каждую ~1с, эмитит изменения, закрывает поток на
INDEXED или FAILED.

# Context
- План трека: `docs/architecture/roadmap/09-track-9-celery-http.md`.
- Скелет: `CLAUDE.md` → «SSE handler skeleton».

# Success criteria
- `entrypoints/http/streams.py`:
  * `async def _status_stream(document_id, repo) -> AsyncIterator[str]`
    как в CLAUDE.md.
  * `@router.get("/documents/{id}/stream")` возвращает
    `StreamingResponse(_status_stream(...),
    media_type="text/event-stream")`.
- Каждое событие — формата `data: {...json...}\n\n` с полями `status`
  и `document_id`. На FAILED добавить `error_message`.
- Стрим закрывается ровно когда `status in ("INDEXED", "FAILED")`.
- Тест с фейк-репо: status переходит QUEUED → PROCESSING → INDEXED, поток
  отдаёт три события и закрывается.
- Подключить роутер в `main.py`.

# Constraints
- НЕ открывать одну долгую транзакцию на стрим — внутри `_status_stream`
  каждый цикл создаёт свежий uow и читает документ.
- НЕ использовать pub/sub Redis — простого поллинга достаточно для MVP.
- НЕ ронять весь стрим, если документ временно недоступен — лог + retry с
  паузой 1с (повторно открыть uow).

# Output
- Содержимое `streams.py`, обновлённый `main.py`.
- Вывод `pytest backend/tests/entrypoints/http/test_streams.py -v`.
- Smoke: `curl -N http://localhost:8000/documents/<uuid>/stream`.

# Stop rules
- Если из-за `expire_on_commit` сессия в стриме не видит обновлений —
  использовать `session.refresh()` или открывать новую сессию каждый
  цикл, не возиться с listener'ами.
```
