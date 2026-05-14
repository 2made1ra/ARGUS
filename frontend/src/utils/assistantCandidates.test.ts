import type { AssistantCandidateItem } from "./assistantCandidates.ts";
import {
  buildVisibleCandidates,
  nextVisibleCandidateItems,
  orderFoundItemsForDisplay,
} from "./assistantCandidates.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    deepStrictEqual: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

/*
 * These tests run through Node's built-in TypeScript loader. Keeping them under
 * src/utils avoids pulling React components into the runtime test runner.
 */
void process;

type StrictAssert = {
  deepStrictEqual: (actual: unknown, expected: unknown) => void;
};

void (assert satisfies StrictAssert);

const lightA = item("00000000-0000-0000-0000-000000000001", "Свет");
const sound = item("00000000-0000-0000-0000-000000000002", "Звук");
const lightB = item("00000000-0000-0000-0000-000000000003", "Свет");

assert.deepStrictEqual(
  orderFoundItemsForDisplay([lightA, sound, lightB]).map((candidate) => candidate.id),
  [lightA.id, lightB.id, sound.id],
);

assert.deepStrictEqual(
  buildVisibleCandidates([lightA, sound, lightB]),
  [
    { ordinal: 1, item_id: lightA.id, service_category: "Свет" },
    { ordinal: 2, item_id: lightB.id, service_category: "Свет" },
    { ordinal: 3, item_id: sound.id, service_category: "Звук" },
  ],
);

assert.deepStrictEqual(
  nextVisibleCandidateItems([lightA, lightB, sound], {
    found_items: [],
    action_plan: { tool_intents: ["verify_supplier_status"] },
    router: { should_search_now: false, tool_intents: ["verify_supplier_status"] },
  }).map((candidate) => candidate.id),
  [lightA.id, lightB.id, sound.id],
);

assert.deepStrictEqual(
  nextVisibleCandidateItems([lightA, lightB, sound], {
    found_items: [],
    action_plan: { tool_intents: ["search_items"] },
    router: { should_search_now: true, tool_intents: ["search_items"] },
  }),
  [],
);

function item(id: string, group: string): AssistantCandidateItem {
  return {
    id,
    result_group: group,
    matched_service_category: group,
    matched_service_categories: [group],
  };
}
