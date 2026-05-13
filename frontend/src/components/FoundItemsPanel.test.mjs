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
const { StaticRouter } = require("react-router-dom/server");

const srcDir = join(dirname(fileURLToPath(import.meta.url)), "..");
installTypeScriptRequireHook(srcDir);

const FoundItemsPanel = require("./FoundItemsPanel.tsx").default;

test("renders selected catalog items in a separate selected list", () => {
  const selectedId = "00000000-0000-0000-0000-000000000002";
  const html = renderPanel({
    items: [
      foundItem("00000000-0000-0000-0000-000000000001", "Световой комплект"),
      foundItem(selectedId, "Звуковой комплект"),
    ],
    selectedItemIds: [selectedId],
  });

  assert.match(html, /Найденные позиции/);
  assert.match(html, /Выбрано в подборку/);

  const selectedSection = sectionHtml(html, "Выбрано в подборку");
  assert.match(selectedSection, /Звуковой комплект/);
  assert.doesNotMatch(selectedSection, /Световой комплект/);
});

test("marks selected candidate controls without selecting all found candidates", () => {
  const selectedId = "00000000-0000-0000-0000-000000000002";
  const html = renderPanel({
    items: [
      foundItem("00000000-0000-0000-0000-000000000001", "Световой комплект"),
      foundItem(selectedId, "Звуковой комплект"),
    ],
    selectedItemIds: [selectedId],
  });

  assert.match(
    html,
    /aria-label="Добавить Световой комплект в подборку"[^>]*type="checkbox"/,
  );
  assert.match(
    html,
    /aria-label="Убрать Звуковой комплект из подборки"[^>]*type="checkbox"[^>]*checked=""/,
  );
});

function renderPanel(props) {
  return renderToStaticMarkup(
    React.createElement(
      StaticRouter,
      { location: "/" },
      React.createElement(FoundItemsPanel, props),
    ),
  );
}

function sectionHtml(html, heading) {
  const headingIndex = html.indexOf(heading);
  assert.notEqual(headingIndex, -1);
  return html.slice(headingIndex, html.indexOf("</section>", headingIndex));
}

function foundItem(id, name) {
  return {
    id,
    score: 0.87,
    name,
    category: "Категория",
    unit: "день",
    unit_price: "15000.00",
    supplier: "ООО Тест",
    supplier_city: "Екатеринбург",
    source_text_snippet: `${name} из строки прайса`,
    source_text_full_available: true,
    match_reason: {
      code: "semantic",
      label: "Семантическое совпадение",
    },
    result_group: "Категория",
    matched_service_category: "Категория",
    matched_service_categories: ["Категория"],
  };
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
