# 06 — Track 6: Indexing *(приоритет №2)*

**Зависит от:** Track 3, 4
**Разблокирует:** Track 7 (search), Track 9 (Celery chain)
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 6 — Indexing»

## Контекст

После того как документ обработан (PROCESSING → ...) и контрагент
сматчен (RESOLVING), все его чанки нужно проиндексировать в Qdrant
(коллекция `document_chunks`) с пэйлоадом для drill-down-поиска. Также
индексируется document-level summary как синтетический «чанк» с
`is_summary=True, chunk_index=-1`.

Embeddings считаются через LM Studio (`nomic-embed-text-v1.5`, 768 dim).

Этот трек отвечает за:
- Qdrant-адаптер (клиент, bootstrap коллекции, upsert).
- Embeddings-адаптер (LM Studio).
- Use case `IndexDocumentUseCase`, который связывает чанки → векторы →
  Qdrant и переводит документ в INDEXED.

## Целевое состояние

```
backend/app/adapters/qdrant/
├── __init__.py
├── client.py             # make_qdrant_client
├── bootstrap.py          # bootstrap_collection
└── index.py              # QdrantVectorIndex (+ VectorPoint)

backend/app/adapters/llm/
└── embeddings.py         # LMStudioEmbeddings

backend/app/features/ingest/
├── ports.py              # +VectorIndex, +EmbeddingService, +VectorPoint dataclass
└── use_cases/
    └── index_document.py # IndexDocumentUseCase
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 6.1 | Qdrant client, bootstrap, vector index | `adapters/qdrant/{client.py, bootstrap.py, index.py}`, `features/ingest/ports.py` (расширение) |
| 6.2 | LM Studio embeddings | `adapters/llm/embeddings.py`, `features/ingest/ports.py` (расширение) |
| 6.3 | `IndexDocumentUseCase` | `features/ingest/use_cases/index_document.py`, тесты |

## Критерии приёмки трека

- [ ] `bootstrap_collection` идемпотентен.
- [ ] `LMStudioEmbeddings` валидирует размерность результата против
  `settings.embedding_dim`.
- [ ] `IndexDocumentUseCase` индексирует все чанки + document summary
  одной батчевой записью в Qdrant и переводит документ в INDEXED.
- [ ] На исключении документ помечается FAILED.

## Что НЕ делаем

* Не пишем поиск (Track 7).
* Не пишем повторное индексирование (re-index) — post-MVP.
* Не подключаем pgvector / альтернативные векторные движки.
* Не делаем sparse-embeddings, hybrid search — post-MVP.

## Тесты

| Use case / модуль | Что покрыть |
|-------------------|-------------|
| `IndexDocumentUseCase` | Happy: чанки + summary упакованы в `VectorPoint[]`, embed вызван, upsert вызван, document = INDEXED. Exception: SAGE-fake кидает на embed → mark_failed. |
| `LMStudioEmbeddings` | Дим-валидация: успешные 768 → ok; 384 → `EmbeddingDimensionMismatch`. Батчинг: 100 текстов делятся на 4 запроса по 32 + 4. (С моком httpx.) |

## Verification checklist

- [ ] `pytest backend/tests/features/ingest/use_cases/test_index_document.py -v`
- [ ] `pytest backend/tests/adapters/llm/test_embeddings.py -v`
- [ ] Smoke: `python -c "import asyncio; from app.adapters.qdrant.client
  import make_qdrant_client; from app.adapters.qdrant.bootstrap import
  bootstrap_collection; ..."` (вручную против локального Qdrant).

---

## Промпты для агента

### PR 6.1 — Qdrant client, bootstrap, vector index

```text
Role: ты — backend-инженер проекта ARGUS, поднимаешь Qdrant-адаптер.

# Goal
Реализовать в `backend/app/adapters/qdrant/`:
- `make_qdrant_client(url) -> AsyncQdrantClient`.
- `bootstrap_collection(client, name, dim)` — идемпотентное создание
  коллекции `document_chunks`.
- `QdrantVectorIndex` — реализация порта `VectorIndex` (`upsert_chunks`,
  `delete_document`).
Расширить `features/ingest/ports.py` Protocol'ом `VectorIndex` и
dataclass'ом `VectorPoint`.

# Context
- План трека: `docs/architecture/roadmap/06-track-6-indexing.md`.
- Структура коллекции: `CLAUDE.md` → «Qdrant — Single Collection».
- Конфиг: `settings.qdrant_url`, `settings.qdrant_collection`,
  `settings.embedding_dim`.

# Success criteria
- `client.py`: `def make_qdrant_client(url: str) -> AsyncQdrantClient`.
- `bootstrap.py`: `async def bootstrap_collection(client:
  AsyncQdrantClient, name: str, dim: int) -> None`.
  * Если коллекция существует — return без ошибки.
  * Иначе создать с `vectors_config=VectorParams(size=dim,
    distance=Distance.COSINE)`.
- `index.py`:
  * `@dataclass class VectorPoint`: `id: UUID, vector: list[float],
    payload: dict[str, Any]`.
  * `class QdrantVectorIndex(client, collection)`:
    * `async upsert_chunks(points: list[VectorPoint])` — батчами по 256
      через `qdrant_client.models.PointStruct`.
    * `async delete_document(document_id)` — `client.delete(...)` с
      filter по payload `document_id`.
- `ports.py` расширен:
  * `class VectorIndex(Protocol):` `async upsert_chunks`, `async
    delete_document`.

# Constraints
- НЕ ходить в Qdrant в bootstrap, если коллекция уже есть нужного
  размера. Если размерность отличается — `raise QdrantSchemaMismatch`.
- НЕ заводить sparse-векторы.
- НЕ читать env напрямую.

# Output
- Содержимое всех файлов.
- Команда вручную: запустить `bootstrap_collection` против локального
  Qdrant (`docker compose up -d qdrant`) и убедиться, что повторный вызов
  не падает.

# Stop rules
- Если `qdrant_client` версии установленной в `pyproject.toml` не имеет
  `AsyncQdrantClient` — обнови минимальную версию в `backend/pyproject.toml`
  и зафиксируй.
```

### PR 6.2 — LM Studio embeddings

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь embedding-адаптер.

# Goal
Реализовать `LMStudioEmbeddings` в `backend/app/adapters/llm/embeddings.py`,
реализующий Protocol `EmbeddingService`. Считать эмбеддинги через POST
`{LM_STUDIO_URL}/embeddings` (OpenAI-совместимый endpoint), батчами по 32
текста.

# Context
- План трека: `docs/architecture/roadmap/06-track-6-indexing.md`.
- Модель: `nomic-embed-text-v1.5`. Размерность: 768.
- LM Studio URL и модель — из `settings.lm_studio_url`,
  `settings.lm_studio_embedding_model`.

# Success criteria
- `EmbeddingService` Protocol в `features/ingest/ports.py`:
  `async def embed(self, texts: list[str]) -> list[list[float]]`.
- `LMStudioEmbeddings(*, base_url: str, model: str =
  "nomic-embed-text-v1.5", batch_size: int = 32, timeout: float = 60.0)`:
  * Использует `httpx.AsyncClient`.
  * `embed(texts)` делит вход на батчи по `batch_size`, по каждому
    POST'ит `{base_url}/embeddings` тело `{"model": model, "input":
    batch}`.
  * Складывает `data[i].embedding` в порядке вызова → возвращает
    `list[list[float]]` той же длины и порядка, что и вход.
  * Валидирует, что каждое возвращённое embedding имеет
    `settings.embedding_dim` элементов; иначе `raise
    EmbeddingDimensionMismatch(actual, expected)`.
- Юнит-тесты:
  * 100 входных текстов разбиваются на 32+32+32+4; проверка через мок
    `httpx`.
  * Возврат с 384 dim → `EmbeddingDimensionMismatch`.
  * Сетевая ошибка пробрасывается.

# Constraints
- НЕ читать env напрямую внутри адаптера — только через конструктор.
- НЕ кешировать клиент глобально.
- НЕ изменять порядок текстов.

# Output
- Содержимое `embeddings.py`, обновлённый `ports.py`, тесты.
- Вывод `pytest backend/tests/adapters/llm/test_embeddings.py -v`.

# Stop rules
- Если LM Studio возвращает embedding под ключом `embedding`/`embeddings`/
  `vector` — следуй фактической схеме и зафиксируй ссылку на ответ в
  Output.
```

### PR 6.3 — `IndexDocumentUseCase`

```text
Role: ты — backend-инженер проекта ARGUS, пишешь use case индексирования
документа в Qdrant.

# Goal
Реализовать `IndexDocumentUseCase` в
`backend/app/features/ingest/use_cases/index_document.py`. Перевод
документа в INDEXING, embed чанков + summary, upsert в Qdrant, перевод в
INDEXED. Exception → FAILED.

# Context
- План трека: `docs/architecture/roadmap/06-track-6-indexing.md`.
- Адаптеры Qdrant и embeddings: PR 6.1 и 6.2.
- Структура payload'а: `CLAUDE.md` → «Qdrant — Single Collection».

# Success criteria
- Конструктор: `__init__(*, documents: DocumentRepository, chunks:
  ChunkRepository, fields: FieldsRepository, summaries: SummaryRepository,
  contractors: ContractorRepository, embeddings: EmbeddingService, index:
  VectorIndex, uow: UnitOfWork)`.
- `async def execute(self, document_id: DocumentId) -> None`:
  1. `async with uow:` загрузить документ; вызвать
     `document.mark_indexing()`; persist; commit.
  2. `async with uow:` загрузить чанки, fields, summary, contractor (если
     есть).
  3. Сформировать `VectorPoint[]`:
     * Для каждого `chunk`: payload по CLAUDE.md
       (`document_id, contractor_entity_id, doc_type, document_kind,
       date, page_start, page_end, section_type, chunk_index, text,
       is_summary=False`). `id = chunk.id`.
     * Один extra point для summary: `chunk_index = -1, is_summary =
       True, page_start = None, page_end = None, text = summary_text`.
       `id = uuid5(NAMESPACE_OID, f"{document_id}:summary")` (детерминирован).
  4. `texts = [p.payload["text"] for p in points]`,
     `vectors = await self._embeddings.embed(texts)`,
     attach `point.vector = v`.
  5. `await self._index.upsert_chunks(points)`.
  6. `async with uow:` `document.mark_indexed()`; persist; commit.
  7. Любой exception в шагах 2–6: открыть свежий uow,
     `document.mark_failed(str(exc))`, persist, commit, re-raise.
- Юнит-тесты:
  * Happy path с canned данными: 3 чанка + summary → 4 точки, embed
    вызван один раз, upsert вызван один раз, статус INDEXED.
  * Exception в embed → FAILED, исключение проброшено.

# Constraints
- НЕ embed'ить чанки и summary раздельно — один батчевый вызов.
- НЕ ставить summary с `chunk_index=0` — строго `-1`.
- НЕ хранить полный текст в payload длиннее 8000 символов — обрежь с
  `text[:8000]` чтобы payload Qdrant'а не разбухал. (Поиск по embed
  работает по вектору, не по тексту.)
- НЕ удалять старые векторы для повторного индексирования — это будет
  задачей re-index (post-MVP).

# Output
- Содержимое `index_document.py`, тестов.
- Вывод `pytest backend/tests/features/ingest/use_cases/test_index_document.py
  -v`.

# Stop rules
- Если `chunk.id` отсутствует в SAGE-Chunk (Track 1) — генерируй
  стабильный `uuid5(NAMESPACE_OID, f"{document_id}:{chunk_index}")` и
  используй его и в БД, и в Qdrant.
```
