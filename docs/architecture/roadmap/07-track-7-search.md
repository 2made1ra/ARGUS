# 07 — Track 7: Search feature *(приоритет №3)*

**Зависит от:** Track 6 (Qdrant, embeddings)
**Разблокирует:** Track 9 (HTTP search-роутеры), Track 10 (drill-down UI)
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 7 — Search feature»

## Контекст

Drill-down search в ARGUS — три уровня:

1. **Глобально по топику** → агрегация по `contractor_entity_id`.
2. **Внутри контрагента** → агрегация по `document_id` с фильтром.
3. **Внутри документа** → плоский список чанков с фильтром.

Все три уровня — один embedding запроса + один Qdrant-поиск, отличаются
только фильтром и группировкой. Результаты обогащаются метаданными из
Postgres (имя контрагента, заголовок документа, дата).

## Целевое состояние

```
backend/app/features/search/
├── __init__.py
├── ports.py                 # VectorSearch
├── dto.py                   # SearchHit, SearchGroup, ContractorSearchResult, ...
└── use_cases/
    ├── __init__.py
    ├── search_contractors.py
    ├── search_documents.py
    └── search_within_document.py

backend/app/adapters/qdrant/
└── search.py                # QdrantVectorSearch
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 7.1 | `search_contractors` (global topic search) | `ports.py`, `dto.py`, `adapters/qdrant/search.py`, `use_cases/search_contractors.py`, тесты |
| 7.2 | `search_documents` (within contractor) | `use_cases/search_documents.py`, тесты |
| 7.3 | `search_within_document` | `use_cases/search_within_document.py`, тесты |

## Критерии приёмки трека

- [ ] `VectorSearch` Protocol покрывает `search` (с filter и group_by).
- [ ] Все три use case'а используют один и тот же embedding-вызов и один
  Qdrant-вызов.
- [ ] Метаданные (имена контрагентов, заголовки документов) подгружаются
  из Postgres.
- [ ] Тесты с фейковым `VectorSearch` проходят и проверяют формат DTO.

## Что НЕ делаем

* Не реализуем reranking, hybrid search, BM25 — это post-MVP.
* Не реализуем подсветку (highlight) на бекенде — клиент сам рендерит
  сниппеты.
* Не пишем search HTTP-роутеры (Track 9).

## Тесты

| Use case | Что покрыть |
|----------|-------------|
| `SearchContractorsUseCase` | Группа по 3 контрагентам → возвращает ContractorSearchResult, имена подгружены, top_snippet берётся от лидера группы. |
| `SearchDocumentsUseCase` | Filter `contractor_entity_id`, группировка по `document_id`, имя/дата документа подгружены. |
| `SearchWithinDocumentUseCase` | Filter `document_id`, плоский список ChunkResult с page_start/page_end. |

## Verification checklist

- [ ] `pytest backend/tests/features/search -v`
- [ ] Импорт-смок всех трёх use case'ов.

---

## Промпты для агента

### PR 7.1 — `search_contractors` (global topic search)

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь верхний уровень
drill-down-поиска (по контрагентам).

# Goal
Создать порт `VectorSearch`, DTO для результатов, реализацию
`QdrantVectorSearch` и use case `SearchContractorsUseCase`.

# Context
- План трека: `docs/architecture/roadmap/07-track-7-search.md`.
- Embeddings: `EmbeddingService` (Track 6 PR 6.2).
- Qdrant client: Track 6 PR 6.1.
- Schemа payload'а: `CLAUDE.md` → «Qdrant — Single Collection».

# Success criteria
- `dto.py`:
  * `@dataclass class SearchHit`: `id: UUID, score: float, payload: dict`.
  * `@dataclass class SearchGroup`: `group_key: str, hits: list[SearchHit]`.
  * `@dataclass class ContractorSearchResult`: `contractor_id:
    ContractorEntityId, name: str, score: float, matched_chunks_count:
    int, top_snippet: str`.
- `ports.py` (search):
  * `class VectorSearch(Protocol):`
    `async def search(self, *, query_vector: list[float], limit: int,
    filter: dict | None = None, group_by: str | None = None,
    group_size: int = 3) -> list[SearchHit] | list[SearchGroup]`.
- `adapters/qdrant/search.py`:
  * `QdrantVectorSearch(client, collection)`. Если `group_by` задан —
    использует `client.search_groups(...)`. Иначе — `client.search(...)`.
  * Конвертирует Qdrant-результаты в DTO.
- `use_cases/search_contractors.py`:
  * Конструктор: `__init__(*, embeddings: EmbeddingService, vectors:
    VectorSearch, contractors: ContractorRepository)`.
  * `async def execute(self, *, query: str, limit: int = 20) ->
    list[ContractorSearchResult]`:
    1. `[vec] = await embeddings.embed([query])`.
    2. `groups = await vectors.search(query_vector=vec, limit=200,
       group_by="contractor_entity_id", group_size=3)`.
    3. Для каждой группы: загрузить `Contractor` из репозитория, собрать
       `ContractorSearchResult` (score = max hit's score; top_snippet =
       hit.payload["text"][:240]).
    4. Вернуть верхние `limit` отсортированных по score desc.
- Юнит-тесты с fake `VectorSearch`, fake `ContractorRepository`, fake
  `EmbeddingService`.

# Constraints
- НЕ возвращать ORM-объекты в DTO.
- НЕ делать дополнительных запросов в Qdrant.
- НЕ делать N+1 на контрагентов — если в репозитории нет батчевого
  `get_many(ids)`, добавь его.

# Output
- Содержимое всех файлов.
- Вывод `pytest backend/tests/features/search/use_cases/test_search_contractors.py -v`.

# Stop rules
- Если Qdrant client не поддерживает `search_groups` в установленной
  версии — обнови минимальную версию в `pyproject.toml`.
```

### PR 7.2 — `search_documents` (within contractor)

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь второй уровень
drill-down-поиска (документы конкретного контрагента).

# Goal
Реализовать `SearchDocumentsUseCase` — фильтр по `contractor_entity_id`,
группировка по `document_id`.

# Context
- План трека: `docs/architecture/roadmap/07-track-7-search.md`.
- Порты `VectorSearch`, `EmbeddingService` уже есть (PR 7.1).
- DTO `SearchHit/SearchGroup` уже есть.

# Success criteria
- DTO `DocumentSearchResult`:
  * `document_id: DocumentId, title: str, date: str | None,
    matched_chunks: list[ChunkSnippet]`.
  * `ChunkSnippet`: `page: int | None, snippet: str, score: float`.
- `SearchDocumentsUseCase`:
  * Конструктор: `__init__(*, embeddings, vectors, documents:
    DocumentRepository)`.
  * `async def execute(self, *, contractor_entity_id: ContractorEntityId,
    query: str, limit: int = 20) -> list[DocumentSearchResult]`:
    1. embed query.
    2. `groups = await vectors.search(query_vector=vec, limit=100,
       filter={"must": [{"key": "contractor_entity_id", "match":
       {"value": str(contractor_entity_id)}}]},
       group_by="document_id", group_size=3)`.
    3. Для каждой группы: загрузить документ (`documents.get`), собрать
       `DocumentSearchResult` со списком `matched_chunks` из payload'ов
       hits (page = page_start).
    4. Вернуть top `limit` отсортированных по max score.
- Юнит-тесты с фейками.

# Constraints
- НЕ ходить в Qdrant дважды.
- НЕ скачивать чанки из Postgres — текст snippet'а берём из payload'а
  Qdrant.

# Output
- Содержимое use case'а и теста.
- Вывод `pytest backend/tests/features/search/use_cases/test_search_documents.py -v`.

# Stop rules
- Если в Postgres у `Document` нет поля `date`, используй `created_at` или
  `extracted_fields.fields["document_date"]` — выбери одно и зафиксируй.
```

### PR 7.3 — `search_within_document`

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь третий уровень
drill-down-поиска (внутри документа).

# Goal
Реализовать `SearchWithinDocumentUseCase` — плоский список чанков
конкретного документа.

# Context
- План трека: `docs/architecture/roadmap/07-track-7-search.md`.
- Порты, DTO — PR 7.1.

# Success criteria
- DTO `WithinDocumentResult`:
  * `chunk_index: int, page_start: int | None, page_end: int | None,
    section_type: str | None, snippet: str, score: float`.
- `SearchWithinDocumentUseCase`:
  * Конструктор: `__init__(*, embeddings, vectors)`.
  * `async def execute(self, *, document_id: DocumentId, query: str,
    limit: int = 20) -> list[WithinDocumentResult]`:
    1. embed query.
    2. `hits = await vectors.search(query_vector=vec, limit=limit,
       filter={"must": [{"key": "document_id", "match": {"value":
       str(document_id)}}]})`.
    3. Конвертировать в `WithinDocumentResult`. По умолчанию исключать
       `is_summary=True` (фильтр в must_not), чтобы summary-точка не
       мешалась.
- Юнит-тесты.

# Constraints
- НЕ возвращать summary-точку.
- НЕ обрезать snippet короче 240 символов.

# Output
- Содержимое use case'а и теста.
- Вывод `pytest backend/tests/features/search/use_cases/test_search_within_document.py -v`.

# Stop rules
- Никаких — простой PR.
```
