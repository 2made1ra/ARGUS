import type { RenderedEventBrief } from "../api";

interface Props {
  brief: RenderedEventBrief;
  variant?: "panel" | "inline";
}

export default function RenderedBriefPanel({ brief, variant = "panel" }: Props) {
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
        <span className="meta">{brief.sections.length} разделов</span>
      </div>

      <div className="rendered-brief-sections">
        {brief.sections.map((section) => (
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

      {brief.open_questions.length > 0 && (
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
