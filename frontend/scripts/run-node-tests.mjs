import { existsSync, readdirSync, realpathSync, statSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const testRoots = ["src", "scripts"];
const runtimeTestPattern = /\.test\.(ts|mjs)$/;
const compileOnlyTestPattern = /\.contract\.test\.ts$/;

export function findRuntimeTestFiles(cwd = process.cwd()) {
  return testRoots
    .flatMap((root) => {
      const rootDir = join(cwd, root);
      if (!existsSync(rootDir)) return [];
      return findTestFiles(rootDir);
    })
    .sort();
}

export function runNodeTests(cwd = process.cwd()) {
  const testFiles = findRuntimeTestFiles(cwd);
  const result = spawnSync(process.execPath, ["--test", ...testFiles], {
    cwd,
    stdio: "inherit",
  });

  return result.status ?? 1;
}

if (isDirectRun()) {
  process.exit(runNodeTests());
}

function isDirectRun() {
  return (
    process.argv[1] !== undefined &&
    realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))
  );
}

function findTestFiles(directory) {
  return readdirSync(directory)
    .flatMap((entry) => {
      const path = join(directory, entry);
      if (statSync(path).isDirectory()) return findTestFiles(path);
      if (!runtimeTestPattern.test(path)) return [];
      if (compileOnlyTestPattern.test(path)) return [];
      return [path];
    })
    .sort();
}
