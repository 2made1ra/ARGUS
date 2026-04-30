# 04 — Track 4: Ingest feature *(приоритет №2)*

**Зависит от:** Track 1, 3
**Разблокирует:** Track 5, 6, 9
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 4 — Ingest feature»

## Контекст

Ingest — стержневая фича: загрузка файла → SAGE-обработка → запись чанков,
полей и summary в БД. Lifecycle документа описан в CLAUDE.md → «Document
Status Lifecycle» (`QUEUED → PROCESSING → RESOLVING → INDEXING → INDEXED |
FAILED`).

Этот трек реализует только два первых шага lifecycle:
- `upload_document` создаёт `Document(status=QUEUED)` и ставит таск.
- `process_document` переводит в `PROCESSING`, зовёт SAGE, пишет результат и
  готовит документ к `RESOLVING`.

Сама постановка `resolve_contractor`-таска (chain) живёт в Celery-обёртке
из Track 9. Этот трек даёт чистые use case'ы и адаптеры; обёртки и HTTP —
позже.

## Целевое состояние

```
backend/app/features/ingest/
├── __init__.py
├── entities/
│   ├── __init__.py
│   └── document.py            # Document, DocumentStatus, InvalidStatusTransition
├── ports.py                   # DocumentRepository, ChunkRepository, FieldsRepository,
│                              # SummaryRepository, DocumentFileStorage,
│                              # SageProcessor, IngestionTaskQueue
└── use_cases/
    ├── __init__.py
    ├── upload_document.py     # UploadDocumentUseCase
    └── process_document.py    # ProcessDocumentUseCase

backend/app/adapters/
├── sage/
│   ├── __init__.py
│   └── processor.py           # SageProcessorAdapter
├── local_fs/
│   ├── __init__.py
│   └── file_storage.py        # LocalFileStorage
└── sqlalchemy/                # дополнительные репозитории
    ├── chunks.py
    ├── fields.py
    └── summaries.py
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 4.1 | Ingest entities & ports | `entities/document.py`, `ports.py`, тесты транзишенов |
| 4.2 | `upload_document` use case | `use_cases/upload_document.py`, тесты с in-memory fakes |
| 4.3 | `process_document` use case | `use_cases/process_document.py`, тесты |
| 4.4 | SAGE adapter, file storage, дополнительные репозитории | `adapters/sage/processor.py`, `adapters/local_fs/file_storage.py`, `adapters/sqlalchemy/{chunks,fields,summaries}.py` |

## Критерии приёмки трека

- [ ] `Document` агрегат с явными методами переходов состояний
  (`mark_processing`, `mark_resolving`, `mark_indexing`, `mark_indexed`,
  `mark_failed`).
- [ ] `UploadDocumentUseCase`: stream → save → создание Document(QUEUED) →
  add → commit → enqueue.
- [ ] `ProcessDocumentUseCase`: load → mark_processing/commit → SAGE → save
  результаты/commit → exception → mark_failed/commit/re-raise.
- [ ] Все use case'ы покрыты unit-тестами с in-memory fakes.
- [ ] Адаптеры (`SageProcessorAdapter`, `LocalFileStorage`, репозитории
  чанков/полей/summary) написаны без бизнес-логики.

## Что НЕ делаем

* Не пишем Celery-таски (Track 9).
* Не реализуем resolve / index — это Track 5 и 6.
* Не пишем HTTP-роутеры (Track 9).
* Не пишем интеграционные тесты адаптеров.

## Тесты

| Use case / модуль | Что покрыть |
|-------------------|-------------|
| `Document` | Все валидные переходы; все запрещённые → `InvalidStatusTransition`. |
| `UploadDocumentUseCase` | Порядок: `storage.save` → `repo.add` → `uow.commit` → `tasks.enqueue_process`. Возврат `DocumentId`. |
| `ProcessDocumentUseCase` | Happy path: status PROCESSING до SAGE, чанки/поля/summary сохранены, `partial_extraction` и `document_kind` обновлены. Exception path: `mark_failed(reason)` + commit + re-raise. |

## Verification checklist

- [ ] `pytest backend/tests/features/ingest -v`
- [ ] `python -c "from app.features.ingest.use_cases.upload_document import
  UploadDocumentUseCase; from app.features.ingest.use_cases.process_document
  import ProcessDocumentUseCase"`

---

## Промпты для агента

### PR 4.1 — Ingest entities & ports

```text
Role: ты — backend-инженер проекта ARGUS, формализуешь домен и порты ingest-
фичи.

# Goal
Создать `Document` агрегат с lifecycle, перечисление `DocumentStatus`,
исключение `InvalidStatusTransition` и все Protocol-порты ingest-фичи в
`backend/app/features/ingest/`.

# Context
- План трека: `docs/architecture/roadmap/04-track-4-ingest.md`.
- Lifecycle: `CLAUDE.md` → «Document Status Lifecycle».
- ID-типы: `app.core.domain.ids` (Track 2).
- В Track 3 был временный stub `Document` — расширь его до полноценного
  агрегата.

# Success criteria
- `entities/document.py`:
  * `class DocumentStatus(StrEnum)`: QUEUED, PROCESSING, RESOLVING, INDEXING,
    INDEXED, FAILED.
  * `@dataclass class Document` с полями: `id: DocumentId,
    contractor_entity_id: ContractorEntityId | None, title: str, file_path:
    str, content_type: str, document_kind: str | None, doc_type: str | None,
    status: DocumentStatus, error_message: str | None,
    partial_extraction: bool, created_at: datetime`.
  * Методы:
    `mark_processing()`, `mark_resolving()`, `mark_indexing()`,
    `mark_indexed()`, `mark_failed(message: str)`. Каждый проверяет
    допустимый предшествующий статус (см. CLAUDE.md) и при нарушении
    бросает `InvalidStatusTransition`.
- `ports.py` объявляет Protocol'ы:
  * `DocumentRepository` (расширение из Track 3 — добавь только если
    отсутствуют методы; не дублируй).
  * `ChunkRepository`: `add_many(document_id, chunks)`,
    `list_for(document_id) -> list[Chunk]` (доменный Chunk, не SAGE-Chunk —
    но можно реиспользовать SAGE-Chunk напрямую через type-alias).
  * `FieldsRepository`: `upsert(document_id, fields: ContractFields)`,
    `get(document_id) -> ContractFields | None`.
  * `SummaryRepository`: `upsert(document_id, summary: str, key_points:
    list[str])`, `get(document_id) -> tuple[str, list[str]] | None`.
  * `DocumentFileStorage`: `async save(stream: BinaryIO, filename: str) ->
    Path`.
  * `SageProcessor`: `async process(file_path: Path) -> ProcessingResult`.
  * `IngestionTaskQueue`: `async enqueue_process(document_id) -> None`,
    `async enqueue_resolve(document_id) -> None`, `async enqueue_index(
    document_id) -> None`.
- Юнит-тесты на `Document`:
  * Все валидные переходы из CLAUDE.md проходят.
  * Все запрещённые переходы (например QUEUED → INDEXED) бросают
    `InvalidStatusTransition`.
  * `mark_failed` вызывается из любого не-INDEXED состояния и
    устанавливает `error_message`.

# Constraints
- НЕ ввязывать Pydantic в доменные сущности — `dataclass` достаточно.
- НЕ привязывать к SQLAlchemy.
- НЕ объявлять методы `save` / `delete` на сущности — это работа репозитория.
- НЕ дублировать `Document` поля в `ports.py`.

# Output
- Содержимое `entities/document.py`, `ports.py`.
- Вывод `pytest backend/tests/features/ingest/entities -v`.

# Stop rules
- Если в SAGE-Chunk поля не покрывают то, что нужно записать в БД (`id`,
  `chunk_summary`) — не модифицируй модель SAGE; добавь mapping-функцию в
  адаптере репозитория (Track 4 PR 4.4).
```

### PR 4.2 — `upload_document` use case

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь use case загрузки
документа.

# Goal
Реализовать `UploadDocumentUseCase` в
`backend/app/features/ingest/use_cases/upload_document.py`. Use case
сохраняет файл, создаёт `Document(QUEUED)`, коммитит транзакцию, ставит
таск на обработку, возвращает `DocumentId`.

# Context
- План трека: `docs/architecture/roadmap/04-track-4-ingest.md`.
- Доменные сущности и порты: PR 4.1.
- UoW: `app.core.ports.unit_of_work.UnitOfWork` (Track 2).
- Конвенции: CLAUDE.md → «Development Conventions» («Use cases receive
  ports via __init__, execute via explicit method»).

# Success criteria
- Конструктор: `__init__(*, storage: DocumentFileStorage, documents:
  DocumentRepository, tasks: IngestionTaskQueue, uow: UnitOfWork)`.
- `async def execute(self, *, file: BinaryIO, filename: str, content_type:
  str) -> DocumentId`:
  1. `path = await self._storage.save(file, filename)`.
  2. Сконструировать `Document(id=new_document_id(), title=filename,
     file_path=str(path), content_type=content_type, status=QUEUED,
     error_message=None, partial_extraction=False, created_at=utcnow(),
     contractor_entity_id=None, document_kind=None, doc_type=None)`.
  3. `async with self._uow: await self._documents.add(document); await
     self._uow.commit()`.
  4. `await self._tasks.enqueue_process(document.id)`.
  5. `return document.id`.
- Юнит-тест с in-memory fakes:
  * `fake_storage` записывает в dict, возвращает Path.
  * `fake_repo` хранит в dict.
  * `fake_tasks` — список вызовов.
  * Проверяет порядок: save → add → commit → enqueue.
  * Проверяет, что enqueue вызывается ТОЛЬКО после commit.

# Constraints
- НЕ enqueue'ить таск до commit — это правило ARGUS (post-commit dispatch).
- НЕ использовать сторонние DI-фреймворки.
- НЕ принимать FastAPI `UploadFile` — use case работает с `BinaryIO`/Path.

# Output
- Содержимое `upload_document.py`, теста.
- Вывод `pytest backend/tests/features/ingest/use_cases/test_upload_document.py
  -v`.

# Stop rules
- Если интерфейс `DocumentFileStorage.save` конфликтует с тем, что
  объявлено в Track 4 PR 4.1 — синхронизируй и зафиксируй разницу.
```

### PR 4.3 — `process_document` use case

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь центральный use case
обработки документа.

# Goal
Реализовать `ProcessDocumentUseCase` в
`backend/app/features/ingest/use_cases/process_document.py`. Загружает
документ, помечает PROCESSING, зовёт SAGE, сохраняет чанки/поля/summary,
обновляет `partial_extraction` и `document_kind`. На исключении — помечает
FAILED и пробрасывает.

# Context
- План трека: `docs/architecture/roadmap/04-track-4-ingest.md`.
- Доменные сущности, порты: PR 4.1.
- SAGE: `packages/sage` (Track 1) — возвращает `ProcessingResult`.
- Use case НЕ ставит следующий таск (resolve_contractor) — это работа
  Celery-обёртки в Track 9.

# Success criteria
- Конструктор: `__init__(*, documents: DocumentRepository, chunks:
  ChunkRepository, fields: FieldsRepository, summaries: SummaryRepository,
  sage: SageProcessor, uow: UnitOfWork)`.
- `async def execute(self, document_id: DocumentId) -> None`:
  1. `async with uow:` загрузить документ, вызвать `document.mark_
     processing()`, `await self._documents.update_status(document_id,
     PROCESSING)`, `commit()`. (Это делает прогресс видимым раньше, чем
     SAGE завершится.)
  2. `result = await self._sage.process(Path(document.file_path))` —
     ВНЕ uow, чтобы транзакция не висела на время LLM/OCR.
  3. `async with uow:` сохранить chunks, fields, summary; обновить
     `document.partial_extraction = result.partial`,
     `document.document_kind = result.document_kind`; persist; commit.
  4. На любом exception в шагах 2 или 3:
     * открыть свежий uow,
     * `document.mark_failed(str(exc))`,
     * `await self._documents.set_error(document_id, str(exc))`,
     * commit,
     * re-raise.
- Юнит-тесты:
  * happy path с canned `ProcessingResult` (один chunk, fields, summary,
    partial=False) — проверяется набор вызовов на каждом fake-репозитории.
  * exception path: SAGE-fake кидает, документ помечен FAILED, exception
    пробрасывается.
  * exception path: репозиторий чанков кидает на step 3, документ FAILED.

# Constraints
- НЕ заворачивать SAGE-вызов в uow.
- НЕ глотать исключения — пробрасывать.
- НЕ ставить здесь следующий таск (resolve_contractor) — это Track 9.
- НЕ менять `error_message` если документ уже FAILED повторно — set_error
  идемпотентен по содержимому.

# Output
- Содержимое `process_document.py`, тестов.
- Вывод `pytest backend/tests/features/ingest/use_cases/test_process_document.py
  -v`.

# Stop rules
- Если SAGE возвращает `ProcessingResult` со структурой, отличной от
  ожидаемой портом `SageProcessor` — выровняй порт под SAGE и зафиксируй в
  Output.
```

### PR 4.4 — SAGE adapter, file storage, репозитории чанков/полей/summary

```text
Role: ты — backend-инженер проекта ARGUS, пишешь адаптеры для ingest-фичи.

# Goal
Реализовать:
- `SageProcessorAdapter` в `backend/app/adapters/sage/processor.py` —
  обёртка над `sage.process_document`.
- `LocalFileStorage` в `backend/app/adapters/local_fs/file_storage.py` —
  сохранение в `settings.upload_dir`.
- `SqlAlchemyChunkRepository`, `SqlAlchemyFieldsRepository`,
  `SqlAlchemySummaryRepository` в `backend/app/adapters/sqlalchemy/`.

# Context
- План трека: `docs/architecture/roadmap/04-track-4-ingest.md`.
- Порты: PR 4.1.
- ORM-модели: Track 3 PR 3.2.
- SAGE API: Track 1 PR 1.8.

# Success criteria
- `SageProcessorAdapter`:
  * Конструктор: `__init__(*, work_dir: Path, llm_client: LMStudioClient |
    None = None)`.
  * `async process(file_path)` — делегирует `sage.process_document(src=file
    _path, work_dir=self._work_dir, llm_client=self._llm_client)`.
- `LocalFileStorage`:
  * Конструктор: `__init__(base: Path)`. `base.mkdir(parents=True,
    exist_ok=True)`.
  * `async save(stream, filename) -> Path`: путь
    `base / f"{uuid4()}__{filename}"`. Запись потоковая (chunked).
  * Возвращает абсолютный Path.
- Репозитории чанков/полей/summary:
  * Все принимают `AsyncSession` в конструктор.
  * Никаких `commit()` внутри методов.
  * `SqlAlchemyChunkRepository.add_many(document_id, chunks)` — bulk
    `session.add_all(...)`.
  * `SqlAlchemyFieldsRepository.upsert` — `INSERT ... ON CONFLICT
    (document_id) DO UPDATE` через `postgresql.dialect`.
  * `SqlAlchemySummaryRepository.upsert` — аналогично.
- Никаких юнит-тестов на адаптеры в этом PR (по конвенции).

# Constraints
- НЕ копировать бизнес-логику в адаптеры.
- НЕ commit'ить в репозиториях.
- НЕ читать env напрямую — конфиг приходит через зависимости.

# Output
- Содержимое всех 5 файлов.
- Импорт-смок: `python -c "from app.adapters.sage.processor import
  SageProcessorAdapter; from app.adapters.local_fs.file_storage import
  LocalFileStorage"`.

# Stop rules
- Если SAGE-Chunk и ORM-`document_chunks` имеют расхождения в типах
  (например `chunk_summary` отсутствует в SAGE) — добавь маппинг с null-
  default'ом, не меняй SAGE-модель.
```
