# Техническое задание: поиск по базе договоров с Entity Resolution и Drill-down UX

## 1. Назначение системы

Необходимо реализовать систему интеллектуального поиска по базе загруженных договоров и связанных документов.

Система должна позволять пользователю искать информацию не только по тексту документов, но и по извлечённым структурированным данным:

- подрядчикам;
- договорам;
- ИНН;
- датам;
- суммам;
- штрафам;
- предметам договора;
- рискам;
- другим атрибутам договора.

Ключевой пользовательский сценарий:

```text
общий тематический поиск
→ список релевантных подрядчиков
→ карточка подрядчика
→ список его договоров
→ поиск внутри договоров / конкретного договора
→ фрагменты документа с объяснением релевантности
```

Пример пользовательского запроса:

```text
поставщики фруктов с штрафами
```

Система должна вернуть не просто чанки, а структурированный результат:

```json
{
  "contractors": [
    {
      "contractor_entity_id": "c_123",
      "name": "ООО ФруктТорг",
      "contracts": ["d_789", "d_222"],
      "matched_facts": [
        "предмет: поставка фруктов",
        "штраф: 1% за просрочку"
      ]
    }
  ],
  "answer": "Найдены поставщики фруктов, у которых в договорах указаны штрафные условия.",
  "drilldown_links": {
    "contractor": "/contractors/c_123",
    "contract": "/contracts/d_789"
  }
}
```

---

## 2. Архитектурная идея

Система состоит из двух больших частей:

```text
1. Ingestion pipeline
   Загружает документы, извлекает текст, структурированные поля,
   summary, чанки, эмбеддинги и canonical contractor entities.

2. Search pipeline
   Выполняет hybrid multi-stage search:
   PostgreSQL pre-filter → Qdrant retrieval → rerank → LLM generation.
```

Ingestion должен работать асинхронно, так как обработка документов включает:

- конвертацию;
- OCR;
- LLM extraction;
- summary generation;
- embedding generation;
- entity resolution.

Поиск должен работать по уже наполненной базе и не должен повторно извлекать данные из документов.

---

## 3. Целевой стек

### Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Qdrant
RabbitMQ / другой broker для ingestion jobs
```

### Document processing

```text
LibreOffice / soffice — конвертация DOC/DOCX в PDF
PyMuPDF / pdfplumber — извлечение текста из PDF
OCR engine — обработка сканов и фотографий документов
```

### LLM / Embeddings

```text
LLM Extraction Service — извлечение структурированных полей и summary
Embedding Service — генерация embeddings для document chunks
```

Qdrant должен использоваться для vector search и payload-filtered search. Для часто используемых payload-полей рекомендуется создавать payload indexes, чтобы фильтрация была эффективнее.

---

## 4. Ingestion pipeline

### 4.1. Общий workflow загрузки документа

При загрузке документа система должна выполнить следующий pipeline:

```text
1. Пользователь загружает документ
2. Backend API создаёт ingestion job
3. Ingestion Worker забирает job
4. Если файл не PDF — Document Converter конвертирует его в PDF
5. Text Extraction Service пытается извлечь текст из PDF
6. Если PDF содержит сканы или image-only страницы — запускается OCR
7. Text Normalizer очищает и нормализует текст
8. Chunking Service разбивает текст на чанки
9. LLM Extraction Service извлекает structured fields и summaries
10. Embedding Service создаёт embeddings чанков
11. Entity Resolution Service связывает contractor_raw с canonical contractor_entity
12. PostgreSQL сохраняет документы, договоры, поля, summary, entities и ingestion metadata
13. Qdrant сохраняет chunk embeddings + payload filters
```

Извлечение данных ориентируется на подход проекта SAGE:

- конвертация DOC/DOCX в PDF через LibreOffice / `soffice`;
- определение типа PDF: текстовый слой или скан;
- извлечение текста или OCR;
- чанкирование длинных документов;
- LLM extraction по чанкам;
- merge partial results;
- Pydantic validation;
- map-reduce summarization;
- запрет на выдумывание отсутствующих значений.

Референс: [SAGE](https://github.com/2made1ra/SAGE)

---

### 4.2. Требования к загрузке документа

Система должна принимать:

```text
PDF
DOC
DOCX
```

Для каждого загруженного файла необходимо сохранить:

```text
document_id
original_filename
mime_type
file_size
upload_status
processing_status
created_at
updated_at
source_file_path / object_storage_key
converted_pdf_path / object_storage_key
```

Статусы обработки:

```text
uploaded
queued
converting
extracting_text
ocr_processing
normalizing
chunking
llm_extracting
embedding
entity_resolving
indexing
completed
failed
partial
```

---

### 4.3. Конвертация документов

Если входной файл не PDF, система должна использовать `soffice` / LibreOffice для конвертации в PDF.

```text
DOC/DOCX → PDF
```

Результат конвертации должен быть сохранён как отдельный артефакт.

Ошибки конвертации должны сохраняться в ingestion metadata:

```json
{
  "stage": "conversion",
  "error": "LibreOffice conversion failed",
  "recoverable": false
}
```

---

### 4.4. Извлечение текста

Для PDF с текстовым слоем система должна извлекать текст постранично.

Минимальный результат:

```json
{
  "document_id": "doc_123",
  "pages": [
    {
      "page_number": 1,
      "text": "..."
    }
  ]
}
```

Если страница не содержит достаточного количества текстовых символов или классифицируется как image-only, она должна быть отправлена в OCR.

---

### 4.5. OCR

OCR должен запускаться:

```text
- для полностью отсканированных PDF
- для отдельных image-only страниц
- для фотографий документов внутри PDF
```

После OCR результат должен быть приведён к тому же формату, что и обычный text extraction:

```json
{
  "page_number": 3,
  "text": "...",
  "extraction_method": "ocr"
}
```

---

### 4.6. Нормализация текста

Text Normalizer должен:

```text
- удалять мусорные пробелы
- нормализовать переносы строк
- сохранять структуру документа там, где это возможно
- приводить OCR-артефакты к читаемому виду
- не удалять юридически значимые данные: суммы, даты, номера, ИНН, КПП, БИК, счета
```

---

### 4.7. Чанкирование

Chunking Service должен разбивать документ на логические чанки.

Основные стратегии:

```text
1. По страницам
2. По заголовкам и разделам
3. По смысловым границам
4. По таблицам, если таблица выделяется отдельно
```

Каждый chunk должен иметь metadata:

```json
{
  "chunk_id": "chunk_123",
  "document_id": "doc_123",
  "contract_id": "contract_456",
  "page_start": 1,
  "page_end": 2,
  "chunk_index": 0,
  "chunk_type": "body",
  "text": "...",
  "normalized_text": "..."
}
```

Допустимые `chunk_type`:

```text
body
table
header
footer
summary
clause
unknown
```

---

## 5. LLM extraction

### 5.1. Назначение

LLM Extraction Service должен извлекать из договора:

- структурированные поля;
- summary чанков;
- итоговое summary документа.

Extraction выполняется через LLM с жёсткой Pydantic-схемой, JSON validation, retry/fallback-логикой и правилом не выдумывать отсутствующие значения.

---

### 5.2. Минимальный набор извлекаемых полей

Базовый набор можно взять из SAGE:

```text
document_type
document_number
document_date
supplier_name
customer_name
service_date
amount
vat
valid_until
supplier_inn
supplier_kpp
supplier_bik
supplier_account
customer_inn
customer_kpp
customer_bik
customer_account
summary
```

Поля должны быть опциональными: если значение отсутствует в документе, модель не должна его придумывать.

Для сценария поиска по подрядчикам и договорам набор стоит расширить.

Дополнительные поля:

```text
contract_subject
goods_or_services
penalties
payment_terms
delivery_terms
termination_terms
risk_factors
responsibilities
contract_price
currency
start_date
end_date
contract_status
source_pages
confidence
```

---

### 5.3. Формат результата extraction

```json
{
  "contract_id": "contract_456",
  "document_id": "doc_123",
  "fields": {
    "document_type": "Договор поставки",
    "document_number": "45/2024",
    "document_date": "2024-03-15",
    "supplier_name": "ООО ФруктТорг",
    "supplier_inn": "7700000000",
    "customer_name": "ООО Покупатель",
    "contract_subject": "Поставка фруктов",
    "penalties": "1% за каждый день просрочки",
    "amount": "1 500 000 RUB"
  },
  "summary": "Договор поставки фруктов между ООО ФруктТорг и ООО Покупатель...",
  "chunk_summaries": [
    {
      "chunk_id": "chunk_1",
      "summary": "Раздел описывает предмет договора и поставку фруктов."
    }
  ],
  "partial": false,
  "confidence": 0.87
}
```

---

## 6. Entity Resolution

### 6.1. Назначение

Entity Resolution Service должен связывать разные написания одного подрядчика с единой canonical entity.

Пример:

```text
ООО "ФруктТорг"
ООО ФРУКТТОРГ
ФруктТорг, общество с ограниченной ответственностью
ИНН 7700000000
```

должны быть связаны с:

```json
{
  "contractor_entity_id": "c_123",
  "canonical_name": "ООО ФруктТорг",
  "inn": "7700000000"
}
```

---

### 6.2. Правила разрешения сущностей

Приоритет matching:

```text
1. ИНН
2. ИНН + КПП
3. Нормализованное название
4. Fuzzy matching названия
5. LLM/entity matching только как fallback
6. Ручное подтверждение для сомнительных случаев
```

---

### 6.3. Confidence entity resolution

Каждой связи нужно присваивать confidence:

```json
{
  "contractor_raw": "ФруктТорг ООО",
  "contractor_entity_id": "c_123",
  "match_method": "inn",
  "confidence": 1.0
}
```

Пример уровней:

```text
1.0 — точное совпадение по ИНН
0.9 — ИНН + похожее имя
0.75 — fuzzy name match
0.5 — LLM suggestion
<0.5 — требуется ручная проверка
```

---

## 7. Хранение данных

### 7.1. PostgreSQL

PostgreSQL является основным источником истины для:

```text
документов
договоров
извлечённых полей
summary
подрядчиков
связей подрядчик-договор
processing status
metadata
```

---

### 7.2. Основные таблицы

#### `documents`

```sql
documents (
    id uuid primary key,
    original_filename text not null,
    mime_type text,
    file_size bigint,
    source_file_path text,
    converted_pdf_path text,
    page_count int,
    extraction_method text,
    processing_status text not null,
    error_message text,
    created_at timestamptz not null,
    updated_at timestamptz not null
)
```

#### `contracts`

```sql
contracts (
    id uuid primary key,
    document_id uuid references documents(id),
    contractor_entity_id uuid references contractor_entities(id),
    document_type text,
    document_number text,
    document_date date,
    contract_subject text,
    amount numeric,
    currency text,
    valid_from date,
    valid_until date,
    summary text,
    fields jsonb,
    partial boolean default false,
    confidence numeric,
    created_at timestamptz not null,
    updated_at timestamptz not null
)
```

#### `contractor_entities`

```sql
contractor_entities (
    id uuid primary key,
    canonical_name text not null,
    inn text,
    kpp text,
    normalized_name text,
    entity_type text,
    created_at timestamptz not null,
    updated_at timestamptz not null
)
```

#### `contractor_aliases`

```sql
contractor_aliases (
    id uuid primary key,
    contractor_entity_id uuid references contractor_entities(id),
    raw_name text not null,
    normalized_name text,
    source_contract_id uuid references contracts(id),
    match_method text,
    confidence numeric,
    created_at timestamptz not null
)
```

#### `contract_chunks`

```sql
contract_chunks (
    id uuid primary key,
    document_id uuid references documents(id),
    contract_id uuid references contracts(id),
    contractor_entity_id uuid references contractor_entities(id),
    chunk_index int not null,
    page_start int,
    page_end int,
    chunk_type text,
    text text not null,
    normalized_text text,
    summary text,
    token_count int,
    created_at timestamptz not null
)
```

#### `ingestion_jobs`

```sql
ingestion_jobs (
    id uuid primary key,
    document_id uuid references documents(id),
    status text not null,
    current_stage text,
    error_message text,
    metadata jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null
)
```

---

### 7.3. Индексы PostgreSQL

```sql
create index idx_contracts_contractor_entity_id
on contracts(contractor_entity_id);

create index idx_contracts_document_date
on contracts(document_date);

create index idx_contracts_document_type
on contracts(document_type);

create index idx_contracts_fields_gin
on contracts using gin(fields);

create index idx_contractor_entities_inn
on contractor_entities(inn);

create index idx_contract_chunks_contract_id
on contract_chunks(contract_id);

create index idx_contract_chunks_contractor_entity_id
on contract_chunks(contractor_entity_id);
```

---

## 8. Qdrant

### 8.1. Назначение

Qdrant хранит embeddings чанков и используется для semantic search.

Каждый point в Qdrant соответствует одному chunk.

---

### 8.2. Qdrant payload

Каждый Qdrant point должен иметь payload:

```json
{
  "chunk_id": "chunk_123",
  "document_id": "doc_123",
  "contract_id": "contract_456",
  "contractor_entity_id": "c_123",
  "contractor_name": "ООО ФруктТорг",
  "document_type": "Договор поставки",
  "chunk_type": "body",
  "page_start": 1,
  "page_end": 2,
  "document_date": "2024-03-15",
  "has_penalties": true,
  "has_amount": true,
  "contract_subject": "поставка фруктов"
}
```

---

### 8.3. Payload indexes

Необходимо создать payload indexes для часто используемых фильтров:

```text
contractor_entity_id
contract_id
document_id
document_type
chunk_type
document_date
has_penalties
has_amount
```

---

## 9. Search pipeline

### 9.1. Общая схема

Поиск должен быть реализован как 4-стадийный pipeline:

```text
1. Query Router / PostgreSQL pre-filter
2. Qdrant Retrieval / Vector + Payload Search
3. Rerank / Multi-source scoring
4. LLM Generation / Structured answer + drill-down links
```

---

### 9.2. Шаг 1 — Query Router

Query Router определяет тип запроса и scope поиска.

Типы запросов:

```text
GLOBAL
CONTRACTOR
CONTRACT
DRILL_DOWN_CONTRACTOR
DRILL_DOWN_CONTRACT
FACT_FILTERED
```

Примеры:

```text
"поставщики фруктов" → GLOBAL
"штрафы у ФруктТорг" → CONTRACTOR
"риски в договоре 456" → CONTRACT
"найди внутри подрядчика c_123 договоры со штрафами" → DRILL_DOWN_CONTRACTOR
"договоры с НДС и штрафами" → FACT_FILTERED
```

---

### 9.3. PostgreSQL pre-filter

PostgreSQL должен использоваться для точных и структурных фильтров:

```text
contractor_name
contractor_inn
contract_id
document_type
date_range
amount_range
has_penalties
has_vat
contract_subject
```

Пример:

```sql
select distinct contractor_entity_id
from contracts
where fields ? 'penalties'
   or fields ->> 'penalties' is not null;
```

Результат router-а:

```json
{
  "query_type": "FACT_FILTERED",
  "contractor_entity_ids": ["c_123"],
  "contract_ids": ["contract_456", "contract_789"],
  "filters": {
    "has_penalties": true,
    "contract_subject": "фрукты"
  }
}
```

---

### 9.4. Шаг 2 — Qdrant Retrieval

После pre-filter система должна выполнить vector search в Qdrant с payload-фильтрами.

Пример:

```python
qdrant_filter = {
    "must": [
        {
            "key": "contractor_entity_id",
            "match": {"any": ["c_123"]}
        }
    ]
}
```

Для запроса:

```text
поставщики фруктов с штрафами
```

поиск должен работать так:

```text
1. query_emb = embed("поставщики фруктов с штрафами")
2. Qdrant ищет top-K chunks
3. Qdrant ограничивает поиск payload-фильтром из PostgreSQL
4. Возвращаются chunk_id, score, payload
```

---

### 9.5. Hybrid search

Базовая версия:

```text
dense vector search only
```

Расширенная версия:

```text
dense vector search + sparse keyword search + fusion
```

Это полезно, потому что dense vectors хорошо ловят смысл, а sparse vectors помогают с точными терминами:

- ИНН;
- номера договоров;
- юридические формулировки;
- названия подрядчиков.

---

### 9.6. Шаг 3 — Rerank

Rerank должен пересчитать релевантность найденных чанков на основании нескольких источников.

Базовая формула:

```text
final_score =
    qdrant_score * 0.50
  + chunk_summary_score * 0.25
  + document_facts_score * 0.20
  + exact_match_score * 0.05
```

Пример:

```python
final_score = (
    hit.qdrant_score * 0.50
    + summary_score * 0.25
    + facts_score * 0.20
    + exact_match_score * 0.05
)
```

Источники rerank:

```text
1. Qdrant score — близость embedding query к chunk embedding
2. Chunk summary score — совпадение query с summary чанка
3. Document facts score — совпадение query с extracted fields
4. Exact match score — точное совпадение по ИНН, номеру договора, названию, штрафам
```

---

### 9.7. Шаг 4 — LLM Generation

LLM Generation Service должен получать top-N reranked chunks и structured facts из PostgreSQL.

LLM не должен самостоятельно придумывать подрядчиков, договоры, суммы или штрафы. Он должен отвечать только на основании переданного context.

Формат ответа:

```json
{
  "answer": "Найдены 2 договора поставки фруктов со штрафными условиями.",
  "contractors": [
    {
      "contractor_entity_id": "c_123",
      "name": "ООО ФруктТорг",
      "matched_contracts": [
        {
          "contract_id": "contract_456",
          "document_number": "45/2024",
          "matched_facts": [
            "Предмет договора: поставка фруктов",
            "Штраф: 1% за каждый день просрочки"
          ],
          "matched_chunks": ["chunk_123", "chunk_124"]
        }
      ]
    }
  ],
  "drilldown_links": [
    {
      "type": "contractor",
      "id": "c_123",
      "url": "/contractors/c_123"
    },
    {
      "type": "contract",
      "id": "contract_456",
      "url": "/contracts/contract_456"
    }
  ]
}
```

---

## 10. Drill-down UX

### 10.1. Уровень 1 — общий поиск

Пользователь вводит:

```text
поставщики фруктов
```

Система возвращает список подрядчиков:

```json
[
  {
    "contractor_entity_id": "c_123",
    "name": "ООО ФруктТорг",
    "relevance_score": 0.92,
    "matched_contracts_count": 3,
    "matched_chunks_count": 8,
    "preview": "Найдены договоры поставки яблок, груш и цитрусовых."
  }
]
```

---

### 10.2. Уровень 2 — карточка подрядчика

При переходе на:

```text
/contractors/c_123
```

система показывает:

```text
canonical name
ИНН
КПП
aliases
количество договоров
список договоров
summary по подрядчику
релевантные extracted facts
```

---

### 10.3. Уровень 3 — договоры подрядчика

Пользователь видит список договоров:

```json
[
  {
    "contract_id": "contract_456",
    "document_number": "45/2024",
    "document_date": "2024-03-15",
    "contract_subject": "Поставка фруктов",
    "amount": "1 500 000 RUB",
    "has_penalties": true,
    "summary": "Договор поставки фруктов..."
  }
]
```

---

### 10.4. Уровень 4 — поиск внутри договора

При поиске внутри договора Qdrant должен получать payload filter:

```json
{
  "must": [
    {
      "key": "contract_id",
      "match": {
        "value": "contract_456"
      }
    }
  ]
}
```

Пользовательский запрос:

```text
какие штрафы есть в этом договоре?
```

Ответ:

```json
{
  "answer": "В договоре предусмотрен штраф 1% за каждый день просрочки поставки.",
  "matched_chunks": [
    {
      "chunk_id": "chunk_123",
      "page_start": 5,
      "page_end": 5,
      "text_preview": "За просрочку поставки Поставщик уплачивает штраф...",
      "score": 0.94
    }
  ]
}
```

---

## 11. API

### 11.1. Upload document

```http
POST /api/v1/documents/upload
```

Response:

```json
{
  "document_id": "doc_123",
  "ingestion_job_id": "job_456",
  "status": "queued"
}
```

---

### 11.2. Get ingestion status

```http
GET /api/v1/ingestion-jobs/{job_id}
```

Response:

```json
{
  "job_id": "job_456",
  "document_id": "doc_123",
  "status": "embedding",
  "current_stage": "embedding",
  "progress": 0.78
}
```

---

### 11.3. Global search

```http
POST /api/v1/search
```

Request:

```json
{
  "query": "поставщики фруктов с штрафами",
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-12-31"
  },
  "limit": 10
}
```

Response:

```json
{
  "query_type": "FACT_FILTERED",
  "answer": "...",
  "contractors": [],
  "contracts": [],
  "chunks": [],
  "drilldown_links": []
}
```

---

### 11.4. Search inside contractor

```http
POST /api/v1/contractors/{contractor_entity_id}/search
```

Request:

```json
{
  "query": "договоры со штрафами",
  "limit": 10
}
```

---

### 11.5. Search inside contract

```http
POST /api/v1/contracts/{contract_id}/search
```

Request:

```json
{
  "query": "условия расторжения",
  "limit": 10
}
```

---

### 11.6. Contractor details

```http
GET /api/v1/contractors/{contractor_entity_id}
```

---

### 11.7. Contract details

```http
GET /api/v1/contracts/{contract_id}
```

---

## 12. Кодовая организация

Рекомендуемая структура:

```text
backend/app/
├── api/
│   └── v1/
│       ├── documents.py
│       ├── search.py
│       ├── contractors.py
│       └── contracts.py
│
├── application/
│   ├── ingestion/
│   │   ├── upload_document.py
│   │   ├── process_document.py
│   │   └── index_document.py
│   │
│   └── search/
│       ├── search_pipeline.py
│       ├── query_router.py
│       ├── reranker.py
│       └── response_generator.py
│
├── domain/
│   ├── documents/
│   ├── contracts/
│   ├── contractors/
│   └── search/
│
├── infrastructure/
│   ├── persistence/
│   │   ├── postgres/
│   │   └── repositories.py
│   │
│   ├── vector/
│   │   └── qdrant_client.py
│   │
│   ├── llm/
│   ├── embeddings/
│   ├── conversion/
│   ├── pdf/
│   ├── ocr/
│   └── queue/
│
└── workers/
    └── ingestion_worker.py
```

---

## 13. SearchPipeline: целевой интерфейс

```python
class SearchPipeline:
    async def search(
        self,
        query: str,
        filters: dict | None = None,
        scope: dict | None = None,
        limit: int = 10,
    ) -> SearchResponse:
        router_result = await self.query_router.route(query, filters, scope)

        qdrant_hits = await self.retriever.retrieve(
            query=query,
            router_result=router_result,
            limit=50,
        )

        reranked = await self.reranker.rerank(
            query=query,
            hits=qdrant_hits,
            router_result=router_result,
        )

        response = await self.generator.generate(
            query=query,
            chunks=reranked[:limit],
            router_result=router_result,
        )

        return response
```

---

## 14. Нефункциональные требования

### 14.1. Производительность

Целевые значения для наполненной базы среднего размера:

```text
PostgreSQL pre-filter: до 100 ms
Qdrant retrieval: до 150–300 ms
Rerank: до 200 ms
LLM generation: до 1–3 s
```

Для UI нужно поддержать два режима:

```text
fast mode — без LLM generation, только contractors/contracts/chunks
answer mode — с LLM generation
```

---

### 14.2. Масштабируемость

Система должна поддерживать рост:

```text
100+ документов
1 000+ chunks
10 000+ chunks
100 000+ chunks
```

Архитектура не должна завязываться на локальный SQLite-подход SAGE. В целевой архитектуре PostgreSQL должен стать основным source of truth.

---

### 14.3. Надёжность

Ingestion должен быть идемпотентным:

```text
повторный запуск job не должен создавать дубликаты contracts/chunks/entities
```

Нужно хранить:

```text
processing status
ошибки по стадиям
partial extraction flag
confidence
source pages
```

---

### 14.4. Объяснимость

Каждый результат поиска должен иметь ссылки на источник:

```text
contract_id
chunk_id
page_start
page_end
matched_text_preview
matched_facts
score
```

---

## 15. Acceptance criteria

Функциональность считается реализованной, если:

1. Пользователь может загрузить PDF/DOC/DOCX, а система создаёт ingestion job.
2. Не-PDF документы конвертируются в PDF.
3. Текстовые PDF обрабатываются через text extraction.
4. Сканированные страницы обрабатываются через OCR.
5. Документ разбивается на chunks.
6. LLM извлекает structured fields и summary.
7. Подрядчики связываются в canonical contractor entities.
8. PostgreSQL хранит документы, договоры, поля, summary, chunks и contractor entities.
9. Qdrant хранит embeddings chunks с payload filters.
10. Поиск `"поставщики фруктов с штрафами"` возвращает подрядчиков, договоры и релевантные чанки.
11. Поиск внутри подрядчика ограничивается `contractor_entity_id`.
12. Поиск внутри договора ограничивается `contract_id`.
13. Ответ содержит drill-down links.
14. Каждый ответ содержит ссылки на исходные chunks/pages.
15. Система не выдумывает факты, которых нет в extracted fields или chunks.

---

## 16. MVP scope

В первую версию стоит включить:

```text
1. Upload PDF/DOC/DOCX
2. Conversion через soffice
3. Text extraction + OCR fallback
4. Chunking
5. LLM extraction fields + document summary
6. PostgreSQL schema
7. Qdrant indexing
8. Entity resolution по ИНН и normalized name
9. SearchPipeline:
   - PG pre-filter
   - Qdrant vector search
   - simple rerank
   - structured response
10. Drill-down:
   - global search
   - contractor page
   - contract page
   - search inside contractor
   - search inside contract
```

---

## 17. Out of scope для MVP

На первую версию не включать:

```text
сложный graph-based entity resolution
ручной moderation workflow для contractor merge
полноценный hybrid dense+sparse search
обучаемый reranker
автоматическое сравнение версий договоров
сложную аналитику рисков
мультиарендность
сложные ACL/permission model
```

---

## 18. Итоговая формулировка

Нужно реализовать систему поиска по базе договоров, где extraction pipeline наполняет PostgreSQL структурированными данными и Qdrant векторными представлениями чанков, а search pipeline выполняет гибридный многостадийный поиск:

```text
PostgreSQL metadata/facts pre-filter
→ Qdrant vector + payload retrieval
→ rerank по chunks, summaries и extracted facts
→ структурированный ответ с contractor/contract drill-down links
```

Главное отличие от обычного RAG: результатом поиска должны быть не только текстовые фрагменты, а бизнес-сущности:

```text
подрядчик
договор
извлечённые факты
страницы/чанки-источники
переходы для drill-down
```

Такая схема хорошо ложится на C4-архитектуру:

- PostgreSQL отвечает за точные данные и сущности;
- Qdrant отвечает за semantic retrieval по чанкам;
- LLM отвечает за extraction и финальную генерацию ответа;
- Entity Resolution связывает сырые названия подрядчиков с canonical contractor entities.

---

## 19. Полезные ссылки

- [SAGE](https://github.com/2made1ra/SAGE)
- [Qdrant Filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant Payload Indexing](https://qdrant.tech/documentation/manage-data/indexing/)
- [Qdrant Hybrid Queries](https://qdrant.tech/documentation/search/hybrid-queries/)
