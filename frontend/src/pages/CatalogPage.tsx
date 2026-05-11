import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { PriceItemOut } from "../api";
import { listCatalogItems } from "../api";

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PriceItemOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listCatalogItems(100, 0)
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
        setTotal(response.total);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ru-RU");
    if (!normalizedQuery) return items;

    return items.filter((item) =>
      [
        item.name,
        item.category,
        item.supplier,
        item.supplier_city,
        item.supplier_inn,
        item.unit,
        item.unit_price,
      ]
        .filter((value): value is string => value !== null)
        .some((value) =>
          value.toLocaleLowerCase("ru-RU").includes(normalizedQuery),
        ),
    );
  }, [items, query]);

  const indexedCount = items.filter(
    (item) => item.catalog_index_status === "indexed",
  ).length;

  return (
    <main className="workspace catalog-workspace">
      <header className="workspace-header catalog-header">
        <div className="catalog-header__intro">
          <p className="eyebrow">Каталог</p>
          <h1>Позиции price_items</h1>
          <p className="workspace-header__note">
            Административная таблица импортированных строк каталога. Детальная
            карточка показывает полный source_text и CSV provenance.
          </p>
        </div>
        <div className="catalog-controls">
          <div className="catalog-summary" aria-label="Сводка каталога">
            <span>
              <strong>{total}</strong>
              всего
            </span>
            <span>
              <strong>{indexedCount}</strong>
              indexed
            </span>
          </div>
          <label className="catalog-filter">
            <span>Фильтр</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Название, поставщик, ИНН или город"
            />
          </label>
        </div>
      </header>

      {error && <p className="error">Ошибка каталога: {error}</p>}
      {loading && <p className="muted">Загружаю каталог...</p>}

      {!loading && items.length === 0 && (
        <section className="empty-state">
          <p className="eyebrow">Пусто</p>
          <h2>Позиции каталога пока не импортированы</h2>
          <p className="muted">
            Импортируйте prices.csv через backend endpoint, затем проиндексируйте
            строки в price_items_search_v1.
          </p>
        </section>
      )}

      {!loading && items.length > 0 && filteredItems.length === 0 && (
        <section className="empty-state empty-state--compact">
          <p className="eyebrow">Фильтр</p>
          <h2>Совпадений нет</h2>
        </section>
      )}

      {filteredItems.length > 0 && (
        <section className="catalog-table-wrap">
          <table className="catalog-table">
            <thead>
              <tr>
                <th>Позиция</th>
                <th>Цена</th>
                <th>Поставщик</th>
                <th>Категория</th>
                <th>Индекс</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link className="catalog-item-link" to={`/catalog/items/${item.id}`}>
                      {item.name}
                    </Link>
                    <span className="catalog-table__meta">
                      {item.unit} · {item.supplier_city ?? "город не указан"}
                    </span>
                  </td>
                  <td>
                    <strong>{item.unit_price}</strong>
                    <span className="catalog-table__meta">{item.has_vat ?? "НДС —"}</span>
                  </td>
                  <td>
                    {item.supplier ?? "Не указан"}
                    <span className="catalog-table__meta">
                      ИНН {item.supplier_inn ?? "—"}
                    </span>
                  </td>
                  <td>{item.category ?? "—"}</td>
                  <td>
                    <span className="status-pill">{item.catalog_index_status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
