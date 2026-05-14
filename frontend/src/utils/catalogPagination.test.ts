import {
  catalogPageCount,
  catalogPageOffset,
  catalogPageRangeLabel,
} from "./catalogPagination.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

assert.equal(catalogPageOffset(1, 50), 0);
assert.equal(catalogPageOffset(4, 50), 150);
assert.equal(catalogPageOffset(0, 50), 0);

assert.equal(catalogPageCount(0, 50), 1);
assert.equal(catalogPageCount(1, 50), 1);
assert.equal(catalogPageCount(50, 50), 1);
assert.equal(catalogPageCount(51, 50), 2);
assert.equal(catalogPageCount(1557, 50), 32);

assert.equal(
  catalogPageRangeLabel({ page: 1, pageSize: 50, total: 1557, loaded: 50 }),
  "1-50 из 1557",
);
assert.equal(
  catalogPageRangeLabel({ page: 32, pageSize: 50, total: 1557, loaded: 7 }),
  "1551-1557 из 1557",
);
assert.equal(
  catalogPageRangeLabel({ page: 1, pageSize: 50, total: 0, loaded: 0 }),
  "0 из 0",
);
