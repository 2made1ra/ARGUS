import { appendAssistantTimelineMessage } from "./assistantTimeline.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    deepStrictEqual: (actual: unknown, expected: unknown) => void;
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

const previousCandidates = [
  { id: "00000000-0000-0000-0000-000000000001" },
];
const nextCandidates = [
  { id: "00000000-0000-0000-0000-000000000002" },
];

type TimelineMessage = {
  role: "user" | "assistant";
  content: string;
  foundItems?: Array<{ id: string }>;
  foundItemsEmptyState?: "pending" | "no-results";
};

const initialMessages: TimelineMessage[] = [
  { role: "user", content: "Найди свет" },
  {
    role: "assistant",
    content: "Первый поиск.",
    foundItems: previousCandidates,
    foundItemsEmptyState: "pending",
  },
];

const replaced = appendAssistantTimelineMessage(initialMessages, {
  role: "assistant",
  content: "Второй поиск.",
  foundItems: nextCandidates,
});

assert.equal(replaced.length, 3);
assert.deepStrictEqual(replaced[1], {
  role: "assistant",
  content: "Первый поиск.",
});
assert.deepStrictEqual(replaced[2].foundItems, nextCandidates);

const preserved = appendAssistantTimelineMessage(replaced, {
  role: "assistant",
  content: "Проверку пока не запускал.",
});

assert.deepStrictEqual(preserved[2].foundItems, nextCandidates);
assert.equal(preserved[3].foundItems, undefined);
