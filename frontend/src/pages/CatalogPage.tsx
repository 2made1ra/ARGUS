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

  const totalDocuments = items.reduce((sum, item) => sum + item.document_count, 0);

  return (
    <main className="workspace catalog-workspace">
      <header className="workspace-header catalog-header">
        <div className="catalog-header__intro">
          <p className="eyebrow">Каталог</p>
          <h1>Каталог подрядчиков</h1>
          <p className="workspace-header__note">
            Подрядчики, найденные в загруженных договорах.
          </p>
        </div>
        <div className="catalog-controls">
          <div className="catalog-summary" aria-label="Сводка каталога">
            <span>
              <strong>{items.length}</strong>
              подрядчиков
            </span>
            <span>
              <strong>{totalDocuments}</strong>
              договоров
            </span>
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
        </div>
      </header>

      {error && <p className="error">Ошибка каталога: {error}</p>}
      {loading && <p className="muted">Загружаю каталог...</p>}

      {!loading && items.length === 0 && (
        <section className="empty-state">
          <p className="eyebrow">Пусто</p>
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
            <div className="catalog-card__body">
              <h2>{item.display_name}</h2>
              <p className="meta">
                <span>ИНН {item.inn ?? "—"}</span>
                <span>КПП {item.kpp ?? "—"}</span>
              </p>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
