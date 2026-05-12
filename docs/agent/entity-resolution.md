# Entity Resolution

Entity resolution remains part of the document/PDF workflow. In the catalog MVP,
CSV supplier fields on `price_items` are stored as catalog facts and are not
automatically resolved into `contractors`.

Guidance:

- `supplier`, `supplier_inn`, `supplier_city`, phone and email from `prices.csv`
  belong on `price_items` for cards, filters and provenance.
- Do not call contractor resolution from the MVP CSV import path.
- Do not block catalog search on contractor matching quality.
- Post-MVP can add an explicit supplier-to-contractor linking workflow, but it
  must preserve the original catalog row facts.

## Supplier Verification Boundary

Supplier verification for the event-brief assistant is a separate backend tool,
not contractor entity resolution.

Use cases:

```text
document/PDF workflow
  -> resolve_contractor(raw_name, inn)
  -> contractors + contractor_raw_mappings

assistant workflow
  -> verify_supplier_status(item ids / supplier INN / supplier name)
  -> SupplierVerificationResult
```

Rules:

- CSV import must not call `resolve_contractor`.
- Catalog search must not depend on contractor matching quality.
- `verify_supplier_status` must work through an explicit
  `SupplierVerificationPort`.
- The default MVP adapter may return `not_verified` with a risk flag such as
  `verification_adapter_not_configured`.
- Future FNS EGRUL/EGRIP or DaData adapters must live in `adapters/`, behind
  the same port, and must not be called from domain code directly.
- Verification targets can come only from `selected_item_ids`,
  `candidate_item_ids`, `visible_candidates` or explicit item ids in the
  request. Do not infer targets from hidden chat history.
- If multiple catalog rows share one `supplier_inn`, verify that INN once and
  map the result back to all related item ids.
- Suppliers without INN are returned as `not_verified` with a risk flag such as
  `supplier_inn_missing`.

Verification semantics:

- `status=active` means the legal entity was found as active in the verification
  source.
- `status=active` does not mean the supplier is available on the event date.
- `status=active` does not mean ARGUS recommends the supplier.
- `status=active` does not mean an agency contract is currently valid.
- Assistant prose should say `юрлицо найдено как действующее в проверочном
  источнике`, not `подрядчик готов к мероприятию`.

`resolve_contractor(raw_name, inn) → ContractorEntityId`

## Matching cascade (stop at first match)

1. **INN exact** — `SELECT * FROM contractors WHERE inn = ?` — deterministic, confidence 1.0
2. **Normalized key exact** — apply `normalize_name()` → lookup `normalized_key`
3. **Fuzzy** — RapidFuzz `token_sort_ratio ≥ 90` against all contractors (or INN-filtered subset)
4. **Create new** — if no match, insert new `Contractor`

## Normalization rules

- Strip legal form prefixes: `ООО`, `АО`, `ИП`, `ПАО`, `ЗАО`, `НКО`
- Strip punctuation, normalize whitespace, lowercase
- FIO heuristic: detect Russian person names (2–3 Cyrillic tokens), reorder to canonical form
- YAML-configurable stopwords and blocklist

## Storage

Matched or created entity is recorded in `contractor_raw_mappings`:
- `confidence = 1.0` for INN/normalized-key exact matches
- `confidence < 1.0` for fuzzy matches (actual ratio / 100)
