import { isCurrentCatalogImportStream } from "./catalogImportStream.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

const currentStream = {};
const staleStream = {};

assert.equal(
  isCurrentCatalogImportStream({
    currentStream,
    expectedStream: currentStream,
    activeJobId: "job-1",
    expectedJobId: "job-1",
  }),
  true,
);
assert.equal(
  isCurrentCatalogImportStream({
    currentStream: staleStream,
    expectedStream: currentStream,
    activeJobId: "job-1",
    expectedJobId: "job-1",
  }),
  false,
);
assert.equal(
  isCurrentCatalogImportStream({
    currentStream,
    expectedStream: currentStream,
    activeJobId: "job-2",
    expectedJobId: "job-1",
  }),
  false,
);
assert.equal(
  isCurrentCatalogImportStream({
    currentStream: null,
    expectedStream: currentStream,
    activeJobId: "job-1",
    expectedJobId: "job-1",
  }),
  false,
);
