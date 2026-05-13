import { Link } from "react-router-dom";
import type { FoundItem } from "../api";
import {
  groupFoundItemsForDisplay,
  orderFoundItemsForDisplay,
} from "../utils/assistantCandidates";

interface Props {
  items: FoundItem[];
  loading?: boolean;
  title?: string;
  variant?: "panel" | "inline";
  emptyState?: "pending" | "no-results";
  selectedItemIds?: string[];
  onSelectedItemIdsChange?: (itemIds: string[]) => void;
}

export default function FoundItemsPanel({
  items,
  loading = false,
  title = "Найденные позиции",
  variant = "panel",
  emptyState = "pending",
  selectedItemIds = [],
  onSelectedItemIdsChange,
}: Props) {
  const groups = groupFoundItemsForDisplay(items);
  const orderedItems = orderFoundItemsForDisplay(items);
  const selectedIdSet = new Set(selectedItemIds);
  const itemsById = new Map(orderedItems.map((item) => [item.id, item]));
  const ordinalById = new Map(
    orderedItems.map((item, index) => [item.id, index + 1]),
  );
  const selectedItems = selectedItemIds
    .map((itemId) => itemsById.get(itemId))
    .filter((item): item is FoundItem => item !== undefined);
  const emptyCopy = foundItemsEmptyCopy(emptyState);

  function handleItemSelected(itemId: string, selected: boolean): void {
    if (onSelectedItemIdsChange === undefined) return;
    if (selected) {
      onSelectedItemIdsChange([...selectedItemIds, itemId].filter(unique));
      return;
    }
    onSelectedItemIdsChange(selectedItemIds.filter((id) => id !== itemId));
  }

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
                  <article
                    className={`found-item-card ${
                      selectedIdSet.has(item.id) ? "found-item-card--selected" : ""
                    }`}
                    key={item.id}
                  >
                    <div className="found-item-card__actions">
                      <span className="candidate-ordinal">
                        Вариант {ordinalById.get(item.id)}
                      </span>
                      <label className="candidate-selection">
                        <input
                          aria-label={
                            selectedIdSet.has(item.id)
                              ? `Убрать ${item.name} из подборки`
                              : `Добавить ${item.name} в подборку`
                          }
                          type="checkbox"
                          checked={selectedIdSet.has(item.id)}
                          readOnly={onSelectedItemIdsChange === undefined}
                          onChange={(event) =>
                            handleItemSelected(item.id, event.currentTarget.checked)
                          }
                        />
                        <span>
                          {selectedIdSet.has(item.id)
                            ? "В подборке"
                            : "В подборку"}
                        </span>
                      </label>
                      <Link
                        className="found-item-open-link"
                        to={`/catalog/items/${item.id}`}
                      >
                        Открыть карточку
                      </Link>
                    </div>
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
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {selectedItems.length > 0 && (
        <section
          className="selected-items-section"
          aria-label="Выбрано в подборку"
        >
          <div className="selected-items-section__heading">
            <h3>Выбрано в подборку</h3>
            <span className="meta">{selectedItems.length} шт.</span>
          </div>
          <div className="selected-item-list">
            {selectedItems.map((item) => (
              <article className="selected-item-card" key={item.id}>
                <div>
                  <h4>{item.name}</h4>
                  <p className="meta">
                    {item.supplier ?? "Поставщик не указан"} ·{" "}
                    {item.unit_price} / {item.unit}
                  </p>
                </div>
                <Link
                  className="found-item-open-link"
                  to={`/catalog/items/${item.id}`}
                >
                  Открыть
                </Link>
              </article>
            ))}
          </div>
        </section>
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

function unique(value: string, index: number, values: string[]): boolean {
  return values.indexOf(value) === index;
}
