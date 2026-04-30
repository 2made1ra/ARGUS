# 10 — Track 10: Test frontend (React + Vite) *(приоритет №3)*

**Зависит от:** Track 9
**Разблокирует:** конец MVP
**Источник истины:** [`../../../ARCHITECTURE_ROADMAP.md`](../../../ARCHITECTURE_ROADMAP.md) — раздел «Track 10 — Test frontend (React + Vite, minimal)»

## Контекст

Минимально функциональный фронтенд для **тестирования** end-to-end
пайплайна и UX drill-down-поиска. Не продакшен. Прод-фронтенд будет
сделан отдельным проектом после MVP. Стек: React 18 + Vite + TypeScript,
без UI-библиотек (только `react-router-dom`).

После завершения трека человек может:
- загрузить документ;
- видеть прогресс пайплайна (SSE);
- листать контрагентов;
- использовать drill-down-поиск.

## Целевое состояние

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── App.css
    ├── api.ts
    ├── pages/
    │   ├── Home.tsx
    │   ├── ContractorPage.tsx
    │   └── DocumentPage.tsx
    └── components/
        ├── UploadForm.tsx
        ├── DocumentStatus.tsx
        ├── SearchBar.tsx
        ├── ContractorSearchResults.tsx
        ├── DocumentResults.tsx
        └── ChunkResults.tsx
```

## План работы

| PR | Заголовок | Файлы |
|----|-----------|-------|
| 10.1 | Vite + React skeleton | `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/{main, App, App.css, api}.tsx`, `src/pages/{Home, ContractorPage, DocumentPage}.tsx` (плейсхолдеры) |
| 10.2 | Upload + status (SSE) | `components/UploadForm.tsx`, `components/DocumentStatus.tsx`, обновлённые `Home.tsx` и `DocumentPage.tsx` |
| 10.3 | Drill-down search UI | `components/{SearchBar, ContractorSearchResults, DocumentResults, ChunkResults}.tsx`, обновлённые pages |

## Критерии приёмки трека

- [ ] `npm install && npm run dev` поднимает `http://localhost:5173`.
- [ ] С запущенным backend'ом из Track 9 можно: загрузить документ →
  увидеть переходы статусов → дойти до INDEXED → найти его через поиск
  на главной странице.
- [ ] Drill-down: клик по контрагенту → его страница; клик по документу
  → страница документа со встроенным поиском по чанкам.

## Что НЕ делаем

* Не подключаем UI-библиотеки (Material, Chakra, Tailwind) — обычный CSS.
* Не делаем auth.
* Не делаем error-boundary'ы и пуш-уведомления.
* Не делаем тестов (Vitest, Playwright) — это post-MVP.

## Verification checklist

- [ ] `cd frontend && npm install && npm run dev`
- [ ] Загрузить `sample.pdf`, дождаться INDEXED.
- [ ] На главной — поиск даёт хотя бы один результат.
- [ ] Drill-down работает на двух уровнях ниже.

---

## Промпты для агента

### PR 10.1 — Vite + React skeleton

```text
Role: ты — frontend-инженер проекта ARGUS, поднимаешь минимальный SPA для
тестирования backend'а.

# Goal
Создать структуру `frontend/` с Vite + React 18 + TypeScript +
react-router-dom. Три плейсхолдер-роута (`/`, `/contractors/:id`,
`/documents/:id`). Тонкий API-клиент над `fetch`.

# Context
- План трека: `docs/architecture/roadmap/10-track-10-test-frontend.md`.
- Backend: Track 9 (`http://localhost:8000`).
- Стек: React 18, Vite 5, TypeScript 5, `react-router-dom` 6. Никаких
  других библиотек.

# Success criteria
- `package.json`:
  * scripts: `"dev": "vite"`, `"build": "tsc -b && vite build"`,
    `"preview": "vite preview"`.
  * deps: react, react-dom, react-router-dom.
  * devDeps: vite, @vitejs/plugin-react, typescript, @types/react,
    @types/react-dom.
- `vite.config.ts`: дефолтный конфиг с `@vitejs/plugin-react`. Порт 5173.
- `tsconfig.json`: target ES2022, strict, jsx=react-jsx.
- `index.html` с `<div id="root">`.
- `src/main.tsx`: рендер `<BrowserRouter><App/></BrowserRouter>`.
- `src/App.tsx`: `<Routes>` с тремя плейсхолдер-страницами.
- `src/api.ts`:
  * `const API_URL = import.meta.env.VITE_API_URL ??
    "http://localhost:8000"`.
  * Типизированные функции: `getDocument(id)`, `listDocuments()`,
    `getContractor(id)`, `searchContractors(q)`,
    `searchDocumentsForContractor(id, q)`,
    `searchWithinDocument(id, q)`. (Использования будут в PR 10.2/10.3.)
- `src/App.css`: минимальный layout (max-width 960px, по центру,
  `font-family: system-ui`).
- `npm install` отрабатывает без ошибок; `npm run dev` поднимает
  страницу.

# Constraints
- НЕ подключать UI-библиотек.
- НЕ подключать state-managers (Redux, Zustand) — `useState` достаточно.
- НЕ подключать react-query — простой `fetch` через api.ts.
- НЕ подключать ESLint в этом PR (можно отдельно post-MVP).

# Output
- Содержимое всех файлов.
- Вывод `npm install` (без ошибок).
- Скриншот или текст «✓ http://localhost:5173/ открывается, видна
  заголовок-заглушка».

# Stop rules
- Если CORS на backend'е не разрешает `localhost:5173` — это уже сделано
  в Track 9 PR 9.3; если нет — не правь backend, зафиксируй замечание в
  Output.
```

### PR 10.2 — Upload + status (SSE)

```text
Role: ты — frontend-инженер проекта ARGUS, реализуешь UX загрузки
документа и наблюдения за прогрессом.

# Goal
Добавить компонент `UploadForm` на главной странице (POST на
`/documents/upload`) и компонент `DocumentStatus` на странице документа
(подписка на SSE `/documents/{id}/stream`, рендер stepper'а статусов).

# Context
- План трека: `docs/architecture/roadmap/10-track-10-test-frontend.md`.
- Скелет — PR 10.1.
- Backend Endpoints:
  * `POST /documents/upload` (multipart, поле `file`).
  * `GET /documents/{id}` → DocumentDTO.
  * `GET /documents/{id}/stream` → SSE.
  * `GET /documents/{id}/facts` → DocumentFactsDTO.

# Success criteria
- `components/UploadForm.tsx`:
  * `<input type="file">` + кнопка «Загрузить».
  * При сабмите: `fetch("/documents/upload", { method: "POST", body:
    formData })` → ожидать 202 + `{document_id}` → `navigate(
    "/documents/" + id)`.
  * Показать в форме error message при non-2xx ответе.
- `pages/Home.tsx`:
  * Заголовок «ARGUS — тестовый интерфейс».
  * `UploadForm` сверху.
  * (PR 10.3 добавит SearchBar.)
- `components/DocumentStatus.tsx`:
  * Принимает `documentId: string`.
  * Открывает `EventSource("/documents/{id}/stream")`.
  * Рендерит stepper: QUEUED → PROCESSING → RESOLVING → INDEXING →
    INDEXED. Текущий статус подсвечен. На FAILED — красная плашка с
    `error_message`.
  * При получении INDEXED или FAILED закрывает EventSource.
- `pages/DocumentPage.tsx`:
  * При маунте загружает `getDocument(id)` и `getDocumentFacts(id)`.
  * Рендерит `DocumentStatus`.
  * Когда статус INDEXED — показывает блоки `Поля`, `Summary`,
    `Key points` (плоский список из `DocumentFactsDTO`).
- При ручном тестировании: загрузка `.pdf` или `.docx` показывает
  переходы статусов в реальном времени.

# Constraints
- НЕ использовать polling вместо SSE.
- НЕ хранить EventSource в Context — локальный useEffect достаточно.
- НЕ блокировать UI на время аплоада — спиннер/disabled у кнопки.

# Output
- Содержимое всех изменённых/новых файлов.
- Скриншоты или текстовое описание ручного прогона: «загрузил X →
  увидел статусы Y → отрисовался summary Z».

# Stop rules
- Если EventSource в браузере падает на CORS — попроси Track 9 проверить,
  что CORS разрешает `Cache-Control` и `text/event-stream`.
- Если backend ещё не INDEXED'ит документ из-за отсутствия LLM —
  тестируй частичный путь (QUEUED → PROCESSING → FAILED) и зафиксируй в
  Output.
```

### PR 10.3 — Drill-down search UI

```text
Role: ты — frontend-инженер проекта ARGUS, добавляешь UX drill-down-
поиска.

# Goal
Реализовать три поисковых интерфейса: глобальный (главная), по
контрагенту, внутри документа.

# Context
- План трека: `docs/architecture/roadmap/10-track-10-test-frontend.md`.
- Backend endpoints:
  * `GET /search?q=` → `ContractorSearchResult[]`.
  * `GET /contractors/{id}` → профиль.
  * `GET /contractors/{id}/documents` → список документов.
  * `GET /contractors/{id}/search?q=` → `DocumentSearchResult[]`.
  * `GET /documents/{id}/search?q=` → `WithinDocumentResult[]`.

# Success criteria
- `components/SearchBar.tsx`: переиспользуемый input + button. Принимает
  `onSearch(query)`.
- `components/ContractorSearchResults.tsx`: список карточек контрагентов
  (имя, snippet, score, count). Клик → `navigate("/contractors/" + id)`.
- `components/DocumentResults.tsx`: список документов (title, date,
  matched_chunks с page и snippet). Клик → `navigate("/documents/" +
  id)`.
- `components/ChunkResults.tsx`: список чанков (page_start–page_end,
  section_type, snippet, score).
- `pages/Home.tsx`:
  * `SearchBar` под `UploadForm`.
  * `ContractorSearchResults` после поиска.
- `pages/ContractorPage.tsx`:
  * Шапка: имя контрагента, ИНН/КПП.
  * Список документов (первые 20, без пагинации).
  * `SearchBar` (внутри контрагента) → `DocumentResults`.
- `pages/DocumentPage.tsx` (расширяет PR 10.2):
  * Снизу — `SearchBar` → `ChunkResults`.
- Подсветка совпадений query в snippet'е: простой split-and-bold по
  подстроке без библиотек. Дополнительно — escape HTML.

# Constraints
- НЕ городить highlight через regex — простой `split(query)`. Регистр —
  case-insensitive.
- НЕ кэшировать результаты — каждый запрос — свежий fetch.
- НЕ делать пагинацию — `limit=20` в каждом запросе.

# Output
- Содержимое всех изменённых/новых файлов.
- Скриншоты или описание сценария: «ввёл «штрафы» → нашёл контрагента
  X → перешёл, увидел договор Y → перешёл, нашёл фрагмент Z на стр. N».

# Stop rules
- Если backend возвращает поля DTO с другими названиями — обнови
  типизацию в `api.ts` и зафиксируй; не правь backend.
```

---

## После Track 10 — конец MVP

После мержа PR 10.3 ARGUS поддерживает полный happy-path из CLAUDE.md:
загрузка → SAGE → факты → резолв контрагента → индексация → drill-down
поиск. Всё, что после — post-MVP, описано в корневом
`ARCHITECTURE_ROADMAP.md` («Post-MVP»).
