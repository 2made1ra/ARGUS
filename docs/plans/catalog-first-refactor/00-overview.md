# Catalog-First MVP Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести ARGUS на catalog-first MVP, где `prices.csv` наполняет рабочий каталог `price_items`, основной поиск идет по новым embeddings из `embedding_text`, а пользователь работает через единый чат с брифом и найденными позициями.

**Architecture:** Новый вертикальный срез `catalog` владеет CSV-импортом, нормализацией, `embedding_text`, `price_items`, Qdrant-индексом `price_items_search_v1` и инструментом `search_items`. Новый вертикальный срез `assistant` владеет chat turn, intent router, состоянием брифа и вызовом backend tools через явные порты, не импортируя бизнес-логику `catalog` напрямую. Существующий PDF/document pipeline сохраняет lifecycle `QUEUED -> PROCESSING -> RESOLVING -> INDEXING -> INDEXED` и остается дополнительной возможностью, а извлечение каталожных строк из PDF переносится после базового CSV/search/chat MVP.

**Tech Stack:** Python 3.13+, FastAPI, SQLAlchemy 2.x async, Alembic, PostgreSQL, Qdrant, LM Studio OpenAI-compatible embeddings/chat, Pydantic v2, Celery, Redis, React 18, Vite, TypeScript.

---

## Главные Решения

- `price_items` становится основным рабочим объектом для поиска, карточек и подборок.
- `prices.csv` является главным источником наполнения MVP. PDF upload остается доступным, но не блокирует запуск catalog-first потока.
- Новые embeddings генерируются из детерминированного `embedding_text` по шаблону `prices_v1`.
- Generated vectors не хранятся в Postgres в MVP: `IndexPriceItemsUseCase` генерирует embedding и сразу upsert-ит его в Qdrant.
- Для `nomic-embed-text-v1.5` embedding input использует task prefixes: `search_document:` для строк каталога и `search_query:` для запросов.
- Статус индексации разделяет сбои генерации embedding и сбои Qdrant upsert: `embedding_failed` и `indexing_failed`.
- CSV re-import защищен от точных дублей через `file_sha256` и `row_fingerprint`.
- CSV-поле `embedding` считается legacy-вектором неизвестного происхождения. В MVP оно хранится только как raw/audit данные и не используется в пользовательском поиске.
- Qdrant collection для основного каталожного поиска: `price_items_search_v1`.
- `search_items` в MVP объединяет semantic search через Qdrant с минимальным Postgres keyword fallback по точным названиям, поставщикам, ИНН, `external_id` и `source_text`.
- Единый пользовательский интерфейс: чат, видимый "Черновик брифа" и видимые "Найденные позиции". Пользователь не выбирает между вкладками "бриф" и "поиск".
- Агент в MVP не является свободным agent framework. Это управляемый `assistant` use case: structured router, brief state, backend tools.
- Основной результат поиска - проверяемые карточки/таблица строк каталога из Postgres, а не RAG-ответ.
- Живой ответ агента нужен как объяснение, группировка, уточнение и следующий шаг, но он не заменяет найденные строки каталога.
- Итоговый бриф может быть связным prose-текстом для менеджера, но факты о ценах, поставщиках, городах, единицах и источниках должны опираться на `BriefState` и найденные `price_items`.
- Existing document search, summaries and drill-down UX остаются дополнительными сценариями и не становятся основой catalog search.

## Evidence-Backed Assistant Response Model

MVP разделяет три результата, которые не должны смешиваться в один RAG-текст:

```text
1. Поиск по базе
   -> проверяемые карточки/таблица price_items из Postgres

2. Живой ответ агента
   -> понятное объяснение, группировка, уточняющие вопросы и следующий шаг

3. Итоговый бриф мероприятия
   -> связный текст + BriefState + подтверждаемые позиции из found_items
```

Правило продукта:

- Сначала должны быть доступны явные найденные позиции с `name`, `unit_price`, `unit`, `supplier`, `supplier_city`, `category`, `source_text_snippet` и backend-generated причиной совпадения.
- Затем агент может объяснить, как эти позиции связаны с задачей пользователя.
- `message` ассистента не является источником истины для цены, поставщика, города, единицы измерения, телефона, email, ИНН или доступности на дату.
- Если в `found_items` нет подтверждающей строки, агент должен говорить как о гипотезе или отсутствии данных, а не как о факте из базы.
- RAG/document summary остается отдельным дополнительным сценарием, но не подменяет catalog search выдачу.

## Файлы Плана

- [01-data-model-and-csv-import.md](01-data-model-and-csv-import.md) - CSV-first модель данных, импорт, нормализация, `embedding_text` metadata и API каталога.
- [02-document-ingestion-to-catalog.md](02-document-ingestion-to-catalog.md) - post-MVP адаптация PDF ingestion к извлечению строк каталога без изменения lifecycle.
- [03-search-and-ui.md](03-search-and-ui.md) - единый чат, router, brief state, backend tools и frontend layout.
- [04-embeddings-and-qdrant.md](04-embeddings-and-qdrant.md) - primary new embeddings, `prices_v1`, Qdrant payload/filter contract и legacy auxiliary policy.
- [05-phased-execution.md](05-phased-execution.md) - пошаговая реализация после обновления этого плана.

## MVP Scope

### Входит

- Новый backend-срез `backend/app/features/catalog`.
- Новый backend-срез `backend/app/features/assistant`.
- Таблицы `price_imports`, `price_import_rows`, `price_items` и упрощенные CSV provenance records.
- CSV import из файлов формы `prices.csv`.
- Минимальная защита от повторных exact duplicate строк через `file_sha256`, `row_fingerprint`, `is_active` и `superseded_at`.
- Нормализация полей, нужных для поиска, фильтров и карточек.
- Детерминированный `embedding_text` `prices_v1`.
- Единый indexing flow: `embedding_text` -> new embedding -> Qdrant upsert -> `catalog_index_status`.
- Qdrant collection `price_items_search_v1`.
- `search_items`: semantic search через Qdrant, минимальный Postgres keyword fallback, hydration из Postgres, простые фильтры.
- `POST /assistant/chat`: единый chat turn с router, brief update и найденными позициями.
- Frontend первый экран: чат, черновик брифа, найденные позиции.
- Сохранение существующего PDF upload/status/drill-down document search без изменения lifecycle.

### Не входит в MVP

- Полноценный agent framework с planner/executor/memory orchestration.
- Извлечение строк каталога из PDF как обязательный путь импорта.
- Hybrid sparse+dense search внутри Qdrant.
- Named vectors для одновременного legacy/new vector spaces.
- UI для dedupe/merge строк каталога.
- Сложная история брифов и версионирование мероприятий.
- RAG-ответ как основной результат поиска.
- Генерация финального коммерческого предложения.
- Использование CSV legacy embeddings в пользовательском search path.

## Основной Поток MVP

```text
prices.csv
  -> POST /catalog/imports
  -> price_imports + price_import_rows
  -> normalize CSV-compatible fields
  -> build embedding_text with template prices_v1
  -> store price_items in Postgres
  -> generate new embeddings with configured catalog embedding model and search_document prefix
  -> validate vector dimension and upsert points into Qdrant collection price_items_search_v1
  -> mark catalog_index_status as indexed / embedding_failed / indexing_failed
  -> user talks to one assistant chat
  -> router classifies brief_discovery | supplier_search | mixed | clarification
  -> assistant updates BriefState and calls search_items when useful
  -> UI renders found item cards, assistant explanation and brief draft as separate layers
```

## Existing Document Flow

```text
PDF upload
  -> existing document pipeline
  -> existing extracted fields, chunks, summary and document Qdrant index
  -> existing contractor resolution and document drill-down search
  -> post-MVP: optional extraction of PriceItemExtraction[] into price_items
```

Rules:

- Do not change document statuses or Celery task chain during catalog MVP work.
- Do not make document chunks the primary evidence for catalog search.
- Do not block CSV import/search/chat on PDF extraction quality.

## Evidence Model

| Stage | Primary evidence | UI behavior |
| --- | --- | --- |
| MVP CSV import | `price_items` row + `price_import_rows.raw` | Open catalog item card with CSV-compatible fields and source text |
| MVP search | hydrated `price_items` rows | Show item cards/table with name, price, unit, supplier, city, source snippet and backend-generated match reason |
| MVP assistant response | `BriefState` + `found_items` | Show live explanation separately from the card/table evidence |
| Post-MVP PDF extraction | `price_items` row + document provenance | Open catalog item and optionally jump to document/page/chunk |
| Post-MVP document RAG | document chunks and summaries | Separate document search/summary flow, not main catalog result |

## Best-Practice References

- Python CSV parsing: https://docs.python.org/3/library/csv.html
- PostgreSQL bulk loading with `COPY`: https://www.postgresql.org/docs/current/sql-copy.html
- Qdrant collections: https://qdrant.tech/documentation/concepts/collections/
- Qdrant indexing: https://qdrant.tech/documentation/concepts/indexing/
- Qdrant filtered search concepts: https://qdrant.tech/documentation/concepts/filtering/
- Nomic task-prefix model card: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF
- OpenAI-compatible embeddings concepts: https://platform.openai.com/docs/guides/embeddings
- Structured outputs concepts: https://platform.openai.com/docs/guides/structured-outputs
