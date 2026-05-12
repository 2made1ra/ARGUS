# Event Brief E2E Scenario Phase Prompts

Готовые промпты для пофазного выполнения
[`08-event-brief-e2e-scenario.md`](../catalog-first-refactor/08-event-brief-e2e-scenario.md).

Промпты составлены под `gpt-5.5` по принципам OpenAI Prompt Guidance:

- начинать с результата и критериев успеха;
- отделять стабильный контекст от конкретной задачи фазы;
- задавать явные ограничения, stop conditions и формат ответа;
- требовать проверяемые контракты вместо свободной интерпретации;
- дробить реализацию на малые вертикальные срезы;
- не просить скрытые рассуждения, а просить краткое техническое обоснование решений.

Источник: <https://developers.openai.com/api/docs/guides/prompt-guidance>

## Как Использовать

1. Используй один промпт на одну сессию, ветку или PR.
2. Не запускай следующую фазу, пока текущая не реализована и не проверена.
3. Для UX-кода сначала прочитай текущую структуру `frontend/`; не придумывай компоненты и API-клиент без инспекции репозитория.
4. Для backend-contract фаз сверяйся с
   [`07-event-brief-assistant-orchestrator.md`](../catalog-first-refactor/07-event-brief-assistant-orchestrator.md).
5. Если backend ещё не отдаёт нужные поля, реализуй тонкий совместимый frontend fallback или зафиксируй contract gap в тесте/документе. Не подменяй backend факты моками в production UI.

## Общий Блок Для Любой Фазы

Добавляй этот блок в начало фазового промпта, если агент не видит текущий контекст репозитория:

```text
Ты работаешь в репозитории ARGUS.

Goal:
Выполни только указанную фазу UX/e2e-плана event-brief assistant. Цель продукта:
ARGUS assistant is an event-brief copilot with catalog-backed supplier search, not a general chat agent.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/search.md
- docs/api/openapi.yaml
- docs/plans/catalog-first-refactor/07-event-brief-assistant-orchestrator.md
- docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md

Inspect before editing:
- frontend/package.json
- frontend/src
- backend/app/features/assistant
- backend/tests/features/assistant

Non-negotiable constraints:
- There are two UX flows:
  1. brief_workspace opens only when the user explicitly creates, prepares, plans or organizes an event.
  2. chat_search stays a simple chat when the user only searches for a contractor, supplier, item or price row.
- Chat is always the primary interaction surface.
- Brief panel must not open in chat_search unless the user asks to create or save an event brief.
- Catalog facts must appear through found_items/cards/tables, not unchecked assistant prose.
- Found candidates are not selected proposal rows until selected_item_ids exists.
- Candidate references such as "второй вариант" and "найденных подрядчиков" require visible_candidates, candidate_item_ids or selected_item_ids.
- Registry active status is not event-date availability, recommendation or proof of an active agency contract.
- Do not add autonomous multi-turn agent loops.
- Do not commit, push or open a PR unless explicitly asked.

Implementation style:
- Use TDD for behavior changes: focused failing tests first, then implementation.
- Keep UI state explicit: interface_mode, brief, found_items, visible_candidates, selected_item_ids, verification_results and rendered_brief.
- Keep frontend presentation separate from assistant message text.
- Preserve existing search and drill-down UX unless this phase explicitly changes it.

Final response format:
- Changed files grouped by layer.
- User-visible behavior added.
- Verification commands run and exact results.
- Skipped checks or blockers.
- Any behavior intentionally left for a later phase.
```

## MVS-UX Prompt: Two Flow Shell

```text
Выполни минимальный UX-срез из docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md.

Outcome:
The assistant screen can choose between event-brief workspace and chat-only catalog search based on backend/interface state, without implementing every later panel.

Scope:
- Add or wire interface_mode handling for brief_workspace and chat_search.
- In brief_workspace, show chat plus a draft brief panel with known fields and open questions.
- In chat_search, show a single chat timeline with inline catalog cards and no draft brief panel.
- Keep found_items visually separate from assistant prose.
- Add request context plumbing for visible_candidates and candidate_item_ids if result cards already exist.

Out of scope:
- Full supplier verification UI.
- Full final brief renderer UI.
- Frontend redesign outside assistant/search surfaces.
- Real external verification providers.

Required behavior:
- “Нужно организовать корпоратив на 120 человек в Екатеринбурге” opens brief_workspace when the backend marks event creation intent.
- “Найди подрядчика по свету в Екатеринбурге” stays chat_search and does not show a draft brief panel.
- Existing catalog cards remain evidence-backed and are not restated as facts inside the assistant message.
- Missing backend fields use safe empty states, not fabricated UI content.

Tests:
- Add or update frontend unit/component tests for mode selection.
- Add or update API contract types if needed.
- Keep tests independent from Postgres, Qdrant and LM Studio.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if backend response shape cannot distinguish brief_workspace from chat_search. Document the exact missing contract instead of guessing from message text alone.
- Stop after the two-flow shell works. Do not implement verification or final brief UI in this session.
```

## Phase UX-0 Prompt: Response Contract Inventory

```text
Выполни Phase UX-0 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Response Contract Inventory.

Outcome:
Document and, where appropriate, test the response fields the frontend needs for the two UX flows before UI implementation expands.

Scope:
- Inspect current assistant backend response DTOs and frontend API types.
- Compare current fields with the UX plan fields:
  - message
  - ui_mode or interface_mode
  - router/action diagnostics
  - brief
  - found_items
  - search_requests or grouped result metadata
  - visible_candidates
  - candidate_item_ids
  - selected_item_ids
  - verification_results
  - rendered_brief
- Update docs or type comments only if this is a docs-only phase.
- If code changes are allowed in this phase, add minimal type definitions without changing runtime behavior.

Out of scope:
- Implementing the full orchestrator.
- Implementing frontend layouts.
- Adding real search, verification or rendering behavior.

Required output:
- A concise contract gap list:
  - already available fields;
  - missing fields;
  - fields that need backwards-compatible aliases;
  - fields that must not be inferred from assistant prose.
- A recommendation for the smallest next implementation slice.

Verification to run:
npm run build
uv run --project backend pytest backend/tests/features/assistant -q

Stop conditions:
- Stop if the response contract differs between OpenAPI, backend DTOs and frontend API types. Report the conflict with file paths and proposed owner.
```

## Phase UX-1 Prompt: Interface Mode Routing In UI

```text
Выполни Phase UX-1 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Interface Mode Routing In UI.

Outcome:
The frontend chooses the correct assistant layout from explicit backend state, not from keyword guessing in the UI.

Scope:
- Add UI state handling for interface_mode values:
  - brief_workspace
  - chat_search
- Keep chat_search as the default if the backend omits the field.
- In brief_workspace, render chat plus a draft brief shell.
- In chat_search, render chat only.
- Add tests for event-creation and direct-search responses.

Required behavior:
- Direct contractor search never opens the draft brief panel unless backend/user explicitly switches to brief_workspace.
- Event creation/planning intent opens the brief workspace.
- Existing found_items rendering still works in both modes.

Test cases:
- Response with interface_mode=brief_workspace and non-empty brief shows draft brief panel.
- Response with interface_mode=chat_search and found_items shows inline cards only.
- Response without interface_mode falls back to chat_search for compatibility.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if the existing frontend has no assistant surface to mount this behavior. Identify the closest current component and propose the smallest integration point.
```

## Phase UX-2 Prompt: Draft Brief Panel

```text
Выполни Phase UX-2 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Draft Brief Panel.

Outcome:
In brief_workspace mode, the user can see the event brief grow as structured state instead of reading all state from chat prose.

Scope:
- Render a draft brief panel with these fields when present:
  - event_type
  - event_goal
  - concept
  - format
  - city
  - date_or_period
  - audience_size
  - venue_status
  - venue_constraints
  - budget_total
  - budget_per_guest
  - event_level
  - service blocks
  - selected items
  - open questions
- Unknown values must appear as open questions or empty states, not hidden fabricated values.
- Keep panel compact and scannable for repeated manager use.

Out of scope:
- Editing brief fields manually unless an existing pattern already supports it.
- Full final brief rendering.
- Turning found_items into selected items automatically.

Required behavior:
- Intake response for “Нужно организовать корпоратив на 120 человек в Екатеринбурге” shows corporate/city/audience in the panel and date/venue/budget/concept as open questions.
- Slot-filling response for “Площадка уже есть, монтаж только ночью, бюджет около 2 млн” updates venue/budget/constraints without launching catalog cards.

Tests:
- Add component tests for known fields.
- Add component tests for unknown/open-question rendering.
- Add regression test that found_items are not shown as selected items.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if brief DTO names conflict with backend plan 07. Add a compatibility mapper instead of scattering aliases across components.
```

## Phase UX-3 Prompt: Chat-Only Catalog Search

```text
Выполни Phase UX-3 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Chat-Only Catalog Search.

Outcome:
Users who only want to search for a contractor, supplier, item or price row get a compact chat search experience with inline catalog evidence.

Scope:
- Render chat_search as a single chat timeline.
- Show assistant clarification questions inline.
- Render found_items as inline catalog cards below the assistant message.
- Group cards by service category when grouped metadata exists; otherwise keep a flat compatible list.
- Keep result facts in cards, not duplicated in assistant prose.

Out of scope:
- Draft brief panel.
- Final event brief rendering.
- Verification UI beyond a safe empty verification state if verification_results already exist.

Required behavior:
- “Найди подрядчика по свету в Екатеринбурге” shows chat_search layout and light-related found_items when backend returns them.
- “Есть кейтеринг до 2500 на гостя?” asks search-specific clarification if backend says data is missing.
- Chat-search clarifications must not ask full event-intake questions such as concept or final event goal unless user switches to event planning.

Tests:
- Direct search response renders no draft brief panel.
- Inline cards display supplier, city, unit, price and source snippet only from found_items fields.
- Empty found_items response says the catalog has no matching rows without inventing alternatives.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if inline catalog cards would duplicate a component already used elsewhere. Reuse the existing card/table component where possible.
```

## Phase UX-4 Prompt: Candidate Context And Selection

```text
Выполни Phase UX-4 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Candidate Context And Selection.

Outcome:
The UI sends explicit candidate context so backend can resolve phrases like “второй вариант”, “первые два” and “найденных подрядчиков” without hidden server memory.

Scope:
- Build visible_candidates from currently rendered candidate cards.
- Include ordinal, item_id and service_category in the next assistant request.
- Include candidate_item_ids for currently visible result sets.
- Wire selection controls so selected item ids are explicit.
- Show selected items separately from found candidates.

Out of scope:
- Backend selection policy unless the endpoint already supports it.
- Supplier verification execution.
- Final rendered brief.

Required behavior:
- Clicking/selecting a candidate creates or sends selected_item_ids through the agreed request shape.
- “Добавь в подборку второй вариант” can work only when visible_candidates includes ordinal 2.
- If no candidate context exists, UI/backend flow should ask clarification rather than guessing.

Tests:
- visible_candidates is built from rendered result order.
- candidate_item_ids contains all visible candidate ids.
- selected items render in a separate selected list and are not confused with found_items.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if backend request DTO does not accept visible_candidates or candidate_item_ids. Add a contract test or docs note and keep UI state ready for the field.
```

## Phase UX-5 Prompt: Supplier Verification UX

```text
Выполни Phase UX-5 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Supplier Verification UX.

Outcome:
The user can ask to verify candidates and see explicit verification results without confusing legal registry status with event availability or recommendation.

Scope:
- Render verification_results as a separate panel, drawer or inline section depending on current mode.
- Show supplier name, INN, status, source, checked timestamp and risk flags when present.
- Show manual/not_verified states as valid states.
- In chat_search, show verification status inline near cards.
- In brief_workspace, show verification as part of the event workspace.

Out of scope:
- Real external verification adapter.
- Legal recommendations or scoring.
- Treating registry active status as availability on event date.

Required behavior:
- “Проверь найденных подрядчиков” with candidate context shows verification results returned by backend.
- The same message without candidate context asks which candidates to verify and shows no invented results.
- Supplier rows without INN are marked as needing manual verification.
- Duplicate INNs should appear as one supplier verification result mapped to related item cards when backend returns that mapping.

Tests:
- status=not_verified renders as a neutral/manual state.
- status=active label says registry/legal active, not “available” or “recommended”.
- Empty verification_results with clarification message does not show stale previous statuses for new candidates.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if frontend has no reliable item-id mapping from found_items to verification_results. Document the missing backend mapping instead of matching by display name.
```

## Phase UX-6 Prompt: Rendered Event Brief UX

```text
Выполни Phase UX-6 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Rendered Event Brief UX.

Outcome:
The final event brief is shown as a structured artifact with evidence-backed selected candidates, verification summary and open questions.

Scope:
- Render rendered_brief when backend returns it.
- Support sections:
  1. Основная информация
  2. Концепция и уровень
  3. Площадка и ограничения
  4. Блоки услуг
  5. Подборка кандидатов
  6. Проверка подрядчиков
  7. Бюджетные заметки
  8. Открытые вопросы
- Keep rendered brief separate from the chat timeline while preserving the triggering assistant message.
- Show found candidates as “найдены, но не выбраны” when selected_item_ids is empty.

Out of scope:
- Export to PDF/DOCX unless explicitly requested.
- LLM rewriting of catalog facts.
- Budget calculation from unselected found_items.

Required behavior:
- “Сформируй итоговый бриф” displays rendered_brief in brief_workspace.
- Missing date/concept/budget remains in open questions.
- Candidate summary uses selected items only; found-only rows are labeled as not selected.
- Verification summary uses verification_results only.

Tests:
- Rendered sections appear in the specified order.
- Empty selected_item_ids does not produce selected supplier lines.
- Budget notes do not use found_items as an estimate without selected rows and explicit quantities.

Verification to run:
npm run build
npm test -- --run

Stop conditions:
- Stop if backend does not yet return rendered_brief. Add a typed unavailable-render state and a contract test, but do not fabricate final brief content in frontend.
```

## Phase UX-7 Prompt: Scenario Acceptance And Regression Tests

```text
Выполни Phase UX-7 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Scenario Acceptance And Regression Tests.

Outcome:
The primary event-brief flow and secondary chat-only search flow are covered by scenario-level tests that prevent UX regressions.

Scope:
- Add frontend or integration tests for these scenarios:
  - intake case
  - direct search case
  - mixed search case
  - venue constraint case
  - venue constraint without search case
  - selection case
  - verification case
  - verification without context case
  - render brief case
- Use fake backend responses or test fixtures where appropriate.
- Keep tests deterministic and independent from external services.

Required assertions:
- Event creation opens brief_workspace.
- Direct search stays chat_search.
- Venue constraint can infer planning implications without catalog cards.
- Candidate references require visible_candidates/candidate_item_ids/selected_item_ids.
- Verification results are separate from assistant prose.
- Rendered brief does not treat found_items as selected items.

Verification to run:
npm run build
npm test -- --run
uv run --project backend pytest backend/tests/features/assistant -q

Stop conditions:
- Stop if the test framework cannot run in the local environment. Report the exact command, failure output and the closest completed static/type check.
```

## Phase UX-8 Prompt: Documentation And Handoff

```text
Выполни Phase UX-8 для docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md: Documentation And Handoff.

Outcome:
The implemented UX behavior is documented clearly enough for the next backend or frontend phase to continue without rediscovering contracts.

Scope:
- Update docs only where implementation has made the docs stale.
- Document the two UX flows:
  - brief_workspace for explicit event creation/planning.
  - chat_search for direct contractor/catalog search.
- Document request context requirements:
  - visible_candidates
  - candidate_item_ids
  - selected_item_ids
- Document evidence boundaries:
  - message is not the source of catalog facts.
  - found_items are candidates, not selected proposal rows.
  - verification_results are legal/registry evidence, not availability or recommendation.
- Link to the backend orchestrator plan 07 and prompt file 07 where useful.

Out of scope:
- Rewriting unrelated architecture docs.
- Creating marketing copy.
- Adding speculative future UX not covered by plan 08.

Verification to run:
rg -n "brief_workspace|chat_search|visible_candidates|candidate_item_ids|selected_item_ids|verification_results|rendered_brief" docs/plans docs/agent frontend/src backend/app/features/assistant
git diff --check

Stop conditions:
- Stop if docs disagree with implemented API contracts. Update the more specific plan doc and call out the remaining owner instead of hiding the mismatch.
```
