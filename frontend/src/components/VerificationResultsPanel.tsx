import type { SupplierVerificationResult } from "../api";

interface Props {
  results: SupplierVerificationResult[];
  variant?: "panel" | "inline";
}

const statusLabels: Record<SupplierVerificationResult["status"], string> = {
  active: "Действует в источнике",
  inactive: "Не действует",
  not_found: "Не найден",
  not_verified: "Не проверен",
  error: "Ошибка проверки",
};

export default function VerificationResultsPanel({
  results,
  variant = "panel",
}: Props) {
  return (
    <section
      className={`verification-panel ${
        variant === "panel" ? "panel" : "verification-panel--inline"
      }`}
      aria-label="Проверка поставщиков"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Verification</p>
          <h2>Проверка поставщиков</h2>
        </div>
        <span className="meta">{results.length} шт.</span>
      </div>

      {results.length === 0 ? (
        <p className="muted">Проверки появятся после явного запроса.</p>
      ) : (
        <div className="verification-list">
          {results.map((result, index) => (
            <article
              className="verification-item"
              key={`${result.item_id ?? "supplier"}-${result.supplier_inn ?? index}`}
            >
              <div className="verification-item__top">
                <h3>{result.supplier_name ?? "Поставщик не указан"}</h3>
                <span className={`verification-status verification-status--${result.status}`}>
                  {statusLabels[result.status]}
                </span>
              </div>
              <dl className="verification-facts">
                <div>
                  <dt>ИНН</dt>
                  <dd>{result.supplier_inn ?? "Нет в каталоге"}</dd>
                </div>
                <div>
                  <dt>Источник</dt>
                  <dd>{result.source}</dd>
                </div>
              </dl>
              {result.risk_flags.length > 0 && (
                <div className="verification-flags">
                  {result.risk_flags.map((flag) => (
                    <span key={flag}>{flag}</span>
                  ))}
                </div>
              )}
              {result.message && <p>{result.message}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
