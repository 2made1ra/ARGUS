# ARGUS Roadmap — рабочие документы по трекам

Эта папка — набор рабочих документов по трекам построения MVP ARGUS.
Источник истины — [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md)
и [`../../../CLAUDE.md`](../../../CLAUDE.md). Каждый документ раскрывает один
трек: контекст, целевое состояние, список PR с критериями приёмки, тесты и
**самодостаточные промпты для агента-исполнителя** (Claude Code / Codex GPT-5).

Промпты написаны по гайдлайну OpenAI Prompt Guidance (GPT-5):
outcome-first, явные `Role / Goal / Context / Success criteria / Constraints /
Output / Stop rules`.

## Как пользоваться

1. Откройте документ нужного трека.
2. Выберите PR из секции «План работы».
3. Скопируйте соответствующий блок «Промпт для агента» целиком.
4. Запустите Claude Code или Codex GPT в чистой ветке от актуального `main`.
5. По завершении проверьте **Критерии приёмки** PR и общий **Verification
   checklist** трека.
6. Если diff превышает ~400 строк осмысленных изменений, разбейте PR ещё мельче,
   сохранив те же критерии.

## Порядок треков

| # | Файл | Зависит от | Цель |
|---|------|------------|------|
| 00 | [00-track-0-foundation.md](00-track-0-foundation.md) | — | Скелет монорепо, docker-compose, конфиг, плейсхолдер C4 |
| 01 | [01-track-1-sage-package.md](01-track-1-sage-package.md) | 00 | Извлечь `packages/sage` из существующего SAGE-сервиса |
| 02 | [02-track-2-core-domain.md](02-track-2-core-domain.md) | 00 | ID-newtype'ы и `UnitOfWork` |
| 03 | [03-track-3-persistence.md](03-track-3-persistence.md) | 02 | SQLAlchemy + Alembic, начальная миграция, базовые репозитории |
| 04 | [04-track-4-ingest.md](04-track-4-ingest.md) | 01, 03 | Upload → process → персистенция чанков/полей/summary |
| 05 | [05-track-5-contractors.md](05-track-5-contractors.md) | 03 | Каскад резолвинга контрагентов, профиль, листинг |
| 06 | [06-track-6-indexing.md](06-track-6-indexing.md) | 03, 04 | Адаптеры Qdrant и embeddings, use case `index_document` |
| 07 | [07-track-7-search.md](07-track-7-search.md) | 06 | Drill-down: контрагенты → документы → внутри документа |
| 08 | [08-track-8-documents.md](08-track-8-documents.md) | 03 | Read-API: `get_document`, `list_documents`, `get_document_facts` |
| 09 | [09-track-9-celery-http.md](09-track-9-celery-http.md) | 04, 05, 06, 07, 08 | Celery-app, цепочка тасков, FastAPI-роутеры, SSE |
| 10 | [10-track-10-test-frontend.md](10-track-10-test-frontend.md) | 09 | React + Vite минимальный фронтенд для тестирования |

После трека 10 — конец MVP. Post-MVP-разделы (auth, мульти-тенантность,
observability, CI/CD, hardening, прод-фронтенд) описаны в
[`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md).

## Общие правила для треков

* **Vertical slice + hexagonal core.** `features/` владеют сущностями, use
  case'ами и портами. Никаких cross-feature импортов.
* **Ports — это `typing.Protocol`**, объявленные внутри фичи. Адаптеры лежат в
  `backend/app/adapters/<tech>/`.
* **Use case** — конструктор для зависимостей, `async def execute(...)` для
  работы. Никакого глобального состояния.
* **Entrypoints тонкие.** Никакой бизнес-логики в FastAPI-хендлерах и Celery-тасках.
* **`packages/sage`** — без сайд-эффектов: одна точка входа
  `process_document(src, work_dir) -> ProcessingResult`.
* **Цепочка задач без событий.** Celery-таск явно ставит следующий через
  `apply_async`. `document.status` — единственный SoT для прогресса.
* **Один PR оставляет систему рабочей.** Существующие тесты должны проходить.
* **Тесты:** unit-тесты на use case'ы и pure-логику (chunker, normalizer,
  resolver, merger). Интеграционные тесты адаптеров — post-MVP.
* **Naming:** `contractor` (не `supplier`), ID-newtype'ы (`DocumentId`,
  `ContractorEntityId`, `ChunkId`), таблицы во множественном snake_case.

## Конвенция промптов

Каждый промпт следует OpenAI Prompt Guidance для GPT-5:

```
Role: <persona и зона ответственности>
# Goal: <одно предложение outcome-first>
# Context: <ссылки на CLAUDE.md, ARCHITECTURE_ROADMAP.md, текущий трек,
            связанные модули>
# Success criteria: <чек-лист, проверяемый автоматически или ревью>
# Constraints: <что нельзя менять, какие интерфейсы оставить>
# Output: <формат финального ответа агента — список файлов, команды, заметки>
# Stop rules: <когда остановиться и спросить вместо того, чтобы продолжать>
```

Промпты самодостаточны: агенту достаточно репозитория и текста промпта,
чтобы выполнить PR без прошлой переписки.
