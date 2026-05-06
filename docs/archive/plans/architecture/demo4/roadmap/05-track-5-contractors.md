# 05 — Track 5: Contractors feature *(приоритет №2)*

**Зависит от:** Track 3 (схема)
**Разблокирует:** Track 9 (HTTP) и финальную цепочку Celery
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 5 — Contractors feature»

## Контекст

Контрагенты в ARGUS — отдельная фича. Документ после извлечения полей
получает «сырое» имя поставщика (`fields.supplier_name`) и, опционально,
ИНН. Задача фичи — превратить пару `(raw_name, inn)` в канонический
`ContractorEntityId`, переиспользуя существующего контрагента или создавая
нового.

CLAUDE.md описывает 4-шаговый каскад:

1. INN exact match.
2. Normalized key match.
3. Fuzzy через RapidFuzz `token_sort_ratio ≥ 90`.
4. Создать нового.

Также фича отвечает за чтение профиля контрагента и листинг его
документов.

## Целевое состояние

```
backend/app/features/contractors/
├── __init__.py
├── entities/
│   ├── __init__.py
│   ├── contractor.py            # Contractor
│   └── resolution.py            # RawContractorMapping
├── ports.py                     # ContractorRepository, RawContractorMappingRepository
├── normalization.py             # normalize_name
├── normalization_rules.yaml     # legal forms, stopwords
└── use_cases/
    ├── __init__.py
    ├── resolve_contractor.py
    ├── get_contractor_profile.py
    └── list_contractor_documents.py

backend/app/adapters/sqlalchemy/
└── contractors.py               # SqlAlchemyContractorRepository, SqlAlchemyRawContractorMappingRepository
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 5.1 | Contractor entities, ports, repositories | `entities/contractor.py`, `entities/resolution.py`, `ports.py`, `adapters/sqlalchemy/contractors.py` |
| 5.2 | Name normalization + `ResolveContractorUseCase` | `normalization.py`, `normalization_rules.yaml`, `use_cases/resolve_contractor.py`, тесты |
| 5.3 | Profile + listing use cases | `use_cases/get_contractor_profile.py`, `use_cases/list_contractor_documents.py`, тесты |

## Критерии приёмки трека

- [ ] `ResolveContractorUseCase.execute(document_id)` гонит каскад INN →
  normalized key → fuzzy → create.
- [ ] Имя нормализуется детерминированно: один и тот же raw_name даёт один
  и тот же `normalized_key`.
- [ ] Каждый успешный resolve пишет `RawContractorMapping` и обновляет
  `document.contractor_entity_id`.
- [ ] `GetContractorProfileUseCase` и `ListContractorDocumentsUseCase`
  возвращают полные DTO для HTTP.

## Что НЕ делаем

* Не пишем Celery-таск `resolve_contractor` — это Track 9.
* Не пишем интеграционные тесты на репозитории.
* Не реализуем «человеческое» подтверждение резолва — это post-MVP.
* Не используем ML/embeddings для матчинга — только rule-based (RapidFuzz).

## Тесты

| Модуль | Что покрыть |
|--------|-------------|
| `normalize_name` | Table-driven: ООО/ОАО/ИП/ПАО/ЗАО/НКО префиксы, пунктуация, пробелы, FIO heuristic (2/3 cyrillic tokens). |
| `ResolveContractorUseCase` | Каждая ветка каскада отдельно: INN exact, normalized key, fuzzy ≥90, fuzzy <90 → create. Проверка записи `RawContractorMapping` и `document.contractor_entity_id`. |
| `GetContractorProfileUseCase` | Возвращает `ContractorProfile` с count'ами. |
| `ListContractorDocumentsUseCase` | Сортировка по `created_at desc`, пагинация. |

## Verification checklist

- [ ] `pytest backend/tests/features/contractors -v`
- [ ] `python -c "from app.features.contractors.use_cases.resolve_contractor
  import ResolveContractorUseCase"`

---

## Промпты для агента

### PR 5.1 — Contractor entities, ports, repositories

```text
Role: ты — backend-инженер проекта ARGUS, формализуешь домен и хранилище
контрагентов.

# Goal
Создать домен-сущности `Contractor` и `RawContractorMapping`, объявить
порты `ContractorRepository` и `RawContractorMappingRepository`,
реализовать SQLAlchemy-адаптеры обоих портов.

# Context
- План трека: `docs/architecture/roadmap/05-track-5-contractors.md`.
- ORM-таблицы `contractors`, `contractor_raw_mappings` уже существуют
  (Track 3 PR 3.2).
- ID-типы: `app.core.domain.ids.ContractorEntityId`.

# Success criteria
- `entities/contractor.py`:
  * `@dataclass class Contractor`: `id: ContractorEntityId, display_name:
    str, normalized_key: str, inn: str | None, kpp: str | None,
    created_at: datetime`.
- `entities/resolution.py`:
  * `@dataclass class RawContractorMapping`: `id: UUID, raw_name: str,
    inn: str | None, contractor_entity_id: ContractorEntityId, confidence:
    float`.
- `ports.py`:
  * `ContractorRepository` Protocol:
    * `async add(contractor) -> None`.
    * `async get(id) -> Contractor`.
    * `async find_by_inn(inn: str) -> Contractor | None`.
    * `async find_by_normalized_key(key: str) -> Contractor | None`.
    * `async find_all_for_fuzzy() -> list[Contractor]` — для MVP отдаём
      все строки; продакшн-оптимизация (LSH/триграммы) — post-MVP.
    * `async count_documents_for(id) -> int`.
    * `async list_for_contractor(id, *, limit, offset) -> list[Document]`
      — берёт из таблицы `documents`. Реэкспорт `Document` через
      `app.features.ingest.entities.document`.
  * `RawContractorMappingRepository` Protocol:
    * `async add(mapping) -> None`.
    * `async find_by_raw(raw_name, inn) -> RawContractorMapping | None`.
- SQLAlchemy-адаптеры:
  * `SqlAlchemyContractorRepository(session)` реализует все методы порта.
  * `SqlAlchemyRawContractorMappingRepository(session)` — тоже.
  * Никаких commit'ов внутри.
  * Маппинг ORM↔domain — приватные `_to_entity` функции.
- Никаких юнит-тестов на адаптеры (по конвенции).

# Constraints
- НЕ использовать кросс-фичевые импорты, кроме `Document` через
  `app.features.ingest.entities.document` (это разрешённое исключение —
  список документов контрагента читается из той же таблицы).
- НЕ делать `find_all_for_fuzzy` ленивым итератором — простой `list[
  Contractor]` достаточен для MVP.
- НЕ хранить normalized_key в Contractor entity если он не используется в
  domain-логике; но он нужен для fuzzy fallback, поэтому оставляем.

# Output
- Содержимое всех файлов.
- Импорт-смок: `python -c "from app.features.contractors.ports import
  ContractorRepository, RawContractorMappingRepository"`.

# Stop rules
- Если связь Contractor ↔ Document через ingest-фичу делает граф импортов
  циклическим — оставь `Document` импорт под `if TYPE_CHECKING:` в `ports.py`
  и используй `from __future__ import annotations`.
```

### PR 5.2 — Name normalization + `ResolveContractorUseCase`

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь нормализацию имён и
основной use case резолвинга контрагентов.

# Goal
Реализовать `normalize_name(raw)` (детерминированная pure-функция) и
`ResolveContractorUseCase` с 4-шаговым каскадом из CLAUDE.md «Entity
Resolution». Покрыть тестами все ветки.

# Context
- План трека: `docs/architecture/roadmap/05-track-5-contractors.md`.
- Каскад: `CLAUDE.md` → «Entity Resolution — contractors feature».
- Сущности и порты: PR 5.1.
- Документ имеет `extracted_fields.fields` (JSONB). Чтобы прочитать
  `supplier_name`/`supplier_inn` — нужен `FieldsRepository.get(document_id)`
  из ingest-фичи (Track 4 PR 4.1).

# Success criteria
- `normalization.py`:
  * `normalize_name(raw: str) -> str` — pure.
  * Шаги:
    1. Strip surrounding whitespace.
    2. Удалить legal-form префиксы (case-insensitive): ООО, АО, ИП, ПАО,
       ЗАО, НКО — окружённые пробелами/кавычками или в начале/конце.
       Список — из `normalization_rules.yaml`.
    3. Убрать пунктуацию (оставить пробелы).
    4. Lowercase.
    5. Схлопнуть whitespace в один пробел.
    6. FIO heuristic: если результат — 2 или 3 кириллические токена
       (`re.fullmatch(r"[а-яёa-z]+( [а-яёa-z]+){1,2}", s)`) — отсортировать
       токены лексикографически и склеить (каноническая форма ФИО).
  * `normalization_rules.yaml`: ключи `legal_forms: [...]`, `stopwords:
    [...]`, `blocklist: [...]`. Загрузка через `pyyaml`. Кеш через
    `lru_cache`.
- `ResolveContractorUseCase`:
  * Конструктор: `__init__(*, contractors: ContractorRepository, mappings:
    RawContractorMappingRepository, documents: DocumentRepository, fields:
    FieldsRepository, uow: UnitOfWork)`.
  * `async def execute(self, document_id: DocumentId) -> ContractorEntityId`:
    1. `async with uow:` загрузить документ, поля.
    2. Извлечь `raw_name = fields.supplier_name`, `inn =
       fields.supplier_inn`. Если `raw_name` пустой — пропустить резолв,
       пометить `document.contractor_entity_id = None`, commit, return None.
       (Документ остаётся резолвимым позже вручную.)
    3. Каскад:
       a. Если `inn`: `existing = await contractors.find_by_inn(inn)`.
          Если найден — confidence = 1.0.
       b. Иначе: `key = normalize_name(raw_name); existing =
          await contractors.find_by_normalized_key(key)`. Confidence = 1.0.
       c. Иначе: `pool = await contractors.find_all_for_fuzzy()`,
          `best = max(pool, key=lambda c: rapidfuzz.fuzz.token_sort_ratio(
          c.normalized_key, key))`. Если `score >= 90` — confidence =
          score/100.
       d. Иначе: создать `Contractor(id=new_contractor_entity_id(),
          display_name=raw_name, normalized_key=key, inn=inn, ...)`.
          Confidence = 1.0.
    4. Записать `RawContractorMapping(id=uuid4(), raw_name, inn,
       contractor_entity_id=resolved.id, confidence)`.
    5. `document.contractor_entity_id = resolved.id`. Persist.
       `document.mark_resolving()` уже должен был быть вызван Celery-обёрткой
       Track 9; здесь use case не трогает status, только attach.
    6. Commit.
    7. Return `resolved.id`.
- Юнит-тесты: каждая ветка каскада — отдельный тест с in-memory fakes.
  Также: пустой `raw_name` — проход без падения.

# Constraints
- НЕ менять `document.status` — за это отвечает Celery-обёртка.
- НЕ делать сетевых вызовов.
- НЕ кэшировать pool fuzzy — каждый вызов делает свежий запрос.
- НЕ хранить YAML-правила в Python-коде — только в файле.

# Output
- Содержимое всех файлов.
- Вывод `pytest backend/tests/features/contractors -k "normalize or resolve"
  -v`.
- Сэмпл `normalization_rules.yaml`.

# Stop rules
- Если `find_all_for_fuzzy` будет тормозить на большом пуле — зафиксируй в
  Output, не оптимизируй (это post-MVP).
- Если в данных встречаются ИНН с разной длиной (10/12 цифр) — нормализуй
  только пробелы, не дроби по длине.
```

### PR 5.3 — Profile + listing use cases

```text
Role: ты — backend-инженер проекта ARGUS, добавляешь read-side use case'ы
для профиля и документов контрагента.

# Goal
Реализовать `GetContractorProfileUseCase` и `ListContractorDocumentsUseCase`
в `backend/app/features/contractors/use_cases/`, использующие репозитории
из PR 5.1.

# Context
- План трека: `docs/architecture/roadmap/05-track-5-contractors.md`.
- Порты `ContractorRepository.count_documents_for`,
  `list_for_contractor` — уже есть (PR 5.1).

# Success criteria
- DTO `ContractorProfile` (dataclass) в `use_cases/get_contractor_profile.py`:
  `contractor: Contractor`, `document_count: int`,
  `raw_mapping_count: int`.
- `GetContractorProfileUseCase.execute(contractor_id) -> ContractorProfile`.
- `ListContractorDocumentsUseCase.execute(*, contractor_id, limit=20,
  offset=0) -> list[Document]`. Сортировка по `created_at desc` (на стороне
  репозитория).
- Юнит-тесты с in-memory fakes:
  * Профиль: вернуть Contractor с counts.
  * Листинг: пагинация (limit=2, offset=2), сортировка.

# Constraints
- НЕ ходить в файловое хранилище.
- НЕ возвращать связанные документы внутри `ContractorProfile` — это
  отдельный use case.
- НЕ N+1: count'ы — отдельные запросы, ОК для MVP.

# Output
- Содержимое use case'ов и тестов.
- Вывод `pytest backend/tests/features/contractors/use_cases -v`.

# Stop rules
- Если для подсчёта raw_mappings в `RawContractorMappingRepository` нет
  метода `count_for(contractor_id)` — добавь его в порт и адаптер
  (минимальное расширение PR 5.1).
```
