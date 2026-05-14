import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, sep } from "node:path";
import { findRuntimeTestFiles } from "./run-node-tests.mjs";

const fixtureDir = mkdtempSync(join(tmpdir(), "argus-node-tests-"));

try {
  mkdirSync(join(fixtureDir, "src", "utils"), { recursive: true });
  mkdirSync(join(fixtureDir, "src", "pages"), { recursive: true });
  mkdirSync(join(fixtureDir, "scripts"), { recursive: true });

  writeFileSync(
    join(fixtureDir, "src", "utils", "inside.test.ts"),
    "import assert from 'node:assert/strict';\nassert.equal(1, 1);\n",
  );
  writeFileSync(
    join(fixtureDir, "src", "pages", "outside.test.ts"),
    "throw new Error('runtime test outside utils executed');\n",
  );
  writeFileSync(
    join(fixtureDir, "src", "phase5.contract.test.ts"),
    "throw new Error('compile-only contract test should not run');\n",
  );
  writeFileSync(
    join(fixtureDir, "scripts", "runner.test.mjs"),
    "import assert from 'node:assert/strict';\nassert.equal(1, 1);\n",
  );

  assert.deepStrictEqual(relativeTestFiles(fixtureDir), [
    "scripts/runner.test.mjs",
    "src/pages/outside.test.ts",
    "src/utils/inside.test.ts",
  ]);
} finally {
  rmSync(fixtureDir, { recursive: true, force: true });
}

function relativeTestFiles(rootDir) {
  return findRuntimeTestFiles(rootDir).map((path) =>
    relative(rootDir, path).split(sep).join("/"),
  );
}
