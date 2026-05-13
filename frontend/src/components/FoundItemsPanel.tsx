import { Link } from "react-router-dom";
import type { FoundItem } from "../api";
import { groupFoundItemsForDisplay } from "../utils/assistantCandidates";

interface Props {
  items: FoundItem[];
  loading?: boolean;
  title?: string;
  variant?: "panel" | "inline";
  emptyState?: "pending" | "no-results";
}

export default function FoundItemsPanel({
  items,
  loading = false,
  title = "Найденные позиции",
  variant = "panel",
  emptyState = "pending",
}: Props) {
  const groups = groupFoundItemsForDisplay(items);
  const emptyCopy = foundItemsEmptyCopy(emptyState);

  return (
    <section
      className={`found-items-panel ${
        variant === "panel" ? "panel" : "found-items-panel--inline"
      }`}
      aria-label={title}
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Catalog</p>
          <h2>{title}</h2>
        </div>
        <span className="meta">{loading ? "поиск..." : `${items.length} шт.`}</span>
      </div>

      {items.length === 0 ? (
        <div className="found-items-empty">
          <strong>{emptyCopy.title}</strong>
          <span>{emptyCopy.body}</span>
        </div>
      ) : (
        <div className="found-item-groups">
          {groups.map((group) => (
            <section className="found-item-group" key={group.title}>
              {groups.length > 1 && <h3>{group.title}</h3>}
              <div className="found-item-list">
                {group.items.map((item) => (
                  <Link
                    className="found-item-card"
                    key={item.id}
                    to={`/catalog/items/${item.id}`}
                  >
                    <div className="found-item-card__top">
                      <div>
                        <h4>{item.name}</h4>
                        <p className="meta">
                          {item.category ?? "Без категории"} ·{" "}
                          {formatScore(item.score)}
                        </p>
                      </div>
                      <span className="found-item-price">
                        {item.unit_price} / {item.unit}
                      </span>
                    </div>

                    <dl className="found-item-facts">
                      <div>
                        <dt>Поставщик</dt>
                        <dd>{item.supplier ?? "Не указан"}</dd>
                      </div>
                      <div>
                        <dt>Город</dt>
                        <dd>{item.supplier_city ?? "Не указан"}</dd>
                      </div>
                    </dl>

                    <div className="found-item-source">
                      <span>Исходный фрагмент</span>
                      <p>{item.source_text_snippet ?? "Фрагмент не передан API"}</p>
                    </div>

                    <div className="found-item-reason">
                      <span>{item.match_reason.label}</span>
                      <small>{item.match_reason.code}</small>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

function formatScore(score: number): string {
  return `score ${score.toFixed(2)}`;
}

function foundItemsEmptyCopy(emptyState: "pending" | "no-results"): {
  title: string;
  body: string;
} {
  if (emptyState === "no-results") {
    return {
      title: "В каталоге нет подходящих строк по этому запросу.",
      body: "Уточните город, категорию, бюджет или формат задачи и повторите поиск.",
    };
  }

  return {
    title: "Позиции появятся после поискового запроса.",
    body: "Ассистент может уточнять бриф без поиска, если потребность пока слишком общая.",
  };
}
