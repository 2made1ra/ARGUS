import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import test from "node:test";

import ts from "typescript";

const require = createRequire(import.meta.url);
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

const srcDir = join(dirname(fileURLToPath(import.meta.url)), "..");
installTypeScriptRequireHook(srcDir);

const VerificationResultsPanel = require("./VerificationResultsPanel.tsx").default;

test("renders not_verified as a neutral manual verification state", () => {
  const html = renderPanel({
    results: [
      verificationResult({
        status: "not_verified",
        supplier_inn: null,
        source: "catalog",
        checked_at: "2026-05-01T09:30:00Z",
        risk_flags: ["supplier_inn_missing"],
        message: "В строке каталога нет ИНН поставщика",
      }),
    ],
  });

  assert.match(html, /ООО Световой Цех/);
  assert.match(html, /Нужна ручная проверка/);
  assert.match(html, /catalog/);
  assert.match(html, /2026/);
  assert.match(html, /supplier_inn_missing/);
  assert.doesNotMatch(html, /Ошибка проверки/);
});

test("labels active status as legal registry status only", () => {
  const html = renderPanel({
    results: [
      verificationResult({
        status: "active",
        source: "fake_registry",
        risk_flags: [],
      }),
    ],
  });

  assert.match(html, /Юрлицо действует в реестре/);
  assert.doesNotMatch(html, /доступ/iu);
  assert.doesNotMatch(html, /рекоменд/iu);
});

test("groups duplicate INN results and maps them to related item cards", () => {
  const firstId = "00000000-0000-0000-0000-000000000001";
  const secondId = "00000000-0000-0000-0000-000000000002";
  const html = renderPanel({
    results: [
      verificationResult({ item_id: firstId }),
      verificationResult({ item_id: secondId }),
    ],
    relatedItems: [
      foundItem(firstId, "Световой комплект"),
      foundItem(secondId, "Монтаж света"),
    ],
  });

  assert.match(html, /1 поставщик/);
  assert.match(html, /Связанные карточки/);
  assert.match(html, /Вариант 1: Световой комплект/);
  assert.match(html, /Вариант 2: Монтаж света/);
  assert.equal(matchCount(html, /ООО Световой Цех/g), 1);
});

function renderPanel(props) {
  return renderToStaticMarkup(
    React.createElement(VerificationResultsPanel, props),
  );
}

function verificationResult(overrides = {}) {
  return {
    item_id: "00000000-0000-0000-0000-000000000001",
    supplier_name: "ООО Световой Цех",
    supplier_inn: "7700000000",
    ogrn: null,
    legal_name: null,
    status: "not_verified",
    source: "manual_not_verified",
    checked_at: null,
    risk_flags: ["verification_adapter_not_configured"],
    message: "Автоматическая проверка не настроена",
    ...overrides,
  };
}

function foundItem(id, name) {
  return {
    id,
    score: 0.87,
    name,
    category: "Свет",
    unit: "день",
    unit_price: "15000.00",
    supplier: "ООО Световой Цех",
    supplier_city: "Екатеринбург",
    source_text_snippet: `${name} из строки прайса`,
    source_text_full_available: true,
    match_reason: {
      code: "semantic",
      label: "Семантическое совпадение",
    },
    result_group: "свет",
    matched_service_category: "свет",
    matched_service_categories: ["свет"],
  };
}

function matchCount(value, pattern) {
  return value.match(pattern)?.length ?? 0;
}

function installTypeScriptRequireHook(baseDir) {
  const previousTs = require.extensions[".ts"];
  const previousTsx = require.extensions[".tsx"];

  const loader = (module, filename) => {
    if (!filename.startsWith(baseDir)) {
      const previous = filename.endsWith(".tsx") ? previousTsx : previousTs;
      if (previous !== undefined) {
        previous(module, filename);
        return;
      }
    }

    const source = readFileSync(filename, "utf8");
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    });
    module._compile(outputText, filename);
  };

  require.extensions[".ts"] = loader;
  require.extensions[".tsx"] = loader;
}
