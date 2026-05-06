# 01 — Track 1: SAGE package extraction *(приоритет №1)*

**Зависит от:** Track 0
**Разблокирует:** Track 4 (ingest)
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 1 — SAGE package extraction»

## Контекст

Существующий проект `/Users/2madeira/DEV/PROJECTS/SAGE` — это полноценный
FastAPI-сервис с собственной БД, HTTP API и слоями
api/application/domain/infrastructure. Нам нужна не вся эта обвязка, а только
ядро пайплайна обработки документа. По CLAUDE.md `packages/sage` — это
**stateless side-effect-free** Python-пакет с одной точкой входа
`process_document(src, work_dir) -> ProcessingResult`.

Цель трека — **извлечь** код пайплайна из SAGE-сервиса (вариант a в
обсуждении), переписав его под чистый интерфейс пакета: убрать FastAPI,
SQLAlchemy, HTTP-клиенты, любые сайд-эффекты в БД. Оставить только pure-
функции и async-обёртки над внешними утилитами (LibreOffice, pymupdf,
pytesseract, LM Studio).

## Целевое состояние

```
packages/sage/sage/
├── __init__.py             # экспорт process_document, моделей
├── models.py               # Page, Chunk, ContractFields, ExtractedDocument, ProcessingResult
├── process.py              # async process_document(src, work_dir, *, llm_client=None)
├── conversion/
│   ├── __init__.py
│   └── libreoffice.py      # ensure_pdf
├── pdf/
│   ├── __init__.py
│   ├── detector.py         # detect_kind
│   ├── text_extractor.py   # extract_text_pages
│   └── ocr.py              # ocr_pages
├── normalizer/
│   ├── __init__.py
│   └── clean.py            # normalize_pages
├── chunker/
│   ├── __init__.py
│   └── split.py            # chunk_pages
└── llm/
    ├── __init__.py
    ├── client.py           # LMStudioClient
    ├── extract.py          # extract_one, merge_fields, prompts
    └── summary.py          # summarize (map-reduce)
```

Внешний API:

```python
from sage import process_document, ProcessingResult, Chunk, ContractFields

result = await process_document(src=Path("contract.docx"), work_dir=tmp)
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 1.1 | SAGE models | `packages/sage/sage/models.py`, `packages/sage/sage/__init__.py`, `packages/sage/tests/test_models.py` |
| 1.2 | LibreOffice conversion | `packages/sage/sage/conversion/{__init__.py, libreoffice.py}` |
| 1.3 | PDF detector + text extractor | `packages/sage/sage/pdf/{__init__.py, detector.py, text_extractor.py}`, тесты |
| 1.4 | OCR | `packages/sage/sage/pdf/ocr.py` |
| 1.5 | Normalizer | `packages/sage/sage/normalizer/{__init__.py, clean.py}`, тесты |
| 1.6 | Chunker | `packages/sage/sage/chunker/{__init__.py, split.py}`, тесты |
| 1.7 | LLM client + extract + summary | `packages/sage/sage/llm/{client.py, extract.py, summary.py}`, тесты с мок-клиентом |
| 1.8 | `process_document` orchestrator | `packages/sage/sage/process.py`, обновлённый `__init__.py`, тест |

## Критерии приёмки трека

- [ ] `from sage import process_document, ProcessingResult` работает.
- [ ] Пайплайн полностью стейтлес: ни одной зависимости от SQLAlchemy,
  FastAPI или persistence-слоёв SAGE-сервиса.
- [ ] Все pure-функции (chunker, normalizer, merge_fields) покрыты unit-тестами.
- [ ] LLM-зависимости тестируются через мок-клиент.
- [ ] Конвертация, OCR и tesseract-завязанные тесты помечены `pytest.mark.skipif`,
  если соответствующие бинарники отсутствуют в PATH.

## Что НЕ делаем

* Не возрождаем HTTP API, БД, persistence-слой SAGE-сервиса.
* Не пишем интеграционные тесты против настоящего LM Studio (только мок).
* Не меняем состав полей `ContractFields` — он зафиксирован в CLAUDE.md.
* Не вводим concurrency-абстракции сверх `asyncio` и `ThreadPoolExecutor`.

## Тесты

| Модуль | Что покрыть |
|--------|-------------|
| `models.py` | Создание каждой модели с минимальным набором полей; `model_dump()` round-trip. |
| `pdf/detector.py` | Текстовый PDF, скан-PDF, ЭДО-шум — мок pymupdf или fixture с тремя готовыми PDF. |
| `normalizer/clean.py` | Таблично: схлопывание whitespace, удаление повторяющихся header/footer (>60% страниц), нормализация page-маркеров. |
| `chunker/split.py` | Пустые страницы, одна гигантская страница, документ без заголовков, документ из одних заголовков, граница `max_chars`. |
| `llm/extract.py` | `merge_fields` left-prefer (table-driven), `extract_one` retry на `ValidationError`, fallback на all-None после второго фейла. |
| `process.py` | Все sub-step'ы замоканы; проверяется порядок вызовов и форма `ProcessingResult`. |

## Verification checklist

- [ ] `pytest packages/sage -v`
- [ ] `python -c "from sage import process_document, ProcessingResult, Chunk, ContractFields"`
- [ ] `rg -n "fastapi|sqlalchemy|alembic" packages/sage` ничего не находит.

---

## Промпты для агента

### PR 1.1 — SAGE models

```text
Role: ты — backend-инженер проекта ARGUS, готовишь модели данных для
извлечённого пакета `packages/sage`.

# Goal
Определить Pydantic-модели `Page`, `Chunk`, `ContractFields`,
`ExtractedDocument`, `ProcessingResult` строго по спецификации
`CLAUDE.md` → раздел «packages/sage — Key models». Реэкспортировать их из
`sage/__init__.py`.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- Источник истины полей: `CLAUDE.md` → «packages/sage — Document Processing
  Package» и «Key models».
- Никаких импортов из `app.*` или внешних SAGE-модулей.

# Success criteria
- Все 5 моделей — `pydantic.BaseModel` (или `dataclass` если поведение строго
  не требует валидации, но предпочтительно BaseModel).
- `Page(index: int, text: str, kind: Literal["text", "scan"])`.
- `Chunk(text, page_start, page_end, section_type: str | None,
  chunk_index: int, chunk_summary: str | None)`.
- `ContractFields` со всеми 21 полем из CLAUDE.md, каждое `Optional[str]`,
  default `None`.
- `ExtractedDocument(pages: list[Page], document_kind: Literal["text","scan"],
  chunks: list[Chunk])`.
- `ProcessingResult(chunks, fields, summary, pages, document_kind, partial)`.
- `from sage import Page, Chunk, ContractFields, ExtractedDocument,
  ProcessingResult` работает.
- Юнит-тест `tests/test_models.py`: создание каждой модели только с
  обязательными полями, `model_dump()` возвращает dict с `None` для
  необязательных.

# Constraints
- НЕ добавлять полей сверх перечисленных в CLAUDE.md.
- НЕ использовать `field_validator` / `model_validator` в этом PR.
- НЕ привязывать модели к БД.

# Output
- Полное содержимое `models.py`, обновлённый `__init__.py`, тест.
- Вывод `pytest packages/sage/tests/test_models.py -v`.

# Stop rules
- Если в CLAUDE.md какое-то поле неоднозначно — следуй буквальному списку и
  оставь Optional[str]; не выдумывай типов вроде `Decimal` для `amount`.
```

### PR 1.2 — LibreOffice conversion

```text
Role: ты — backend-инженер проекта ARGUS, портируешь конвертацию документов в
`packages/sage`.

# Goal
Реализовать `ensure_pdf(src: Path, work_dir: Path) -> Path` в
`packages/sage/sage/conversion/libreoffice.py`. Если входной файл уже PDF —
возвращать как есть. Иначе — конвертировать через `soffice --headless`.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- Существующий код конвертации лежит в SAGE-сервисе
  (`/Users/2madeira/DEV/PROJECTS/SAGE`) — используй как ориентир, но
  отвязывай от его инфраструктуры.
- Поддерживаемые входы: `.pdf`, `.doc`, `.docx`, `.rtf`, `.odt`.

# Success criteria
- Сигнатура: `async def ensure_pdf(src: Path, work_dir: Path) -> Path`.
- Если `src.suffix.lower() == ".pdf"` — функция возвращает `src` без вызова
  внешних процессов.
- Иначе запускает `asyncio.create_subprocess_exec("soffice", "--headless",
  "--convert-to", "pdf", "--outdir", str(work_dir), str(src))` с таймаутом
  120 секунд.
- На ненулевом exit code или таймауте — `raise ConversionError(stderr)`.
- `ConversionError(Exception)` экспортирован из модуля.
- Тест с моком `asyncio.create_subprocess_exec`: проверка команды, поведения
  при ненулевом exit, таймауте. Smoke-тест с реальным `soffice` — под
  `pytest.mark.skipif(not shutil.which("soffice"))`.

# Constraints
- НЕ использовать `subprocess.run` (нужен async).
- НЕ кэшировать результат между вызовами — функция чистая по параметрам.
- НЕ зависеть от внешнего state (текущий cwd и пр.).

# Output
- Содержимое `libreoffice.py` и теста.
- Вывод `pytest packages/sage/tests/test_conversion.py -v`.

# Stop rules
- Если SAGE-сервис использует другую утилиту (например `unoconv`) —
  предпочти `soffice --headless` и зафиксируй причину в Output.
```

### PR 1.3 — PDF detection + text extraction

```text
Role: ты — backend-инженер проекта ARGUS, портируешь PDF-детектор и
текстовый экстрактор в `packages/sage`.

# Goal
Реализовать `detect_kind(pdf_path) -> Literal["text", "scan"]` и
`extract_text_pages(pdf_path) -> list[Page]` в `packages/sage/sage/pdf/`,
взяв за основу логику из SAGE-сервиса.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- Исходный код: SAGE-сервис, модули определения типа PDF и извлечения текста.
- Pydantic-модель `Page` уже есть (PR 1.1).
- Пакет: pymupdf (импортируется как `fitz`).

# Success criteria
- `detect_kind(pdf_path: Path) -> Literal["text", "scan"]` использует три
  эвристики из SAGE: длина текста на странице, доля страниц с текстом,
  фильтр ЭДО-шума. Пороги — 1-в-1 из SAGE.
- `extract_text_pages(pdf_path: Path) -> list[Page]` — возвращает список
  `Page(index=i, text=page.get_text(), kind="text")` через pymupdf.
- Оба модуля синхронные — async не требуется.
- Юнит-тесты:
  * `detect_kind` с моком pymupdf для трёх кейсов (text-heavy, scan-heavy,
    ЭДО-noise).
  * `extract_text_pages` на fixture-PDF с известным текстом или моком
    pymupdf.

# Constraints
- НЕ менять пороги детектора по сравнению с SAGE без обоснования.
- НЕ добавлять извлечение метаданных, изображений и таблиц — только текст.
- НЕ открывать PDF дважды — один проход.

# Output
- Содержимое `detector.py`, `text_extractor.py`, тестов.
- Вывод `pytest packages/sage/tests/test_pdf.py -v`.

# Stop rules
- Если в SAGE детектор использует ML-модель — оставь только эвристики и
  зафиксируй упрощение в Output.
```

### PR 1.4 — OCR

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь OCR-шаг пайплайна.

# Goal
Реализовать `ocr_pages(pdf_path: Path) -> list[Page]` в
`packages/sage/sage/pdf/ocr.py`: рендер страниц в 300 DPI и pytesseract с
`lang="rus+eng"`.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- pymupdf уже подключён (PR 1.3). pytesseract в зависимостях `packages/sage`.

# Success criteria
- Сигнатура: `def ocr_pages(pdf_path: Path) -> list[Page]`.
- Каждая страница рендерится в PIL-изображение через `fitz` с DPI=300
  (`pix = page.get_pixmap(dpi=300)` → `PIL.Image.frombytes`).
- Распознавание идёт параллельно через `concurrent.futures.ThreadPoolExecutor`
  с `max_workers=os.cpu_count() or 2`.
- Возвращается `list[Page]` упорядоченный по `index`, `kind="scan"`.
- Smoke-тест помечен `pytest.mark.skipif(not
  shutil.which("tesseract"))`.

# Constraints
- НЕ обрабатывать страницы последовательно — нужен ThreadPool.
- НЕ предсказывать язык автоматически — фиксированный `rus+eng`.
- НЕ возвращать пустые страницы как None — пустая строка допустима.

# Output
- Содержимое `ocr.py` и тестов.
- Заметка про пиковое потребление памяти при 300 DPI.

# Stop rules
- Если памяти не хватает на больших PDF — упомяни проблему в Output, не
  пытайся снизить DPI без согласования.
```

### PR 1.5 — Normalizer

```text
Role: ты — backend-инженер проекта ARGUS, портируешь нормализацию текста.

# Goal
Реализовать `normalize_pages(pages: list[Page]) -> list[Page]`: схлопывание
whitespace, починка mojibake, удаление повторяющихся header/footer,
нормализация page-маркеров.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- Базовая логика — из SAGE-сервиса. Все этапы — pure Python (никаких внешних
  утилит).

# Success criteria
- Pure-функция: вход — список `Page`, выход — новый список `Page` той же
  длины, с очищенным `text`. Никаких side-effect'ов.
- Шаги (порядок):
  1. Удалить управляющие символы (кроме `\n` и `\t`).
  2. Починить распространённые mojibake-паттерны (карта из SAGE).
  3. Схлопнуть последовательности `\s+` в один пробел, сохранив `\n`.
  4. Найти строки, появляющиеся на >60% страниц, — удалить как header/footer.
  5. Нормализовать page-маркеры (если SAGE их использует) к единому виду.
- Юнит-тесты — table-driven: каждый шаг покрыт минимум тремя кейсами.

# Constraints
- НЕ использовать NLP-библиотек (spacy, nltk).
- НЕ менять порядок страниц.
- НЕ удалять полезный контент: эвристика >60% применяется только к
  идентичным строкам.

# Output
- Содержимое `clean.py` и тестов.
- Вывод `pytest packages/sage/tests/test_normalizer.py -v`.

# Stop rules
- Если карта mojibake из SAGE отсутствует или неполная — оставь
  минимальный набор (cp1251↔utf-8) и зафиксируй в Output.
```

### PR 1.6 — Chunker

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь чанкер документа.

# Goal
Реализовать `chunk_pages(pages: list[Page], max_chars: int = 2000) ->
list[Chunk]`: split по страницам → по markdown-заголовкам → семантический
fallback. Сохранять `page_start`/`page_end`. Чисто Python, без LLM.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- Pydantic-модель `Chunk` уже есть (PR 1.1).
- LLM сюда не подключается — это полностью детерминированная функция.

# Success criteria
- Алгоритм:
  1. Стартовый список — по одному чанку на страницу.
  2. Внутри каждого — split на markdown-заголовки (`^#{1,6}\s`), каждый
     заголовок → новый чанк.
  3. Если чанк всё ещё длиннее `max_chars`: семантический split по
     предложениям (`\.\s|\!\s|\?\s`), затем по абзацам (`\n\n`).
- `page_start`/`page_end` у каждого чанка корректны (в т.ч. при склейке
  multi-page-чанка).
- `chunk_index` — последовательный, начиная с 0.
- `section_type = "header"` если чанк начинается с heading-строки, иначе
  `"body"`.
- `chunk_summary = None`.
- Юнит-тесты:
  * пустой список страниц → пустой список чанков;
  * одна гигантская страница без заголовков → семантический fallback;
  * документ без заголовков → один чанк на страницу;
  * документ из одних заголовков → отдельный чанк на каждый;
  * проверка инварианта `page_start <= page_end`.

# Constraints
- НЕ вызывать LLM, embedding-модели или внешние сервисы.
- НЕ пересобирать `Page` — работаем только на уровне `Chunk`.
- НЕ нарушать порядок текста.

# Output
- Содержимое `split.py` и тестов.
- Вывод `pytest packages/sage/tests/test_chunker.py -v`.

# Stop rules
- Если SAGE использует другой алгоритм (например только семантический split
  без markdown) — следуй CLAUDE.md (page → headings → semantic) и зафиксируй.
```

### PR 1.7 — LLM client + extract + summary

```text
Role: ты — backend-инженер проекта ARGUS, реализуешь LLM-обвязку SAGE.

# Goal
Реализовать в `packages/sage/sage/llm/`:
- `LMStudioClient` — async-обёртка над OpenAI-совместимым chat-completions.
- `extract_one(client, chunk) -> ContractFields` с одной retry-итерацией на
  `ValidationError`.
- `merge_fields(left, right) -> ContractFields` — left-prefer.
- `summarize(client, pages) -> str` — map-reduce (per-page summary, затем
  reduce).

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- LLM-промпты — на русском языке, документы — русские контракты.
- Источник логики экстракции: SAGE-сервис.
- LM Studio выставляет endpoint `{LM_STUDIO_URL}/chat/completions`.
- Модель LLM передаётся через конструктор клиента (имя берётся из
  `LM_STUDIO_LLM_MODEL`).

# Success criteria
- `LMStudioClient(base_url: str, model: str, *, timeout: float = 60.0)`,
  метод `async chat(messages: list[dict], response_format: dict | None =
  None) -> str`.
- `extract_one(client, chunk) -> ContractFields`:
  1. Шлёт промпт, требующий строгий JSON, явно запрещающий выдумывать
     значения (отсутствует → `null`).
  2. Парсит JSON. Если `pydantic.ValidationError` — повторяет вызов один раз
     с приклеенным текстом ошибки.
  3. Если оба раза не получилось — возвращает `ContractFields()` (все None) и
     логирует warning.
- `merge_fields(left, right)` — по каждому полю: `left.f if left.f is not
  None else right.f`. Возвращает новый `ContractFields`.
- `summarize(client, pages) -> str`:
  1. Map: per-page summary в 1–2 предложения.
  2. Reduce: объединение в документ-level summary ≤500 символов.
- Юнит-тесты:
  * `merge_fields` table-driven (минимум 8 кейсов: оба None, оба заполнены,
    смешанные).
  * `extract_one` с моком клиента: успех с первого раза, успех с retry,
    fallback после двух фейлов.
  * `summarize` с моком клиента — проверяет map-reduce-цепочку.

# Constraints
- НЕ ходить в реальный LM Studio в тестах.
- НЕ менять состав полей `ContractFields`.
- НЕ кэшировать клиент глобально — клиент создаётся снаружи.
- Промпты должны явно требовать `null` для отсутствующих полей и запрещать
  «правдоподобные догадки».

# Output
- Содержимое `client.py`, `extract.py`, `summary.py` и тестов.
- Вывод `pytest packages/sage/tests/test_llm.py -v`.
- Полные тексты промптов (на русском) — отдельным блоком.

# Stop rules
- Если LM Studio API расходится с OpenAI-схемой (например requires `role:
  user` only) — адаптируй и зафиксируй разницу в Output.
- Если ContractFields содержит nested-структуры — не плоди их сейчас, оставь
  плоский dict как в CLAUDE.md.
```

### PR 1.8 — `process_document` orchestrator

```text
Role: ты — backend-инженер проекта ARGUS, собираешь итоговый pipeline SAGE.

# Goal
Реализовать `process_document(...)` в `packages/sage/sage/process.py`,
оркеструя все шаги PR 1.2–1.7. Реэкспортировать из `sage/__init__.py`.

# Context
- План трека: `docs/architecture/roadmap/01-track-1-sage-package.md`.
- CLAUDE.md → «packages/sage — Internal pipeline (steps 3–9)».
- Все sub-step'ы реализованы в предыдущих PR.

# Success criteria
- Сигнатура: `async def process_document(src: Path, work_dir: Path, *,
  llm_client: LMStudioClient | None = None) -> ProcessingResult`.
- Шаги в строгом порядке:
  1. `pdf_path = await ensure_pdf(src, work_dir)`.
  2. `kind = detect_kind(pdf_path)`.
  3. `pages = extract_text_pages(pdf_path) if kind == "text" else
     ocr_pages(pdf_path)`.
  4. `pages = normalize_pages(pages)`.
  5. `chunks = chunk_pages(pages)`.
  6. Для каждого `chunk` в `chunks`:
     `partial_fields_i = await extract_one(llm_client, chunk)`.
     Reduce через `merge_fields` (left-prefer, в порядке появления).
     `partial = any(extracted_returned_all_none)`.
  7. `summary = await summarize(llm_client, pages)`.
  8. Вернуть `ProcessingResult(chunks=chunks, fields=fields, summary=summary,
     pages=pages, document_kind=kind, partial=partial)`.
- Если `llm_client is None` — создаётся дефолтный `LMStudioClient` из env
  (`LM_STUDIO_URL`, `LM_STUDIO_LLM_MODEL`).
- Юнит-тест: каждый sub-step замокан, проверяется порядок вызовов и форма
  результата.

# Constraints
- НЕ обрабатывать ошибки — пусть пробрасываются вверх (вызывающий слой
  ARGUS пометит документ FAILED).
- НЕ читать БД, не писать файлов кроме `work_dir`.
- НЕ менять сигнатуры sub-step'ов.

# Output
- Содержимое `process.py`, обновлённый `__init__.py`, тест.
- Вывод `pytest packages/sage/tests/test_process.py -v`.

# Stop rules
- Если порядок шагов в SAGE-сервисе расходится с CLAUDE.md — следуй CLAUDE.md
  и зафиксируй.
```
