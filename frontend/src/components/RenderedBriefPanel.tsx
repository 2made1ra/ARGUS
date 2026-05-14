import type { RenderedEventBrief } from "../api";

interface Props {
  brief: RenderedEventBrief;
  variant?: "panel" | "inline";
}

const REQUIRED_SECTION_ORDER = [
  "Основная информация",
  "Концепция и уровень",
  "Площадка и ограничения",
  "Блоки услуг",
  "Подборка кандидатов",
  "Проверка подрядчиков",
  "Бюджетные заметки",
  "Открытые вопросы",
] as const;

const EVIDENCE_LABELS: Record<string, string> = {
  selected_item_ids: "Выбранные позиции",
  verification_result_ids: "Проверки подрядчиков",
};

export default function RenderedBriefPanel({ brief, variant = "panel" }: Props) {
  const sections = orderBriefSections(brief.sections);
  const evidenceEntries = Object.entries(brief.evidence).filter(
    ([, values]) => values.length > 0,
  );
  const hasOpenQuestionsSection = sections.some(
    (section) => section.title === "Открытые вопросы",
  );

  return (
    <section
      className={`rendered-brief-panel ${
        variant === "panel" ? "panel" : "rendered-brief-panel--inline"
      }`}
      aria-label="Итоговый бриф"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Rendered brief</p>
          <h2>{brief.title}</h2>
        </div>
        <span className="meta">{sections.length} разделов</span>
      </div>

      <div className="rendered-brief-sections">
        {sections.map((section) => (
          <section className="rendered-brief-section" key={section.title}>
            <h3>{section.title}</h3>
            {section.items.length > 0 ? (
              <ul>
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Нет данных</p>
            )}
          </section>
        ))}
      </div>

      {evidenceEntries.length > 0 && (
        <section className="rendered-brief-evidence">
          <div>
            <p className="eyebrow">Evidence</p>
            <h3>Доказательства</h3>
          </div>
          <dl>
            {evidenceEntries.map(([key, values]) => (
              <div key={key}>
                <dt>{evidenceLabel(key)}</dt>
                <dd>{values.join(", ")}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {brief.open_questions.length > 0 && !hasOpenQuestionsSection && (
        <div className="rendered-brief-open">
          <h3>Открытые вопросы</h3>
          <ul>
            {brief.open_questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function orderBriefSections(
  sections: RenderedEventBrief["sections"],
): RenderedEventBrief["sections"] {
  return sections
    .map((section, index) => ({ section, index }))
    .sort((left, right) => {
      const leftOrder = sectionOrder(left.section.title);
      const rightOrder = sectionOrder(right.section.title);
      if (leftOrder !== rightOrder) return leftOrder - rightOrder;
      return left.index - right.index;
    })
    .map(({ section }) => section);
}

function sectionOrder(title: string): number {
  const index = REQUIRED_SECTION_ORDER.indexOf(
    title as (typeof REQUIRED_SECTION_ORDER)[number],
  );
  return index === -1 ? REQUIRED_SECTION_ORDER.length : index;
}

function evidenceLabel(key: string): string {
  return EVIDENCE_LABELS[key] ?? key;
}
