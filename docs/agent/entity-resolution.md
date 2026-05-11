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
