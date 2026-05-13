import type {
  ActionPlan,
  AssistantInterfaceMode,
  BriefState,
  EventBriefWorkflowState,
  FoundItem,
  RouterIntent,
  RouterDecision,
} from "../api.ts";
import {
  assistantUiStateFromResponse,
  type AssistantResponseForUi,
} from "./assistantUiState.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    deepStrictEqual: (actual: unknown, expected: unknown) => void;
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

const eventBrief: BriefState = {
  ...emptyBrief(),
  event_type: "корпоратив",
  city: "Екатеринбург",
  audience_size: 120,
  open_questions: ["date_or_period"],
};

const foundItem: FoundItem = {
  id: "00000000-0000-0000-0000-000000000001",
  score: 0.81,
  name: "Световой комплект",
  category: "Свет",
  unit: "день",
  unit_price: "15000.00",
  supplier: "ООО Свет",
  supplier_city: "Екатеринбург",
  source_text_snippet: "Световой комплект для мероприятий",
  source_text_full_available: true,
  match_reason: {
    code: "semantic",
    label: "Семантическое совпадение",
  },
  result_group: "свет",
  matched_service_category: "свет",
  matched_service_categories: ["свет"],
};

const briefWorkspaceState = assistantUiStateFromResponse([], responseFixture({
  ui_mode: undefined,
  router: routerFixture("brief_workspace", "brief_discovery", "clarifying", false),
  action_plan: actionPlanFixture("brief_workspace", "clarifying", [
    "update_brief",
  ]),
  brief: eventBrief,
  found_items: [foundItem],
}));

assert.equal(briefWorkspaceState.interfaceMode, "brief_workspace");
assert.equal(briefWorkspaceState.showDraftBriefPanel, true);
assert.equal(briefWorkspaceState.brief.event_type, "корпоратив");
assert.deepStrictEqual(
  briefWorkspaceState.foundItems.map((item) => item.id),
  [foundItem.id],
);
assert.equal(briefWorkspaceState.assistantMessage.foundItems, undefined);

const chatSearchState = assistantUiStateFromResponse([], responseFixture({
  ui_mode: undefined,
  router: routerFixture("chat_search", "supplier_search", "searching", true),
  action_plan: actionPlanFixture("chat_search", "searching", ["search_items"]),
  found_items: [foundItem],
}));

assert.equal(chatSearchState.interfaceMode, "chat_search");
assert.equal(chatSearchState.showDraftBriefPanel, false);
assert.deepStrictEqual(
  chatSearchState.assistantMessage.foundItems?.map((item) => item.id),
  [foundItem.id],
);
assert.deepStrictEqual(
  chatSearchState.visibleCandidates,
  [{ ordinal: 1, item_id: foundItem.id, service_category: "свет" }],
);

const legacyState = assistantUiStateFromResponse([], responseFixture({
  ui_mode: undefined,
  router: undefined,
  action_plan: null,
  found_items: [foundItem],
}));

assert.equal(legacyState.interfaceMode, "chat_search");
assert.equal(legacyState.showDraftBriefPanel, false);
assert.deepStrictEqual(
  legacyState.assistantMessage.foundItems?.map((item) => item.id),
  [foundItem.id],
);

function responseFixture(
  overrides: Partial<AssistantResponseForUi>,
): AssistantResponseForUi {
  return {
    session_id: "00000000-0000-0000-0000-000000000000",
    message: "Карточки ниже.",
    ui_mode: "chat_search",
    router: routerFixture("chat_search", "supplier_search", "searching", true),
    action_plan: actionPlanFixture("chat_search", "searching", ["search_items"]),
    brief: emptyBrief(),
    found_items: [],
    verification_results: [],
    rendered_brief: null,
    ...overrides,
  };
}

function routerFixture(
  interfaceMode: AssistantInterfaceMode,
  intent: RouterIntent,
  workflowStage: EventBriefWorkflowState,
  shouldSearchNow: boolean,
): RouterDecision {
  return {
    intent,
    confidence: 0.9,
    known_facts: {},
    missing_fields: [],
    should_search_now: shouldSearchNow,
    search_query: shouldSearchNow ? "свет Екатеринбург" : null,
    brief_update: emptyBrief(),
    interface_mode: interfaceMode,
    workflow_stage: workflowStage,
    reason_codes:
      interfaceMode === "brief_workspace"
        ? ["event_creation_intent_detected"]
        : ["direct_catalog_search_detected"],
    search_requests: [],
    tool_intents: shouldSearchNow ? ["search_items"] : ["update_brief"],
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
    search_requests: [],
    verification_targets: [],
    item_detail_ids: [],
    render_requested: false,
    missing_fields: [],
    clarification_questions: [],
    skipped_actions: [],
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
