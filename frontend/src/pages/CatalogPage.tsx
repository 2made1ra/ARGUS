import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ContractorCatalogItem } from "../api";
import { listContractors } from "../api";

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<ContractorCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listContractors(query)
      .then((nextItems) => {
        if (!cancelled) setItems(nextItems);
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
  }, [query]);

  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Catalog</p>
          <h1>Каталог подрядчиков</h1>
        </div>
        <label className="catalog-filter">
          <span>Фильтр</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Название, ИНН или КПП"
          />
        </label>
      </header>

      {error && <p className="error">Ошибка каталога: {error}</p>}
      {loading && <p className="muted">Загружаю каталог...</p>}

      {!loading && items.length === 0 && (
        <section className="empty-state">
          <p className="eyebrow">Empty</p>
          <h2>Подрядчики пока не найдены</h2>
          <p className="muted">
            Загрузите договоры и дождитесь резолва подрядчика, чтобы каталог
            наполнился.
          </p>
        </section>
      )}

      <div className="catalog-grid">
        {items.map((item) => (
          <Link className="catalog-card" key={item.id} to={`/contractors/${item.id}`}>
            <div>
              <h2>{item.display_name}</h2>
              <p className="meta">ИНН {item.inn ?? "—"} · КПП {item.kpp ?? "—"}</p>
            </div>
            <div className="catalog-card__metric">
              <strong>{item.document_count}</strong>
              <span>договоров</span>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
