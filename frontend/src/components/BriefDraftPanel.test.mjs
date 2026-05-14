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

const componentPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "BriefDraftPanel.tsx",
);
const BriefDraftPanel = loadBriefDraftPanel();

test("renders known event brief fields as compact manager-facing facts", () => {
  const html = renderPanel({
    event_type: "корпоратив",
    city: "Екатеринбург",
    audience_size: 120,
    venue_status: "площадка есть",
    venue_constraints: ["монтаж только ночью"],
    budget_total: 2_000_000,
    service_needs: [
      {
        category: "кейтеринг",
        priority: "required",
        source: "explicit",
        reason: null,
        notes: "фуршет",
      },
    ],
    open_questions: ["date_or_period", "concept"],
  });

  assert.match(html, /Тип мероприятия/);
  assert.match(html, /корпоратив/);
  assert.match(html, /Город/);
  assert.match(html, /Екатеринбург/);
  assert.match(html, /120 гостей/);
  assert.match(html, /Площадка есть/);
  assert.match(html, /Монтаж только ночью/);
  assert.match(html, /2 000 000 ₽/);
  assert.match(html, /кейтеринг/);
  assert.match(html, /фуршет/);
});

test("renders unknown values as open questions instead of raw DTO keys", () => {
  const html = renderPanel({
    event_type: "корпоратив",
    city: "Екатеринбург",
    audience_size: 120,
    open_questions: [
      "date_or_period",
      "venue_status",
      "budget_total",
      "concept",
    ],
  });

  assert.match(html, /Открытые вопросы/);
  assert.match(html, /Дата или период/);
  assert.match(html, /Площадка уже есть/);
  assert.match(html, /Какой общий бюджет/);
  assert.match(html, /Какая концепция/);
  assert.doesNotMatch(html, /date_or_period/);
  assert.doesNotMatch(html, /venue_status/);
  assert.doesNotMatch(html, /budget_total/);
});

test("does not show found catalog candidates as selected brief items", () => {
  const html = renderPanel({
    selected_item_ids: [],
    found_items: [
      {
        id: "00000000-0000-0000-0000-000000000001",
        name: "Кандидат из выдачи",
      },
    ],
  });

  assert.match(html, /Выбранные позиции/);
  assert.match(html, /Пока нет выбранных позиций/);
  assert.doesNotMatch(html, /Кандидат из выдачи/);
});

function renderPanel(overrides) {
  return renderToStaticMarkup(
    React.createElement(BriefDraftPanel, {
      brief: {
        ...emptyBrief(),
        ...overrides,
      },
    }),
  );
}

function loadBriefDraftPanel() {
  const source = readFileSync(componentPath, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: componentPath,
  });
  const module = { exports: {} };
  const compiled = new Function("exports", "require", "module", outputText);
  compiled(module.exports, require, module);
  return module.exports.default;
}

function emptyBrief() {
  return {
    event_type: null,
    event_goal: null,
    concept: null,
    format: null,
    city: null,
    date_or_period: null,
    audience_size: null,
    venue: null,
    venue_status: null,
    venue_constraints: [],
    duration_or_time_window: null,
    event_level: null,
    budget: null,
    budget_total: null,
    budget_per_guest: null,
    budget_notes: null,
    catering_format: null,
    technical_requirements: [],
    service_needs: [],
    required_services: [],
    must_have_services: [],
    nice_to_have_services: [],
    selected_item_ids: [],
    constraints: [],
    preferences: [],
    open_questions: [],
  };
}
