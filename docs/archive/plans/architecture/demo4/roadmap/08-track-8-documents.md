# 08 — Track 8: Documents feature *(приоритет №3)*

**Зависит от:** Track 3 (репозиторий documents), Track 4 (репозитории fields/summary)
**Разблокирует:** Track 9 (HTTP read-API)
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 8 — Documents feature»

## Контекст

`features/documents/` — это read-side для одиночных документов. Нужно:
- получить мета документа (`get_document`);
- листинг с фильтрами (`list_documents`);
- получить «факты» документа (поля + summary + key_points) одной операцией
  для UI.

Поиск по чанкам внутри документа уже реализован в `features/search/`.

## Целевое состояние

```
backend/app/features/documents/
├── __init__.py
├── ports.py                  # реэкспорт DocumentRepository / read-only обёртки
├── dto.py                    # DocumentDTO, DocumentFactsDTO
└── use_cases/
    ├── __init__.py
    ├── get_document.py
    ├── list_documents.py
    └── get_document_facts.py
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 8.1 | Read use cases | все файлы из «целевого состояния», тесты |

## Критерии приёмки трека

- [ ] `GetDocumentUseCase`, `ListDocumentsUseCase`, `GetDocumentFactsUseCase`
  реализованы и покрыты unit-тестами.
- [ ] DTO готовы к прямой сериализации (datetime → ISO, UUID → str —
  средствами FastAPI).

## Что НЕ делаем

* Не пишем HTTP-роутеры (Track 9).
* Не пишем write use case'ы (delete, archive) — post-MVP.
* Не делаем eager-loading связанных контрагентов в `DocumentDTO` — отдельным
  запросом при необходимости.

## Тесты

| Use case | Что покрыть |
|----------|-------------|
| `GetDocumentUseCase` | Возвращает DTO; при отсутствии — `DocumentNotFound`. |
| `ListDocumentsUseCase` | Фильтр по `status`, `contractor_entity_id`; пагинация. |
| `GetDocumentFactsUseCase` | Объединяет fields и summary; если faktов нет — пустой DTO с null'ами. |

## Verification checklist

- [ ] `pytest backend/tests/features/documents -v`

---

## Промпты для агента

### PR 8.1 — Read use cases

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь read-side документов.

# Goal
Создать `features/documents/` со всеми read use case'ами и DTO для
HTTP-сериализации. Никакой бизнес-логики — только маппинг.

# Context
- План трека: `docs/architecture/roadmap/08-track-8-documents.md`.
- Репозитории `DocumentRepository`, `FieldsRepository`, `SummaryRepository`
  уже существуют (Track 3, 4).
- DTO будут сериализованы FastAPI (Track 9).

# Success criteria
- `dto.py`:
  * `DocumentDTO`: id, title, status, doc_type, document_kind,
    contractor_entity_id, content_type, partial_extraction, error_message,
    created_at.
  * `DocumentFactsDTO`: fields (dict — `ContractFields.model_dump()`),
    summary (str | None), key_points (list[str]), partial_extraction
    (bool).
- `use_cases/get_document.py`: `GetDocumentUseCase(*, documents)`,
  `execute(document_id) -> DocumentDTO`. На отсутствии — пробросить
  `DocumentNotFound`.
- `use_cases/list_documents.py`: `ListDocumentsUseCase(*, documents)`,
  `execute(*, limit=50, offset=0, status=None, contractor_id=None) ->
  list[DocumentDTO]`. Если в `DocumentRepository.list` не хватает
  фильтров — расширь сигнатуру порта (Track 3) и адаптер.
- `use_cases/get_document_facts.py`: `GetDocumentFactsUseCase(*, documents,
  fields, summaries)`, `execute(document_id) -> DocumentFactsDTO`. При
  отсутствии fields/summary — null-значения внутри DTO.
- `ports.py`: реэкспортируй `DocumentRepository` из ingest-фичи (через
  явный импорт), не дублируй Protocol. Если хочется ужесточить read-only
  интерфейс — добавь Protocol `DocumentReader` поверх существующего
  репозитория. Допустимы оба подхода; выбери один и зафиксируй.
- Юнит-тесты с in-memory fakes покрывают все три use case'а.

# Constraints
- НЕ возвращать ORM-объекты или SQLAlchemy-Row.
- НЕ читать БД дважды для одного и того же документа в пределах одного
  use case'а.
- НЕ ходить в файловую систему.

# Output
- Содержимое всех файлов.
- Вывод `pytest backend/tests/features/documents -v`.

# Stop rules
- Если расширение `DocumentRepository` ломает другие use case'ы — обнови
  fakes в их тестах в этом же PR (минимально).
```
