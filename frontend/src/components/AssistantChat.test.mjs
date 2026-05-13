import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import test from "node:test";

import ts from "typescript";

const require = createRequire(import.meta.url);
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { StaticRouter } = require("react-router-dom/server");

const srcDir = join(dirname(fileURLToPath(import.meta.url)), "..");
installTypeScriptRequireHook(srcDir);

const AssistantChat = require("./AssistantChat.tsx").default;
const {
  assistantUiStateFromResponse,
} = require("../utils/assistantUiState.ts");

test("direct search response renders chat timeline without a draft brief panel", () => {
  const uiState = assistantUiStateFromResponse([], responseFixture({
    message: "Нашел варианты в каталоге. Карточки ниже.",
    found_items: [foundItem()],
  }));

  const html = renderChat([uiState.assistantMessage]);

  assert.equal(uiState.interfaceMode, "chat_search");
  assert.equal(uiState.showDraftBriefPanel, false);
  assert.match(html, /Каталог в чате/);
  assert.doesNotMatch(html, /Черновик брифа/);
});

test("chat-search clarification stays inline without a catalog empty state", () => {
  const uiState = assistantUiStateFromResponse([], clarificationResponseFixture());

  const html = renderChat([uiState.assistantMessage]);

  assert.equal(uiState.interfaceMode, "chat_search");
  assert.equal(uiState.showDraftBriefPanel, false);
  assert.equal(uiState.assistantMessage.foundItems, undefined);
  assert.match(html, /Уточните город и формат задачи по свету/);
  assert.doesNotMatch(html, /Черновик брифа/);
  assert.doesNotMatch(html, /В каталоге нет подходящих строк/);
  assert.doesNotMatch(html, /концепц/iu);
  assert.doesNotMatch(html, /цель мероприятия/iu);
});

test("inline catalog cards render facts from found_items fields", () => {
  const uiState = assistantUiStateFromResponse([], responseFixture({
    message: "Карточки ниже.",
    found_items: [foundItem()],
  }));

  const html = renderChat([uiState.assistantMessage]);

  assert.match(html, /ООО Световой Цех/);
  assert.match(html, /Екатеринбург/);
  assert.match(html, /день/);
  assert.match(html, /15000\.00/);
  assert.match(html, /Световой комплект для сцены из строки прайса/);
});

test("empty chat-search results show no matching catalog rows without alternatives", () => {
  const uiState = assistantUiStateFromResponse([], responseFixture({
    message: "По этому запросу ничего не нашел.",
    found_items: [],
  }));

  const html = renderChat([uiState.assistantMessage]);

  assert.match(html, /В каталоге нет подходящих строк по этому запросу/);
  assert.doesNotMatch(html, /альтернатив/iu);
  assert.doesNotMatch(html, /лучший вариант/iu);
});

function renderChat(messages) {
  return renderToStaticMarkup(
    React.createElement(
      StaticRouter,
      { location: "/" },
      React.createElement(AssistantChat, {
        messages,
        input: "",
        loading: false,
        error: null,
        latestRouter: null,
        selectedItemIds: [],
        onInputChange: () => undefined,
        onSend: async () => undefined,
        onSelectedItemIdsChange: () => undefined,
      }),
    ),
  );
}

function responseFixture(overrides) {
  return {
    session_id: "00000000-0000-0000-0000-000000000000",
    message: "Карточки ниже.",
    ui_mode: "chat_search",
    router: {
      intent: "supplier_search",
      confidence: 0.92,
      known_facts: {},
      missing_fields: [],
      should_search_now: true,
      search_query: "свет Екатеринбург",
      brief_update: emptyBrief(),
      interface_mode: "chat_search",
      workflow_stage: "searching",
      reason_codes: ["direct_catalog_search_detected"],
      search_requests: [],
      tool_intents: ["search_items"],
      clarification_questions: [],
      user_visible_summary: null,
    },
    action_plan: {
      interface_mode: "chat_search",
      workflow_stage: "searching",
      tool_intents: ["search_items"],
      search_requests: [],
      verification_targets: [],
      item_detail_ids: [],
      render_requested: false,
      missing_fields: [],
      clarification_questions: [],
      skipped_actions: [],
    },
    brief: emptyBrief(),
    found_items: [],
    verification_results: [],
    rendered_brief: null,
    ...overrides,
  };
}

function clarificationResponseFixture() {
  return responseFixture({
    message: "Уточните город и формат задачи по свету: оборудование, монтаж или операторская работа.",
    found_items: [],
    router: {
      intent: "supplier_search",
      confidence: 0.86,
      known_facts: {},
      missing_fields: ["city", "task_format"],
      should_search_now: false,
      search_query: null,
      brief_update: emptyBrief(),
      interface_mode: "chat_search",
      workflow_stage: "search_clarifying",
      reason_codes: ["direct_catalog_search_detected"],
      search_requests: [],
      tool_intents: [],
      clarification_questions: [
        "Уточните город и формат задачи по свету: оборудование, монтаж или операторская работа.",
      ],
      user_visible_summary: null,
    },
    action_plan: {
      interface_mode: "chat_search",
      workflow_stage: "search_clarifying",
      tool_intents: [],
      search_requests: [],
      verification_targets: [],
      item_detail_ids: [],
      render_requested: false,
      missing_fields: ["city", "task_format"],
      clarification_questions: [
        "Уточните город и формат задачи по свету: оборудование, монтаж или операторская работа.",
      ],
      skipped_actions: [],
    },
  });
}

function foundItem() {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    score: 0.87,
    name: "Световой комплект",
    category: "Свет",
    unit: "день",
    unit_price: "15000.00",
    supplier: "ООО Световой Цех",
    supplier_city: "Екатеринбург",
    source_text_snippet: "Световой комплект для сцены из строки прайса",
    source_text_full_available: true,
    match_reason: {
      code: "semantic",
      label: "Семантическое совпадение",
    },
    result_group: "свет",
    matched_service_category: "свет",
    matched_service_categories: ["свет"],
  };
}

function emptyBrief() {
  return {
    event_type: null,
    event_goal: null,
    concept: null,
    format: null,
    city: null,
    date_or_period: null,
    audience_size: null,
    venue: null,
    venue_status: null,
    venue_constraints: [],
    duration_or_time_window: null,
    event_level: null,
    budget: null,
    budget_total: null,
    budget_per_guest: null,
    budget_notes: null,
    catering_format: null,
    technical_requirements: [],
    service_needs: [],
    required_services: [],
    must_have_services: [],
    nice_to_have_services: [],
    selected_item_ids: [],
    constraints: [],
    preferences: [],
    open_questions: [],
  };
}

function installTypeScriptRequireHook(baseDir) {
  const previousTs = require.extensions[".ts"];
  const previousTsx = require.extensions[".tsx"];

  const loader = (module, filename) => {
    if (!filename.startsWith(baseDir)) {
      const previous = filename.endsWith(".tsx") ? previousTsx : previousTs;
      if (previous !== undefined) {
        previous(module, filename);
        return;
      }
    }

    const source = readFileSync(filename, "utf8");
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    });
    module._compile(outputText, filename);
  };

  require.extensions[".ts"] = loader;
  require.extensions[".tsx"] = loader;
}
