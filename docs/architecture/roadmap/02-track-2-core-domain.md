# 02 — Track 2: Core domain & ports *(приоритет №1)*

**Зависит от:** Track 0
**Разблокирует:** Track 3, и через него все feature-треки
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 2 — Core domain & ports»

## Контекст

Согласно CLAUDE.md, всё, что разделяют несколько фич (типы ID, общие
порты), живёт в `core/`. Конкретно нужны:

- ID newtype'ы (`DocumentId`, `ContractorEntityId`, `ChunkId`) поверх UUID,
  чтобы не путать сущности на сигнатурах.
- Базовый порт `UnitOfWork` — async-context-менеджер с `commit()`/`rollback()`.

`core/domain/` для типов и `core/ports/` для протоколов. Никаких
конкретных реализаций в этом треке — только Protocol'ы и newtype'ы.

## Целевое состояние

```
backend/app/core/
├── domain/
│   ├── __init__.py        # реэкспорт ID-newtype'ов и фабрик
│   └── ids.py             # DocumentId, ContractorEntityId, ChunkId, new_*_id()
└── ports/
    ├── __init__.py        # реэкспорт UnitOfWork
    └── unit_of_work.py    # Protocol UnitOfWork
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 2.1 | ID newtypes | `backend/app/core/domain/{__init__.py, ids.py}`, тесты |
| 2.2 | UnitOfWork port | `backend/app/core/ports/{__init__.py, unit_of_work.py}` |

## Критерии приёмки трека

- [ ] `from app.core.domain import DocumentId, ContractorEntityId, ChunkId,
  new_document_id, new_contractor_entity_id, new_chunk_id` работает.
- [ ] `from app.core.ports import UnitOfWork` работает.
- [ ] Юнит-тесты на ID round-trip зелёные.
- [ ] `mypy` (если уже подключён) считает типы newtype'ов различимыми.

## Что НЕ делаем

* Не пишем реализации `UnitOfWork` — это Track 3.
* Не вводим базовых классов агрегатов / event base — нам это не нужно для MVP.
* Не вводим `DomainEvent` / `EventBus` — CLAUDE.md явно отвергает событийную
  модель.

## Тесты

* `backend/tests/core/test_ids.py`:
  * фабрики возвращают корректные UUID4-обёртки;
  * round-trip `str(DocumentId(...))` → `UUID(...)`;
  * проверка различимости типов через mypy-комментарий
    `reveal_type` (если mypy подключён) или просто документирующий тест.

## Verification checklist

- [ ] `pytest backend/tests/core -v`
- [ ] `python -c "from app.core.domain import DocumentId, ChunkId; from
  app.core.ports import UnitOfWork; print(UnitOfWork)"`

---

## Промпты для агента

### PR 2.1 — ID newtypes

```text
Role: ты — backend-инженер проекта ARGUS, готовишь общие ID-типы для всех
фич.

# Goal
Определить newtype'ы `DocumentId`, `ContractorEntityId`, `ChunkId` поверх
`uuid.UUID` и фабрики `new_document_id()`, `new_contractor_entity_id()`,
`new_chunk_id()` в `backend/app/core/domain/ids.py`. Реэкспортировать всё
из `core/domain/__init__.py`.

# Context
- План трека: `docs/architecture/roadmap/02-track-2-core-domain.md`.
- CLAUDE.md → «Development Conventions» («ID types: ContractorEntityId,
  DocumentId, ChunkId — newtype wrappers over UUID»).
- Скелет монорепо уже создан в Track 0.

# Success criteria
- `DocumentId = NewType("DocumentId", UUID)`.
- Аналогично `ContractorEntityId`, `ChunkId`.
- Фабрики возвращают `DocumentId(uuid.uuid4())` и т.д.
- Реэкспорт из `core/domain/__init__.py`.
- Тест `tests/core/test_ids.py`:
  * каждая фабрика возвращает значение, проходящее `isinstance(x, UUID)`;
  * `str(DocumentId(...))` парсится обратно через `UUID(...)`;
  * `DocumentId` и `ContractorEntityId` — формально разные типы (тест-
    документ — комментарий с `# type: ignore[arg-type]` показывает
    несовместимость в mypy, либо просто assert на наличие отдельных
    `__name__` через `typing.get_type_hints` если применимо).

# Constraints
- НЕ использовать `class DocumentId(UUID)` — нужен именно `NewType`
  (легче, без runtime-overhead).
- НЕ заводить `BaseId` / абстракций.
- НЕ вводить функций сериализации/десериализации — `UUID` сам по себе
  сериализуется через `str()`.

# Output
- Содержимое `ids.py`, `__init__.py`, теста.
- Вывод `pytest backend/tests/core/test_ids.py -v`.

# Stop rules
- Если в проекте уже подключён mypy — добавь конфиг проверки `strict =
  True` для `app.core` без слома остального кода. Если не подключён — не
  трогай конфиг.
```

### PR 2.2 — UnitOfWork port

```text
Role: ты — backend-инженер проекта ARGUS, описываешь общий порт транзакций.

# Goal
Определить `UnitOfWork` Protocol в `backend/app/core/ports/unit_of_work.py`:
async-context-менеджер с явными `commit()` и `rollback()`. Реэкспортировать
из `core/ports/__init__.py`.

# Context
- План трека: `docs/architecture/roadmap/02-track-2-core-domain.md`.
- CLAUDE.md → «Development Conventions»: ports — `typing.Protocol`, не ABC.
- Реализация (`SqlAlchemyUnitOfWork`) появится в Track 3.

# Success criteria
- `class UnitOfWork(Protocol):` со следующими методами:
  * `async def __aenter__(self) -> "UnitOfWork"`.
  * `async def __aexit__(self, exc_type, exc, tb) -> None`.
  * `async def commit(self) -> None`.
  * `async def rollback(self) -> None`.
- Docstring класса (≤3 строк) фиксирует контракт:
  «выход из контекста без commit() откатывает; исключение внутри блока
  откатывается автоматически».
- Реэкспорт из `core/ports/__init__.py`.
- Никаких реализаций в этом PR.

# Constraints
- НЕ объявлять как ABC.
- НЕ добавлять полей (Protocol'ы — только методы).
- НЕ привязывать к SQLAlchemy.

# Output
- Содержимое `unit_of_work.py`, `__init__.py`.
- Импорт-смок: `python -c "from app.core.ports import UnitOfWork"`.

# Stop rules
- Если в проекте есть стандарт другого имени метода (например `save_changes`)
  — не подгоняй; используй `commit/rollback` строго.
```
