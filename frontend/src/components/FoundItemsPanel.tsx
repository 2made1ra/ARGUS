import { Link } from "react-router-dom";
import type { FoundItem } from "../api";

interface Props {
  items: FoundItem[];
  loading?: boolean;
}

export default function FoundItemsPanel({ items, loading = false }: Props) {
  return (
    <section className="found-items-panel panel" aria-label="Найденные позиции">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Catalog</p>
          <h2>Найденные позиции</h2>
        </div>
        <span className="meta">{loading ? "поиск..." : `${items.length} шт.`}</span>
      </div>

      {items.length === 0 ? (
        <div className="found-items-empty">
          <strong>Позиции появятся после поискового запроса.</strong>
          <span>
            Ассистент может уточнять бриф без поиска, если потребность пока
            слишком общая.
          </span>
        </div>
      ) : (
        <div className="found-item-list">
          {items.map((item) => (
            <Link
              className="found-item-card"
              key={item.id}
              to={`/catalog/items/${item.id}`}
            >
              <div className="found-item-card__top">
                <div>
                  <h3>{item.name}</h3>
                  <p className="meta">
                    {item.category ?? "Без категории"} · {formatScore(item.score)}
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
      )}
    </section>
  );
}

function formatScore(score: number): string {
  return `score ${score.toFixed(2)}`;
}
