import type { BriefState } from "../api";

interface Props {
  brief: BriefState;
}

const scalarFields: Array<{
  key: keyof Pick<
    BriefState,
    | "event_type"
    | "event_goal"
    | "concept"
    | "format"
    | "city"
    | "date_or_period"
    | "audience_size"
    | "venue"
    | "venue_status"
    | "duration_or_time_window"
    | "budget"
    | "budget_total"
    | "budget_per_guest"
    | "budget_notes"
    | "catering_format"
    | "event_level"
  >;
  label: string;
}> = [
  { key: "event_type", label: "Формат" },
  { key: "event_goal", label: "Цель" },
  { key: "concept", label: "Концепция" },
  { key: "format", label: "Тип участия" },
  { key: "city", label: "Город" },
  { key: "date_or_period", label: "Дата/период" },
  { key: "audience_size", label: "Гостей" },
  { key: "venue", label: "Площадка" },
  { key: "venue_status", label: "Статус площадки" },
  { key: "duration_or_time_window", label: "Время" },
  { key: "budget", label: "Бюджет legacy" },
  { key: "budget_total", label: "Бюджет общий" },
  { key: "budget_per_guest", label: "На гостя" },
  { key: "budget_notes", label: "Заметки бюджета" },
  { key: "catering_format", label: "Кейтеринг" },
  { key: "event_level", label: "Уровень" },
];

const arrayFields: Array<{
  key: keyof Pick<
    BriefState,
    | "venue_constraints"
    | "technical_requirements"
    | "required_services"
    | "must_have_services"
    | "nice_to_have_services"
    | "selected_item_ids"
    | "constraints"
    | "preferences"
    | "open_questions"
  >;
  label: string;
}> = [
  { key: "venue_constraints", label: "Ограничения площадки" },
  { key: "technical_requirements", label: "Технические требования" },
  { key: "required_services", label: "Требуемые услуги" },
  { key: "must_have_services", label: "Обязательные услуги" },
  { key: "nice_to_have_services", label: "Желательные услуги" },
  { key: "selected_item_ids", label: "Выбранные позиции" },
  { key: "constraints", label: "Ограничения" },
  { key: "preferences", label: "Предпочтения" },
  { key: "open_questions", label: "Открытые вопросы" },
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
        <div className="brief-chip-group">
          <span>Потребности в услугах</span>
          {brief.service_needs.length > 0 ? (
            <div className="brief-chip-list">
              {brief.service_needs.map((need) => (
                <span
                  className="brief-chip"
                  key={`${need.category}-${need.priority}-${need.source}`}
                >
                  {need.category} · {need.priority}
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">Не указано</p>
          )}
        </div>

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
