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

const RenderedBriefPanel = require("./RenderedBriefPanel.tsx").default;

test("renders final brief sections in the required UX order", () => {
  const html = renderPanel(renderedBrief({
    sections: [
      section("Открытые вопросы", ["Дата мероприятия"]),
      section("Подборка кандидатов", [
        "Кандидаты найдены, но не выбраны: Фуршет; поставщик: ООО Вкус",
      ]),
      section("Основная информация", [
        "Тип: корпоратив",
        "Город: Екатеринбург",
      ]),
      section("Бюджетные заметки", [
        "Смету из найденных кандидатов не считаю без выбранных позиций и количеств.",
      ]),
      section("Концепция и уровень", ["Концепция или уровень уточняются"]),
      section("Площадка и ограничения", ["Статус площадки: площадка есть"]),
      section("Блоки услуг", ["Нужен блок: кейтеринг"]),
      section("Проверка подрядчиков", [
        "Проверка подрядчиков еще не выполнялась",
      ]),
    ],
  }));

  assertSectionOrder(html, [
    "Основная информация",
    "Концепция и уровень",
    "Площадка и ограничения",
    "Блоки услуг",
    "Подборка кандидатов",
    "Проверка подрядчиков",
    "Бюджетные заметки",
    "Открытые вопросы",
  ]);
});

test("shows rendered brief as an evidence-backed artifact", () => {
  const selectedId = "00000000-0000-0000-0000-000000000001";
  const verifiedId = "00000000-0000-0000-0000-000000000002";
  const html = renderPanel(renderedBrief({
    sections: [
      section("Основная информация", ["Тип: корпоратив"]),
      section("Подборка кандидатов", [
        "Выбрано: Световой комплект; поставщик: ООО НИКА",
      ]),
      section("Проверка подрядчиков", [
        "поставщик: ООО НИКА; статус: юрлицо найдено как действующее в проверочном источнике",
      ]),
      section("Бюджетные заметки", [
        "По выбранным позициям нужны количества; итоговую сумму не считаю.",
      ]),
      section("Открытые вопросы", ["Дата мероприятия"]),
    ],
    open_questions: ["Дата мероприятия"],
    evidence: {
      selected_item_ids: [selectedId],
      verification_result_ids: [verifiedId],
    },
  }));

  assert.match(html, /Итоговый бриф/);
  assert.match(html, /Доказательства/);
  assert.match(html, /Выбранные позиции/);
  assert.match(html, new RegExp(selectedId));
  assert.match(html, /Проверки подрядчиков/);
  assert.match(html, new RegExp(verifiedId));
  assert.equal(matchCount(html, /Дата мероприятия/g), 1);
});

test("keeps found-only candidates and budget notes unselected", () => {
  const html = renderPanel(renderedBrief({
    sections: [
      section("Подборка кандидатов", [
        "Кандидаты найдены, но не выбраны: Фуршет; поставщик: ООО Вкус; цена: 2500.00 за гость",
      ]),
      section("Бюджетные заметки", [
        "Смету из найденных кандидатов не считаю без выбранных позиций и количеств.",
      ]),
    ],
    evidence: {
      selected_item_ids: [],
      verification_result_ids: [],
    },
  }));

  const candidateSection = sectionHtml(html, "Подборка кандидатов");
  const budgetSection = sectionHtml(html, "Бюджетные заметки");

  assert.match(candidateSection, /Кандидаты найдены, но не выбраны/);
  assert.doesNotMatch(candidateSection, /Выбрано:/);
  assert.doesNotMatch(budgetSection, /2500\.00/);
  assert.match(budgetSection, /без выбранных позиций и количеств/);
});

function renderPanel(brief) {
  return renderToStaticMarkup(
    React.createElement(RenderedBriefPanel, { brief }),
  );
}

function renderedBrief(overrides = {}) {
  return {
    title: "Бриф мероприятия",
    sections: [],
    open_questions: [],
    evidence: {},
    ...overrides,
  };
}

function section(title, items) {
  return { title, items };
}

function assertSectionOrder(html, titles) {
  const positions = titles.map((title) => {
    const index = html.indexOf(`>${title}</h3>`);
    assert.notEqual(index, -1, `section not found: ${title}`);
    return index;
  });

  assert.deepEqual(positions, [...positions].sort((left, right) => left - right));
}

function sectionHtml(html, heading) {
  const headingIndex = html.indexOf(`>${heading}</h3>`);
  assert.notEqual(headingIndex, -1);
  return html.slice(headingIndex, html.indexOf("</section>", headingIndex));
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
