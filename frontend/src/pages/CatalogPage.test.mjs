import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const source = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "CatalogPage.tsx"),
  "utf8",
);

test("catalog import modal uses simple waiting and completed states", () => {
  assert.match(source, /catalog-import-waiting/);
  assert.match(source, /База загружена/);
  assert.match(source, /ОК/);
  assert.doesNotMatch(source, /catalog-import-stages/);
  assert.doesNotMatch(source, /catalogImportStageSegments/);
});

test("catalog page restores mounted guard after StrictMode remount", () => {
  assert.match(
    source,
    /isMountedRef\.current = true;[\s\S]*return \(\) => \{[\s\S]*isMountedRef\.current = false;/,
  );
});
