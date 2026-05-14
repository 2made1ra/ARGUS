import {
  catalogImportStageSegments,
  catalogImportStatusIsActive,
  catalogImportUploadDisplayPercent,
  formatCatalogImportEta,
  timestampToMs,
  progressPercentFromUpload,
} from "./catalogImportProgress.ts";

declare const process: {
  getBuiltinModule(id: "node:assert/strict"): {
    equal: (actual: unknown, expected: unknown) => void;
  };
};

const assert = process.getBuiltinModule("node:assert/strict");

assert.equal(progressPercentFromUpload(0), 0);
assert.equal(progressPercentFromUpload(50), 5);
assert.equal(progressPercentFromUpload(100), 10);
assert.equal(progressPercentFromUpload(140), 10);
assert.equal(progressPercentFromUpload(-20), 0);

assert.equal(
  catalogImportUploadDisplayPercent({
    uploadPercent: 0,
    isStartingUpload: true,
    elapsedMs: 2_500,
  }),
  3,
);
assert.equal(
  catalogImportUploadDisplayPercent({
    uploadPercent: 0,
    isStartingUpload: true,
    elapsedMs: 30_000,
  }),
  9,
);
assert.equal(
  catalogImportUploadDisplayPercent({
    uploadPercent: 100,
    isStartingUpload: true,
    elapsedMs: 1_000,
  }),
  10,
);
assert.equal(
  catalogImportUploadDisplayPercent({
    uploadPercent: 0,
    isStartingUpload: false,
    elapsedMs: 30_000,
  }),
  0,
);

assert.equal(timestampToMs(null), null);
assert.equal(timestampToMs(""), null);
assert.equal(timestampToMs("not-a-date"), null);
assert.equal(timestampToMs("2026-05-15T00:00:00.000Z"), 1778803200000);

assert.equal(catalogImportStatusIsActive("QUEUED"), true);
assert.equal(catalogImportStatusIsActive("IMPORTING"), true);
assert.equal(catalogImportStatusIsActive("INDEXING"), true);
assert.equal(catalogImportStatusIsActive("COMPLETED"), false);
assert.equal(catalogImportStatusIsActive("FAILED"), false);

assert.equal(
  catalogImportStageSegments.map((segment) => `${segment.label}:${segment.from}-${segment.to}`).join("|"),
  "Загрузка файла:0-10|Импорт CSV:10-35|Индексация:35-100",
);

assert.equal(
  formatCatalogImportEta({
    progressPercent: 0,
    status: "QUEUED",
    startedAtMs: 1_000,
    nowMs: 31_000,
  }),
  "ожидает worker",
);
assert.equal(
  formatCatalogImportEta({
    progressPercent: 0,
    status: "IMPORTING",
    startedAtMs: 1_000,
    nowMs: 31_000,
  }),
  "считаю время",
);
assert.equal(
  formatCatalogImportEta({
    progressPercent: 50,
    status: "INDEXING",
    startedAtMs: 1_000,
    nowMs: 61_000,
  }),
  "примерно 1 мин",
);
assert.equal(
  formatCatalogImportEta({
    progressPercent: 95,
    status: "INDEXING",
    startedAtMs: 1_000,
    nowMs: 61_000,
  }),
  "меньше минуты",
);
assert.equal(
  formatCatalogImportEta({
    progressPercent: 100,
    status: "COMPLETED",
    startedAtMs: 1_000,
    nowMs: 61_000,
  }),
  "готово",
);
