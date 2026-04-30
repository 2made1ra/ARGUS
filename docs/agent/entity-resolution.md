# Entity Resolution

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
