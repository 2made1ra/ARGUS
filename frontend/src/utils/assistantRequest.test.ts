import type { BriefState, FoundItem } from "../api.ts";
import { buildAssistantChatRequest } from "./assistantRequest.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    deepStrictEqual: (actual: unknown, expected: unknown) => void;
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

const lightA = foundItem(
  "00000000-0000-0000-0000-000000000001",
  "Световой комплект A",
  "Свет",
);
const sound = foundItem(
  "00000000-0000-0000-0000-000000000002",
  "Звуковой комплект",
  "Звук",
);
const lightB = foundItem(
  "00000000-0000-0000-0000-000000000003",
  "Световой комплект B",
  "Свет",
);

const request = buildAssistantChatRequest({
  sessionId: "00000000-0000-0000-0000-000000000000",
  message: "Добавь в подборку второй вариант",
  brief: {
    ...emptyBrief(),
    selected_item_ids: [lightB.id],
  },
  messages: [
    { role: "user", content: "Найди свет" },
    {
      role: "assistant",
      content: "Карточки ниже.",
      foundItems: [lightA, sound, lightB],
    },
  ],
  visibleFoundItems: [lightA, sound, lightB],
});

assert.equal(request.message, "Добавь в подборку второй вариант");
assert.deepStrictEqual(request.brief?.selected_item_ids, [lightB.id]);
assert.deepStrictEqual(request.visible_candidates, [
  { ordinal: 1, item_id: lightA.id, service_category: "Свет" },
  { ordinal: 2, item_id: lightB.id, service_category: "Свет" },
  { ordinal: 3, item_id: sound.id, service_category: "Звук" },
]);
assert.deepStrictEqual(request.candidate_item_ids, [
  lightA.id,
  lightB.id,
  sound.id,
]);
assert.deepStrictEqual(request.recent_turns, [
  { role: "user", content: "Найди свет" },
  { role: "assistant", content: "Карточки ниже." },
]);

function foundItem(id: string, name: string, group: string): FoundItem {
  return {
    id,
    score: 0.82,
    name,
    category: group,
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
    result_group: group,
    matched_service_category: group,
    matched_service_categories: [group],
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
