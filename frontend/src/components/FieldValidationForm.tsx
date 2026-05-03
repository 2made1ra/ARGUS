import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { patchDocumentFacts } from "../api";
import type { DocumentFactsOut } from "../api";

const FIELD_LABELS: Record<string, string> = {
  document_type: "Тип документа",
  document_number: "Номер документа",
  document_date: "Дата документа",
  service_date: "Дата оказания услуг",
  valid_until: "Действует до",
  amount: "Сумма",
  vat: "НДС",
  supplier_name: "Поставщик",
  supplier_inn: "ИНН поставщика",
  supplier_kpp: "КПП поставщика",
  supplier_bik: "БИК поставщика",
  supplier_account: "Счёт поставщика",
  customer_name: "Заказчик",
  customer_inn: "ИНН заказчика",
  customer_kpp: "КПП заказчика",
  customer_bik: "БИК заказчика",
  customer_account: "Счёт заказчика",
  service_subject: "Предмет услуг",
  service_price: "Стоимость услуг",
  signatory_name: "Подписант",
  contact_phone: "Телефон",
};

const FIELD_ORDER = Object.keys(FIELD_LABELS);

interface Props {
  facts: DocumentFactsOut;
  documentId: string;
}

function toInputValue(v: unknown): string {
  if (v === null || v === undefined || v === "null") return "";
  return String(v);
}

export default function FieldValidationForm({ facts, documentId }: Props) {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showToast, setShowToast] = useState(false);

  const initialFields: Record<string, string> = {};
  for (const key of FIELD_ORDER) {
    initialFields[key] = toInputValue(facts.fields[key]);
  }
  for (const key of Object.keys(facts.fields)) {
    if (!(key in initialFields)) {
      initialFields[key] = toInputValue(facts.fields[key]);
    }
  }

  const [fieldValues, setFieldValues] = useState<Record<string, string>>(initialFields);

  function handleFieldChange(key: string, value: string) {
    setFieldValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    try {
      const fields: Record<string, string | null> = {};
      for (const [k, v] of Object.entries(fieldValues)) {
        fields[k] = v.trim() === "" ? null : v.trim();
      }
      await patchDocumentFacts(documentId, {
        fields,
        summary: facts.summary,
        key_points: facts.key_points,
      });
      setShowToast(true);
      setTimeout(() => {
        navigate("/");
      }, 1200);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
      setSaving(false);
    }
  }

  const orderedKeys = [
    ...FIELD_ORDER.filter((k) => k in fieldValues),
    ...Object.keys(fieldValues).filter((k) => !FIELD_ORDER.includes(k)),
  ];

  return (
    <div className="validation-form">
      <section className="panel">
        <h2 style={{ marginBottom: "1.25rem" }}>Поля</h2>
        <div className="validation-fields-grid">
          {orderedKeys.map((key) => (
            <div key={key} className="validation-field">
              <label htmlFor={`field-${key}`}>
                {FIELD_LABELS[key] ?? key}
              </label>
              <input
                id={`field-${key}`}
                type="text"
                value={fieldValues[key] ?? ""}
                onChange={(e) => handleFieldChange(key, e.target.value)}
                disabled={saving}
              />
            </div>
          ))}
        </div>
      </section>

      {facts.summary && (
        <section className="panel">
          <h2 style={{ marginBottom: "0.75rem" }}>Саммари</h2>
          <div className="validation-summary">{facts.summary}</div>
        </section>
      )}

      {facts.key_points.length > 0 && (
        <section className="panel">
          <h2 style={{ marginBottom: "0.75rem" }}>Ключевые моменты</h2>
          <ul style={{ paddingLeft: "1.5rem", lineHeight: 1.8 }}>
            {facts.key_points.map((pt, i) => (
              <li key={i}>{pt}</li>
            ))}
          </ul>
        </section>
      )}

      {saveError && (
        <p className="error" style={{ marginBottom: "0.75rem" }}>
          Ошибка сохранения: {saveError}
        </p>
      )}

      <button
        className="validation-save-btn"
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? "Сохраняю…" : "Сохранить в базу"}
      </button>

      {showToast && (
        <div className="toast-success">Документ сохранён ✓</div>
      )}
    </div>
  );
}
