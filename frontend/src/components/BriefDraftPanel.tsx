import type { BriefState } from "../api";

interface Props {
  brief: BriefState;
  onReset?: () => void;
}

type BriefFact = {
  label: string;
  value: string | null;
};

type BriefChipGroup = {
  title: string;
  items: string[];
  empty: string;
};

const openQuestionLabels: Record<string, string> = {
  event_type: "Какой тип мероприятия?",
  event_goal: "Какая цель мероприятия?",
  concept: "Какая концепция?",
  format: "Какой формат события?",
  city: "В каком городе проходит событие?",
  date_or_period: "Дата или период?",
  audience_size: "Сколько гостей ожидается?",
  venue: "Какая площадка?",
  venue_status: "Площадка уже есть?",
  venue_constraints: "Есть ли ограничения площадки?",
  budget_total: "Какой общий бюджет?",
  budget_per_guest: "Какой бюджет на гостя?",
  event_level: "Какой уровень мероприятия?",
  service_needs: "Какие услуги нужны?",
  selected_item_ids: "Какие позиции выбраны в подборку?",
};

export default function BriefDraftPanel({ brief, onReset }: Props) {
  const primaryFacts = compactFacts([
    { label: "Тип мероприятия", value: brief.event_type },
    { label: "Город", value: brief.city },
    {
      label: "Аудитория",
      value:
        brief.audience_size === null ? null : `${brief.audience_size} гостей`,
    },
    { label: "Дата/период", value: brief.date_or_period },
  ]);
  const conceptFacts = compactFacts([
    { label: "Цель", value: brief.event_goal },
    { label: "Концепция", value: brief.concept },
    { label: "Формат", value: brief.format },
    { label: "Уровень", value: brief.event_level },
  ]);
  const venueFacts = compactFacts([
    { label: "Статус", value: formatTextValue(brief.venue_status) },
    { label: "Площадка", value: brief.venue },
    { label: "Окно времени", value: brief.duration_or_time_window },
  ]);
  const budgetFacts = compactFacts([
    {
      label: "Общий бюджет",
      value: formatMoney(brief.budget_total),
    },
    {
      label: "На гостя",
      value: formatMoney(brief.budget_per_guest),
    },
    { label: "Заметки", value: brief.budget_notes },
  ]);
  const serviceGroups = serviceBlockGroups(brief);
  const openQuestions = brief.open_questions.map(formatOpenQuestion);

  return (
    <section className="brief-panel panel" aria-label="Черновик брифа">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Brief</p>
          <h2>Черновик брифа</h2>
        </div>
        <div className="section-heading__actions">
          <span className="meta">{knownFactCount(brief)} фактов</span>
          {onReset && (
            <button
              className="btn-ghost btn-ghost--danger btn-sm"
              onClick={onReset}
              title="Сбросить бриф и вернуться к поиску"
              type="button"
            >
              Сбросить
            </button>
          )}
        </div>
      </div>

      <div className="brief-panel__sections">
        <BriefFactSection
          empty="Основные параметры пока не зафиксированы."
          facts={primaryFacts}
          title="Основное"
        />
        <BriefFactSection
          empty="Цель, концепция и уровень пока открыты."
          facts={conceptFacts}
          title="Концепция и уровень"
        />
        <BriefFactSection
          empty="Статус площадки и ограничения пока не уточнены."
          facts={venueFacts}
          title="Площадка"
        />
        <BriefChipSection
          empty="Ограничения площадки пока не указаны."
          items={formatTextList(brief.venue_constraints)}
          title="Ограничения площадки"
        />
        <BriefFactSection
          empty="Бюджет пока не указан."
          facts={budgetFacts}
          title="Бюджет"
        />
        <BriefChipGroups
          groups={serviceGroups}
          title="Блоки услуг"
        />
        <BriefChipSection
          empty="Пока нет выбранных позиций."
          items={brief.selected_item_ids}
          title="Выбранные позиции"
        />
        <BriefChipSection
          empty="Открытых вопросов пока нет."
          items={openQuestions}
          title="Открытые вопросы"
        />
      </div>
    </section>
  );
}

function BriefFactSection({
  title,
  facts,
  empty,
}: {
  title: string;
  facts: BriefFact[];
  empty: string;
}) {
  return (
    <section className="brief-section">
      <h3>{title}</h3>
      {facts.length > 0 ? (
        <dl className="brief-grid">
          {facts.map((fact) => (
            <div className="brief-grid__row" key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="brief-empty">{empty}</p>
      )}
    </section>
  );
}

function BriefChipGroups({
  title,
  groups,
}: {
  title: string;
  groups: BriefChipGroup[];
}) {
  const hasItems = groups.some((group) => group.items.length > 0);

  return (
    <section className="brief-section">
      <h3>{title}</h3>
      {hasItems ? (
        <div className="brief-chip-groups">
          {groups.map((group) => (
            <div className="brief-chip-group" key={group.title}>
              <span>{group.title}</span>
              {group.items.length > 0 ? (
                <div className="brief-chip-list">
                  {group.items.map((item) => (
                    <span className="brief-chip" key={item}>
                      {item}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="brief-empty">{group.empty}</p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="brief-empty">Услуги пока не спланированы.</p>
      )}
    </section>
  );
}

function BriefChipSection({
  title,
  items,
  empty,
}: {
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <section className="brief-section">
      <h3>{title}</h3>
      {items.length > 0 ? (
        <div className="brief-chip-list">
          {items.map((item) => (
            <span className="brief-chip" key={item}>
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="brief-empty">{empty}</p>
      )}
    </section>
  );
}

function serviceBlockGroups(brief: BriefState): BriefChipGroup[] {
  return [
    {
      title: "Потребности",
      items: brief.service_needs.map((need) =>
        [
          need.category,
          servicePriorityLabel(need.priority),
          need.notes,
        ].filter(Boolean).join(" · "),
      ),
      empty: "Потребности пока не указаны.",
    },
    {
      title: "Требуемые",
      items: brief.required_services,
      empty: "Требуемые услуги пока не указаны.",
    },
    {
      title: "Обязательные",
      items: brief.must_have_services,
      empty: "Обязательные услуги пока не указаны.",
    },
    {
      title: "Желательные",
      items: brief.nice_to_have_services,
      empty: "Желательные услуги пока не указаны.",
    },
  ];
}

function servicePriorityLabel(priority: string): string {
  if (priority === "must_have") return "обязательно";
  if (priority === "nice_to_have") return "желательно";
  return "нужно";
}

function compactFacts(facts: BriefFact[]): BriefFact[] {
  return facts.filter((fact): fact is BriefFact => Boolean(fact.value));
}

function knownFactCount(brief: BriefState): number {
  return [
    brief.event_type,
    brief.event_goal,
    brief.concept,
    brief.format,
    brief.city,
    brief.date_or_period,
    brief.audience_size,
    brief.venue,
    brief.venue_status,
    brief.event_level,
    brief.budget_total,
    brief.budget_per_guest,
    brief.budget_notes,
    ...brief.venue_constraints,
    ...brief.service_needs.map((need) => need.category),
    ...brief.required_services,
    ...brief.must_have_services,
    ...brief.nice_to_have_services,
    ...brief.selected_item_ids,
  ].filter(Boolean).length;
}

function formatOpenQuestion(value: string): string {
  if (openQuestionLabels[value] !== undefined) {
    return openQuestionLabels[value];
  }
  if (value.includes("_")) {
    return `Уточнить: ${value.replaceAll("_", " ")}`;
  }
  return value;
}

function formatMoney(value: number | null): string | null {
  if (value === null) return null;
  return `${String(value).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} ₽`;
}

function formatTextValue(value: string | null): string | null {
  if (value === null || value.trim() === "") return null;
  return capitalizeFirst(value.trim());
}

function formatTextList(values: string[]): string[] {
  return values
    .map((value) => formatTextValue(value))
    .filter((value): value is string => value !== null);
}

function capitalizeFirst(value: string): string {
  return value.charAt(0).toLocaleUpperCase("ru-RU") + value.slice(1);
}
