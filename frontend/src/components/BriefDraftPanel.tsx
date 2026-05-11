import type { BriefState } from "../api";

interface Props {
  brief: BriefState;
}

const scalarFields: Array<{
  key: keyof Pick<
    BriefState,
    | "event_type"
    | "city"
    | "date_or_period"
    | "audience_size"
    | "venue"
    | "venue_status"
    | "duration_or_time_window"
    | "budget"
    | "event_level"
  >;
  label: string;
}> = [
  { key: "event_type", label: "Формат" },
  { key: "city", label: "Город" },
  { key: "date_or_period", label: "Дата/период" },
  { key: "audience_size", label: "Гостей" },
  { key: "venue", label: "Площадка" },
  { key: "venue_status", label: "Статус площадки" },
  { key: "duration_or_time_window", label: "Время" },
  { key: "budget", label: "Бюджет" },
  { key: "event_level", label: "Уровень" },
];

const arrayFields: Array<{
  key: keyof Pick<
    BriefState,
    "required_services" | "constraints" | "preferences"
  >;
  label: string;
}> = [
  { key: "required_services", label: "Услуги" },
  { key: "constraints", label: "Ограничения" },
  { key: "preferences", label: "Предпочтения" },
];

export default function BriefDraftPanel({ brief }: Props) {
  return (
    <section className="brief-panel panel" aria-label="Черновик брифа">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Brief</p>
          <h2>Черновик брифа</h2>
        </div>
        <span className="meta">структура</span>
      </div>

      <dl className="brief-grid">
        {scalarFields.map((field) => (
          <div className="brief-grid__row" key={field.key}>
            <dt>{field.label}</dt>
            <dd>{formatValue(brief[field.key])}</dd>
          </div>
        ))}
      </dl>

      <div className="brief-chip-groups">
        {arrayFields.map((field) => (
          <div className="brief-chip-group" key={field.key}>
            <span>{field.label}</span>
            {brief[field.key].length > 0 ? (
              <div className="brief-chip-list">
                {brief[field.key].map((value) => (
                  <span className="brief-chip" key={value}>
                    {value}
                  </span>
                ))}
              </div>
            ) : (
              <p className="muted">Не указано</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function formatValue(value: string | number | null): string {
  if (value === null || value === "") return "Не указано";
  return String(value);
}
