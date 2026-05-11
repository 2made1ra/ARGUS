import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { PriceItemDetailOut } from "../api";
import { getCatalogItem } from "../api";

export default function CatalogItemPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<PriceItemDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setError(null);
    setDetail(null);
    getCatalogItem(id)
      .then(setDetail)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, [id]);

  if (!id) return <p className="error">Не передан id позиции каталога.</p>;
  if (error) return <p className="error">Ошибка загрузки позиции: {error}</p>;
  if (!detail) return <p className="muted">Загружаю позицию каталога...</p>;

  const { item } = detail;

  return (
    <main className="workspace catalog-detail-workspace">
      <header className="workspace-header catalog-detail-header">
        <div>
          <p className="eyebrow">Catalog item</p>
          <h1>{item.name}</h1>
        </div>
        <div className="catalog-detail-actions">
          <Link className="secondary-action" to="/catalog">
            Назад в каталог
          </Link>
        </div>
      </header>

      <section className="catalog-detail-grid">
        <article className="panel catalog-detail-main">
          <div className="section-heading">
            <h2>Факты позиции</h2>
            <span className="status-pill">{item.catalog_index_status}</span>
          </div>

          <dl className="catalog-detail-facts">
            <Fact label="Цена" value={`${item.unit_price} / ${item.unit}`} />
            <Fact label="Категория" value={item.category} />
            <Fact label="Поставщик" value={item.supplier} />
            <Fact label="Город поставщика" value={item.supplier_city} />
            <Fact label="ИНН" value={item.supplier_inn} />
            <Fact label="Телефон" value={item.supplier_phone} />
            <Fact label="Email" value={item.supplier_email} />
            <Fact label="НДС" value={item.has_vat} />
            <Fact label="Статус поставщика" value={item.supplier_status} />
            <Fact label="Раздел" value={item.section} />
            <Fact label="External ID" value={item.external_id} />
          </dl>
        </article>

        <aside className="panel catalog-provenance">
          <div className="section-heading">
            <h2>CSV provenance</h2>
            <span className="meta">{detail.sources.length} source</span>
          </div>
          <dl className="catalog-detail-facts">
            <Fact label="Import batch" value={item.import_batch_id} />
            <Fact label="Source file" value={item.source_file_id} />
            <Fact label="Embedding template" value={item.embedding_template_version} />
            <Fact label="Embedding model" value={item.embedding_model} />
          </dl>
        </aside>
      </section>

      <section className="panel catalog-source-panel">
        <div className="section-heading">
          <h2>Полный source_text</h2>
          <span className="meta">из price_items</span>
        </div>
        <pre>{item.source_text ?? "source_text отсутствует"}</pre>
      </section>

      {detail.sources.length > 0 && (
        <section className="panel catalog-source-panel">
          <div className="section-heading">
            <h2>Исходные строки</h2>
            <span className="meta">price_import_rows</span>
          </div>
          <div className="catalog-source-list">
            {detail.sources.map((source) => (
              <article
                className="catalog-source-row"
                key={`${source.source_kind}-${source.price_import_row_id ?? source.row_number}`}
              >
                <dl className="catalog-detail-facts">
                  <Fact label="Тип" value={source.source_kind} />
                  <Fact label="Строка CSV" value={source.row_number} />
                  <Fact label="Import batch" value={source.import_batch_id} />
                  <Fact label="Source file" value={source.source_file_id} />
                  <Fact label="Import row" value={source.price_import_row_id} />
                </dl>
                <pre>{source.source_text ?? "source_text отсутствует"}</pre>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function Fact({
  label,
  value,
}: {
  label: string;
  value: string | number | null;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value === null || value === "" ? "—" : value}</dd>
    </div>
  );
}
