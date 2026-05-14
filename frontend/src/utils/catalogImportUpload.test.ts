import { createCatalogUploadAbortError } from "./catalogImportUpload.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

const error = createCatalogUploadAbortError();
assert.equal(error.name, "AbortError");
assert.equal(error.message, "CSV upload was cancelled");
