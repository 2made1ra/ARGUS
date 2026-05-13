import type { FoundItem, SupplierVerificationResult } from "../api";
import {
  formatSupplierCount,
  formatVerificationCheckedAt,
  groupVerificationResults,
  verificationStatusLabel,
} from "../utils/assistantVerification";

interface Props {
  results: SupplierVerificationResult[];
  variant?: "panel" | "inline";
  relatedItems?: FoundItem[];
}

export default function VerificationResultsPanel({
  results,
  variant = "panel",
  relatedItems = [],
}: Props) {
  const groups = groupVerificationResults(results, relatedItems);

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
        <span className="meta">{formatSupplierCount(groups.length)}</span>
      </div>

      {groups.length === 0 ? (
        <p className="muted">Проверки появятся после явного запроса.</p>
      ) : (
        <div className="verification-list">
          {groups.map(({ key, result, relatedItems, riskFlags }) => {
            const checkedAt = formatVerificationCheckedAt(result.checked_at);

            return (
              <article className="verification-item" key={key}>
                <div className="verification-item__top">
                  <h3>{result.supplier_name ?? "Поставщик не указан"}</h3>
                  <span
                    className={`verification-status verification-status--${result.status}`}
                  >
                    {verificationStatusLabel(result.status)}
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
                  {checkedAt !== null && (
                    <div>
                      <dt>Проверено</dt>
                      <dd>{checkedAt}</dd>
                    </div>
                  )}
                </dl>
                {riskFlags.length > 0 && (
                  <div className="verification-flags">
                    {riskFlags.map((flag) => (
                      <span key={flag}>{flag}</span>
                    ))}
                  </div>
                )}
                {relatedItems.length > 0 && (
                  <div className="verification-related">
                    <span>Связанные карточки</span>
                    <ul>
                      {relatedItems.map(({ item, ordinal }) => (
                        <li key={item.id}>
                          Вариант {ordinal}: {item.name}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.message && <p>{result.message}</p>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
