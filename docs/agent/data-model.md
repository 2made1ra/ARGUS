# Data Model

## PostgreSQL tables

**contractors**
```sql
id              uuid PK
display_name    text
normalized_key  text UNIQUE       -- canonical matching key
inn             text              -- primary dedup key, nullable
kpp             text
created_at      timestamptz
```

**contractor_raw_mappings**
```sql
id                   uuid PK
raw_name             text
inn                  text
contractor_entity_id uuid FK → contractors.id
confidence           float         -- 1.0=exact, <1.0=fuzzy
```

**documents**
```sql
id                   uuid PK
contractor_entity_id uuid FK → contractors.id, nullable
title                text
file_path            text
content_type         text
document_kind        text          -- "text" | "scan"
doc_type             text          -- "contract" | "act" | "invoice" | ...
status               text          -- QUEUED | PROCESSING | RESOLVING | INDEXING | INDEXED | FAILED
error_message        text          -- null unless status=FAILED
partial_extraction   bool
created_at           timestamptz
```

**document_chunks**
```sql
id              uuid PK
document_id     uuid FK → documents.id
chunk_index     int
text            text
page_start      int
page_end        int
section_type    text
chunk_summary   text
```

**extracted_fields**
```sql
id          uuid PK
document_id uuid FK → documents.id UNIQUE
fields      jsonb       -- ContractFields as JSON
created_at  timestamptz
```

**document_summaries**
```sql
id          uuid PK
document_id uuid FK → documents.id UNIQUE
summary     text
key_points  text[]
created_at  timestamptz
```

## Qdrant collection: `document_chunks`

**Payload per vector:**
```json
{
  "document_id":           "uuid",
  "contractor_entity_id":  "uuid",
  "doc_type":              "contract",
  "document_kind":         "text",
  "date":                  "2025-01-15",
  "page_start":            3,
  "page_end":              4,
  "section_type":          "body",
  "chunk_index":           7,
  "text":                  "...",
  "is_summary":            false
}
```

Document-level summary: stored as a chunk with `is_summary: true`, `chunk_index: -1`.

## ContractFields (LLM extraction target)

Russian contract fields, all `Optional[str]`, never invented — null if not found:
`document_type`, `document_number`, `document_date`, `supplier_name`, `customer_name`,
`service_date`, `amount`, `vat`, `valid_until`, `supplier_inn`, `supplier_kpp`,
`supplier_bik`, `supplier_account`, `customer_inn`, `customer_kpp`, `customer_bik`,
`customer_account`, `service_subject`, `service_price`, `signatory_name`, `contact_phone`
