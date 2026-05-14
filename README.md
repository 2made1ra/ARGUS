# ARGUS

Catalog-first event-agency copilot with document intelligence as a secondary
workflow.

## Quick start

See [CLAUDE.md](CLAUDE.md) for architecture overview and development
conventions.

See [OpenAPI contract](docs/api/openapi.yaml) for the current HTTP API snapshot.

Primary catalog MVP flow:

```text
prices.csv -> price_items -> price_items_search_v1 -> unified assistant chat
```

## Packages

| Package | Path | Purpose |
|---------|------|---------|
| `argus-backend` | `backend/` | FastAPI app, Celery workers, domain logic |
| `sage` | `packages/sage/` | Stateless document processing (PDF, OCR, chunking) |

## Локальный запуск для тестирования

Требования:

- Python 3.13+ и `uv`
- Docker + Docker Compose
- Node.js 18+ для фронтенда
- LM Studio или другой локальный OpenAI-compatible сервер на
  `http://localhost:1234/v1` для catalog embeddings

```bash
uv sync
cp .env.example .env
make infra-up
make migrate
```

В `.env` укажите `LM_STUDIO_EMBEDDING_MODEL=nomic-embed-text-v1.5`. Укажите
`LM_STUDIO_LLM_MODEL`, если хотите проверять LLM-assisted интерпретацию роутера:
если chat model недоступна, ассистент откатится к детерминированному роутингу,
но catalog search всё равно требует рабочий embedding endpoint.

Запустите backend и frontend в отдельных терминалах:

```bash
make dev
```

```bash
cd frontend
npm install
npm run dev
```

Полезные локальные URL:

- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`
- Каталог: `http://localhost:5173/catalog`
- Ассистент: `http://localhost:5173/`

### Мок-режим для демо без локальной LLM

Мок-режим покрывает текущий MVP-сценарий ассистента по каталогу и обычный
поиск по каталогу. Он не требует LM Studio, не подключает Qdrant для semantic
search и не предназначен для проверки document upload/SAGE pipeline.

Поднимите инфраструктуру, примените миграции и загрузите демо-каталог из
`test_files/prices.csv`:

```bash
uv sync
cp .env.example .env
make infra-up
make migrate
make demo-seed
```

Запустите backend в мок-режиме:

```bash
ARGUS_DEMO_MODE=true make dev
```

Frontend запускается стандартно:

```bash
cd frontend
npm install
npm run dev
```

По умолчанию `make demo-seed` использует `test_files/prices.csv`. Для другого
CSV укажите путь явно:

```bash
ARGUS_DEMO_CATALOG_CSV_PATH=/absolute/path/to/prices.csv make demo-seed
ARGUS_DEMO_MODE=true ARGUS_DEMO_CATALOG_CSV_PATH=/absolute/path/to/prices.csv make dev
```

После запуска можно открыть `http://localhost:5173/` и проверить запросы вроде
`Найди радиомикрофоны в Екатеринбурге`. Ответ строится на строках
`price_items` из Postgres; мок-режим использует deterministic router и
keyword-only catalog search.

Перед ручной проверкой запустите focused checks:

```bash
uv run --project backend pytest backend/tests/entrypoints/http/test_catalog.py -v
uv run --project backend pytest backend/tests/features/catalog -v
uv run --project backend pytest backend/tests/features/assistant -v
(cd frontend && npm run build)
```

Если менялись shared contracts, persistence или frontend API layer, расширьте
проверку:

```bash
uv run --project backend pytest -v
uv run --project packages/sage pytest -v
uv run --group dev ruff check .
uv run --group dev ruff format --check .
```

## Загрузка каталога из CSV

Для ручного тестирования используйте страницу каталога:
`http://localhost:5173/catalog`. Действие `CSV import` загружает файл,
создаёт активные строки `price_items` и сразу индексирует их в Qdrant
collection `price_items_search_v1`, чтобы каталог был готов для прямого
поиска и сценариев ассистента.

Текущая реализация также оставляет раздельные API-операции:

- `POST /catalog/imports/indexed` - полный dev/test flow: import + indexing.
- `POST /catalog/imports` - только импорт CSV в Postgres без индексации.

CSV парсится как `prices_csv_v1`; таблица `price_items` в Postgres остаётся
source of truth для catalog facts. Legacy CSV `embedding` сохраняется только как
audit metadata и не используется для пользовательского поиска.

Обязательные CSV-колонки:

- `name`
- `unit`
- `unit_price`

Поддерживаемые опциональные колонки:

- `id`, `category`, `source_text`, `section`, `supplier`, `has_vat`
- `supplier_inn`, `supplier_city`, `supplier_phone`, `supplier_email`
- `supplier_status`, `embedding`

Загрузите и подготовьте файл при запущенном backend:

```bash
curl -X POST \
  -F "file=@/absolute/path/to/prices.csv;type=text/csv" \
  "http://localhost:8000/catalog/imports/indexed?index_limit=1000"
```

Ответ содержит сводку импорта и индексации; фрагмент:

```json
{
  "import": {
    "filename": "prices.csv",
    "row_count": 120,
    "valid_row_count": 118,
    "invalid_row_count": 2
  },
  "indexing": {
    "total": 118,
    "indexed": 118,
    "embedding_failed": 0,
    "indexing_failed": 0,
    "skipped": 0
  }
}
```

Проверьте через API, что активные строки появились в Postgres и получили
актуальные статусы индекса:

```bash
curl "http://localhost:8000/catalog/items?limit=5&offset=0"
```

Если используется только `POST /catalog/imports`, строки получают
`catalog_index_status=pending` и не готовы к semantic catalog search до запуска
индексации. Для тестовой загрузки предпочитайте `/catalog/imports/indexed` или
кнопку `CSV import` на странице каталога. Если CSV содержит больше строк, чем
`index_limit`, повторите подготовку с большим лимитом или добавьте отдельный
запуск индексации. Успешные строки получают `catalog_index_status=indexed`;
ошибки помечаются как `embedding_failed` или `indexing_failed`.

Для прямой проверки catalog search:

```bash
curl -X POST http://localhost:8000/catalog/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "радиомикрофоны в Екатеринбурге",
    "limit": 8,
    "filters": {
      "supplier_city": "г. Екатеринбург"
    }
  }'
```

## Сценарий агентного поиска

Unified assistant endpoint: `POST /assistant/chat`; frontend вызывает его со
страницы ассистента. Один запрос выполняет один bounded chat turn:

```text
message + brief + visible candidate context
  -> interpretation
  -> workflow policy
  -> approved backend tools
  -> response with message, ui_mode, action_plan, brief and evidence
```

Прямой поиск поставщика или услуги остаётся в `chat_search` и показывает inline
catalog cards:

```bash
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": null,
    "message": "Найди радиомикрофоны у поставщиков в Екатеринбурге",
    "brief": null,
    "recent_turns": [],
    "visible_candidates": [],
    "candidate_item_ids": []
  }'
```

Ожидаемая форма ответа:

- `ui_mode`: `chat_search`
- `router.intent`: `supplier_search`
- `action_plan.tool_intents`: содержит `search_items`
- `found_items`: catalog-backed candidate cards, hydrated from Postgres

Планирование мероприятия открывает `brief_workspace` и держит draft brief
отдельно от catalog evidence:

```bash
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": null,
    "message": "Нужно организовать корпоратив на 120 человек в Екатеринбурге, нужна площадка, свет и кейтеринг",
    "brief": null,
    "recent_turns": [],
    "visible_candidates": [],
    "candidate_item_ids": []
  }'
```

Ожидаемая форма ответа:

- `ui_mode`: `brief_workspace`
- `brief`: structured event state с извлечёнными фактами
- `found_items`: кандидаты только если policy одобрила catalog search
- `rendered_brief`: `null`, пока пользователь явно не попросит сформировать
  brief

Контекстные follow-up команды требуют явный candidate context от клиента.
Backend не резолвит фразы вроде "второй вариант" или "проверь найденных" из
скрытой server memory:

```json
{
  "message": "Проверь найденных подрядчиков",
  "visible_candidates": [
    { "ordinal": 1, "item_id": "uuid-from-found-items", "service_category": "свет" }
  ],
  "candidate_item_ids": ["uuid-from-found-items"]
}
```

Supplier verification отделена от catalog search и сейчас использует manual
`not_verified` adapter, если внешний registry adapter не настроен. `found_items`
это кандидаты; final briefs должны использовать только явно выбранные
`brief.selected_item_ids`.
