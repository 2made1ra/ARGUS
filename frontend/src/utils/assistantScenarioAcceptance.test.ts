import type {
  ActionPlan,
  AssistantInterfaceMode,
  BriefState,
  EventBriefWorkflowState,
  FoundItem,
  RenderedEventBrief,
  RouterDecision,
  RouterIntent,
  SupplierVerificationResult,
} from "../api.ts";
import { assistantUiStateFromResponse } from "./assistantUiState.ts";
import type { AssistantResponseForUi } from "./assistantUiState.ts";
import { buildAssistantChatRequest } from "./assistantRequest.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    deepStrictEqual: (actual: unknown, expected: unknown) => void;
    equal: (actual: unknown, expected: unknown) => void;
    match: (actual: string, expected: RegExp) => void;
    doesNotMatch: (actual: string, expected: RegExp) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

const catering = foundItem(
  "00000000-0000-0000-0000-000000000001",
  "Фуршет на 120 гостей",
  "кейтеринг",
);
const light = foundItem(
  "00000000-0000-0000-0000-000000000002",
  "Световой комплект",
  "свет",
);
const truss = foundItem(
  "00000000-0000-0000-0000-000000000003",
  "Ground support ферма",
  "сценические конструкции",
);

const intakeState = assistantUiStateFromResponse(
  [],
  responseFixture({
    message: "Начинаю собирать бриф мероприятия.",
    ui_mode: "brief_workspace",
    router: routerFixture("brief_workspace", "brief_discovery", "clarifying", [
      "update_brief",
    ]),
    action_plan: actionPlanFixture("brief_workspace", "clarifying", [
      "update_brief",
    ]),
    brief: {
      ...emptyBrief(),
      event_type: "корпоратив",
      city: "Екатеринбург",
      audience_size: 120,
      open_questions: ["date_or_period", "venue_status", "budget_total"],
    },
  }),
);

assert.equal(intakeState.interfaceMode, "brief_workspace");
assert.equal(intakeState.showDraftBriefPanel, true);
assert.equal(intakeState.brief.event_type, "корпоратив");
assert.equal(intakeState.brief.city, "Екатеринбург");
assert.equal(intakeState.brief.audience_size, 120);
assert.deepStrictEqual(intakeState.foundItems, []);

const directSearchState = assistantUiStateFromResponse(
  [],
  responseFixture({
    message: "Нашел кандидатов в каталоге.",
    ui_mode: "chat_search",
    router: routerFixture("chat_search", "supplier_search", "searching", [
      "search_items",
    ]),
    action_plan: actionPlanFixture("chat_search", "searching", [
      "search_items",
    ]),
    found_items: [light],
  }),
);

assert.equal(directSearchState.interfaceMode, "chat_search");
assert.equal(directSearchState.showDraftBriefPanel, false);
assert.deepStrictEqual(directSearchState.assistantMessage.foundItems, [light]);
assert.deepStrictEqual(directSearchState.visibleCandidates, [
  { ordinal: 1, item_id: light.id, service_category: "свет" },
]);

const mixedSearchState = assistantUiStateFromResponse(
  [],
  responseFixture({
    message: "Обновил черновик брифа. Нашел кандидатов в каталоге.",
    ui_mode: "brief_workspace",
    router: routerFixture("brief_workspace", "mixed", "supplier_searching", [
      "update_brief",
      "search_items",
    ]),
    action_plan: actionPlanFixture("brief_workspace", "supplier_searching", [
      "update_brief",
      "search_items",
    ]),
    brief: {
      ...emptyBrief(),
      event_type: "корпоратив",
      city: "Екатеринбург",
      audience_size: 120,
      budget_per_guest: 2500,
      required_services: ["кейтеринг"],
    },
    found_items: [catering],
  }),
);

assert.equal(mixedSearchState.interfaceMode, "brief_workspace");
assert.equal(mixedSearchState.showDraftBriefPanel, true);
assert.equal(mixedSearchState.brief.budget_per_guest, 2500);
assert.deepStrictEqual(mixedSearchState.brief.required_services, ["кейтеринг"]);
assert.equal(mixedSearchState.assistantMessage.foundItems, undefined);
assert.deepStrictEqual(mixedSearchState.foundItems, [catering]);

const venueConstraintState = assistantUiStateFromResponse(
  [],
  responseFixture({
    message: "Обновил черновик брифа и запустил подбор.",
    ui_mode: "brief_workspace",
    router: routerFixture("brief_workspace", "mixed", "supplier_searching", [
      "update_brief",
      "search_items",
    ]),
    action_plan: actionPlanFixture("brief_workspace", "supplier_searching", [
      "update_brief",
      "search_items",
    ]),
    brief: {
      ...emptyBrief(),
      event_type: "корпоратив",
      venue_constraints: ["площадка без подвеса"],
      service_needs: [
        {
          category: "сценические конструкции",
          priority: "nice_to_have",
          source: "policy_inferred",
          reason: "площадка без подвеса",
          notes: "искать ground support, фермы или самонесущие конструкции",
        },
      ],
    },
    found_items: [truss],
  }),
);

assert.equal(venueConstraintState.showDraftBriefPanel, true);
assert.deepStrictEqual(venueConstraintState.brief.venue_constraints, [
  "площадка без подвеса",
]);
assert.deepStrictEqual(venueConstraintState.foundItems, [truss]);
assert.doesNotMatch(venueConstraintState.assistantMessage.content, /сможет|доступ/i);

const venuePlanningOnlyState = assistantUiStateFromResponse(
  [],
  responseFixture({
    message: "Начинаю собирать бриф мероприятия.",
    ui_mode: "brief_workspace",
    router: routerFixture("brief_workspace", "brief_discovery", "clarifying", [
      "update_brief",
    ]),
    action_plan: actionPlanFixture("brief_workspace", "clarifying", [
      "update_brief",
    ]),
    brief: {
      ...emptyBrief(),
      event_type: "корпоратив",
      audience_size: 300,
      venue_constraints: ["площадка без подвеса"],
      service_needs: [
        {
          category: "свет",
          priority: "nice_to_have",
          source: "policy_inferred",
          reason: "площадка без подвеса",
          notes: "искать стойки, напольные приборы или свет без подвеса",
        },
      ],
    },
    found_items: [],
  }),
);

assert.deepStrictEqual(venuePlanningOnlyState.foundItems, []);
assert.equal(venuePlanningOnlyState.assistantMessage.foundItems, undefined);
assert.deepStrictEqual(
  venuePlanningOnlyState.brief.service_needs.map((need) => need.category),
  ["свет"],
);

const selectionRequest = buildAssistantChatRequest({
  sessionId: null,
  message: "Добавь в подборку второй вариант.",
  brief: {
    ...emptyBrief(),
    event_type: "корпоратив",
    selected_item_ids: [],
  },
  messages: [{ role: "assistant", content: "Карточки ниже.", foundItems: [light, truss] }],
  visibleFoundItems: [light, truss],
});

assert.deepStrictEqual(selectionRequest.visible_candidates, [
  { ordinal: 1, item_id: light.id, service_category: "свет" },
  {
    ordinal: 2,
    item_id: truss.id,
    service_category: "сценические конструкции",
  },
]);
assert.deepStrictEqual(selectionRequest.candidate_item_ids, [light.id, truss.id]);

const selectionState = assistantUiStateFromResponse(
  [light, truss],
  responseFixture({
    ui_mode: "brief_workspace",
    router: routerFixture("brief_workspace", "selection", "supplier_searching", [
      "select_item",
    ]),
    action_plan: actionPlanFixture("brief_workspace", "supplier_searching", [
      "select_item",
    ]),
    brief: {
      ...emptyBrief(),
      event_type: "корпоратив",
      selected_item_ids: [truss.id],
    },
    found_items: [],
  }),
);

assert.deepStrictEqual(selectionState.selectedItemIds, [truss.id]);
assert.deepStrictEqual(selectionState.foundItems, [light, truss]);

const verificationState = assistantUiStateFromResponse(
  [light],
  responseFixture({
    message:
      "Юридические статусы и риск-флаги вернул отдельно в verification_results.",
    ui_mode: "chat_search",
    router: routerFixture("chat_search", "verification", "supplier_verification", [
      "verify_supplier_status",
    ]),
    action_plan: actionPlanFixture("chat_search", "supplier_verification", [
      "verify_supplier_status",
    ]),
    found_items: [],
    verification_results: [
      verificationResult({
        item_id: light.id,
        status: "active",
        source: "fake_registry",
      }),
    ],
  }),
);

assert.equal(verificationState.showDraftBriefPanel, false);
assert.deepStrictEqual(verificationState.assistantMessage.foundItems, [light]);
assert.equal(verificationState.assistantMessage.verificationResults?.length, 1);
assert.match(verificationState.assistantMessage.content, /verification_results/);
assert.doesNotMatch(
  verificationState.assistantMessage.content,
  /доступен|рекомендуем|действующий договор/i,
);

const verificationWithoutContextState = assistantUiStateFromResponse(
  [],
  responseFixture({
    message: "Уточните, каких найденных подрядчиков проверить.",
    ui_mode: "chat_search",
    router: routerFixture("chat_search", "verification", "search_clarifying", []),
    action_plan: actionPlanFixture("chat_search", "search_clarifying", []),
    found_items: [],
    verification_results: [],
  }),
);

assert.equal(verificationWithoutContextState.showDraftBriefPanel, false);
assert.deepStrictEqual(verificationWithoutContextState.verificationResults, []);
assert.equal(verificationWithoutContextState.assistantMessage.foundItems, undefined);
assert.match(verificationWithoutContextState.assistantMessage.content, /каких/);

const renderedBriefState = assistantUiStateFromResponse(
  [catering],
  responseFixture({
    message: "Подготовил структурированный бриф.",
    ui_mode: "brief_workspace",
    router: routerFixture("brief_workspace", "render_brief", "brief_rendered", [
      "render_event_brief",
    ]),
    action_plan: {
      ...actionPlanFixture("brief_workspace", "brief_rendered", [
        "render_event_brief",
      ]),
      render_requested: true,
    },
    brief: {
      ...emptyBrief(),
      event_type: "корпоратив",
      selected_item_ids: [],
    },
    rendered_brief: renderedBrief(),
  }),
);

assert.equal(renderedBriefState.showDraftBriefPanel, true);
assert.deepStrictEqual(renderedBriefState.renderedBrief?.evidence.selected_item_ids, []);
assert.match(
  renderedBriefState.renderedBrief?.sections[4]?.items.join("\n") ?? "",
  /Кандидаты найдены, но не выбраны/,
);
assert.doesNotMatch(
  renderedBriefState.renderedBrief?.sections[6]?.items.join("\n") ?? "",
  /2500\.00/,
);

function responseFixture(
  overrides: Partial<AssistantResponseForUi>,
): AssistantResponseForUi {
  return {
    session_id: "00000000-0000-0000-0000-000000000000",
    message: "Карточки ниже.",
    ui_mode: "chat_search",
    router: routerFixture("chat_search", "supplier_search", "searching", [
      "search_items",
    ]),
    action_plan: actionPlanFixture("chat_search", "searching", ["search_items"]),
    brief: emptyBrief(),
    found_items: [],
    item_details: [],
    verification_results: [],
    rendered_brief: null,
    ...overrides,
  };
}

function routerFixture(
  interfaceMode: AssistantInterfaceMode,
  intent: RouterIntent,
  workflowStage: EventBriefWorkflowState,
  toolIntents: RouterDecision["tool_intents"],
): RouterDecision {
  return {
    intent,
    confidence: 0.9,
    known_facts: {},
    missing_fields: [],
    should_search_now: toolIntents.includes("search_items"),
    search_query: toolIntents.includes("search_items") ? "свет Екатеринбург" : null,
    brief_update: emptyBrief(),
    interface_mode: interfaceMode,
    workflow_stage: workflowStage,
    reason_codes:
      interfaceMode === "brief_workspace"
        ? ["brief_workspace_selected"]
        : ["chat_search_selected"],
    search_requests: toolIntents.includes("search_items")
      ? [searchRequest("свет")]
      : [],
    tool_intents: toolIntents,
    clarification_questions: [],
    user_visible_summary: null,
  };
}

function actionPlanFixture(
  interfaceMode: AssistantInterfaceMode,
  workflowStage: EventBriefWorkflowState,
  toolIntents: ActionPlan["tool_intents"],
): ActionPlan {
  return {
    interface_mode: interfaceMode,
    workflow_stage: workflowStage,
    tool_intents: toolIntents,
    search_requests: toolIntents.includes("search_items")
      ? [searchRequest("свет")]
      : [],
    verification_targets: [],
    comparison_targets: [],
    item_detail_ids: [],
    render_requested: false,
    missing_fields: [],
    clarification_questions: [],
    skipped_actions: [],
  };
}

function searchRequest(serviceCategory: string) {
  return {
    query: `${serviceCategory} Екатеринбург`,
    service_category: serviceCategory,
    filters: {
      supplier_city_normalized: "екатеринбург",
      category: null,
      service_category: serviceCategory,
      supplier_status_normalized: null,
      has_vat: null,
      vat_mode: null,
      unit_price_min: null,
      unit_price_max: null,
    },
    priority: 1,
    limit: 8,
  };
}

function foundItem(id: string, name: string, serviceCategory: string): FoundItem {
  return {
    id,
    score: 0.87,
    name,
    category: serviceCategory,
    unit: "день",
    unit_price: "15000.00",
    supplier: "ООО Тест",
    supplier_city: "Екатеринбург",
    source_text_snippet: `${name} из строки прайса`,
    source_text_full_available: true,
    match_reason: {
      code: "semantic",
      label: "Семантическое совпадение",
    },
    result_group: serviceCategory,
    matched_service_category: serviceCategory,
    matched_service_categories: [serviceCategory],
  };
}

function verificationResult(
  overrides: Partial<SupplierVerificationResult> = {},
): SupplierVerificationResult {
  return {
    item_id: light.id,
    supplier_name: "ООО Свет",
    supplier_inn: "7700000000",
    ogrn: null,
    legal_name: null,
    status: "not_verified",
    source: "manual_not_verified",
    checked_at: null,
    risk_flags: ["verification_adapter_not_configured"],
    message: "Автоматическая проверка не настроена",
    ...overrides,
  };
}

function renderedBrief(): RenderedEventBrief {
  return {
    title: "Бриф мероприятия",
    sections: [
      { title: "Основная информация", items: ["Тип: корпоратив"] },
      { title: "Концепция и уровень", items: ["Нет"] },
      { title: "Площадка и ограничения", items: ["Нет"] },
      { title: "Блоки услуг", items: ["Нужен блок: кейтеринг"] },
      {
        title: "Подборка кандидатов",
        items: ["Кандидаты найдены, но не выбраны: Фуршет; поставщик: ООО Вкус"],
      },
      {
        title: "Проверка подрядчиков",
        items: ["Проверка подрядчиков еще не выполнялась"],
      },
      {
        title: "Бюджетные заметки",
        items: [
          "Смету из найденных кандидатов не считаю без выбранных позиций и количеств.",
        ],
      },
      { title: "Открытые вопросы", items: ["Дата мероприятия"] },
    ],
    open_questions: ["Дата мероприятия"],
    evidence: {
      selected_item_ids: [],
      verification_result_ids: [],
    },
  };
}

function emptyBrief(): BriefState {
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
