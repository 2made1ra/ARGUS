import { nextModalFocusIndex } from "./modalFocus.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

assert.equal(nextModalFocusIndex(0, 3, false), 1);
assert.equal(nextModalFocusIndex(2, 3, false), 0);
assert.equal(nextModalFocusIndex(2, 3, true), 1);
assert.equal(nextModalFocusIndex(0, 3, true), 2);
assert.equal(nextModalFocusIndex(-1, 3, false), 0);
assert.equal(nextModalFocusIndex(-1, 3, true), 2);
assert.equal(nextModalFocusIndex(0, 0, false), -1);
