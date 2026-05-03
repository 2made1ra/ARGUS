import { useEffect, useState } from "react";
import { API_URL } from "../api";

const STEPS = ["QUEUED", "PROCESSING", "RESOLVING", "INDEXING", "INDEXED"] as const;
type Step = (typeof STEPS)[number];

const STEP_LABELS: Record<Step, string> = {
  QUEUED: "В очереди",
  PROCESSING: "Извлечение",
  RESOLVING: "Проверка сторон",
  INDEXING: "Индексация",
  INDEXED: "Готово",
};

const STEP_DESCRIPTIONS: Record<Step, string> = {
  QUEUED: "Файл принят и ожидает обработки.",
  PROCESSING: "Распознаём документ и извлекаем содержимое.",
  RESOLVING: "Сопоставляем поставщика и заказчика.",
  INDEXING: "Готовим договор для поиска по базе.",
  INDEXED: "Можно проверить поля и сохранить договор.",
};

interface SSEPayload {
  status: string;
  document_id: string;
  error_message?: string;
}

interface Props {
  documentId: string;
  initialStatus?: string | null;
  onStatusChange?: (status: string) => void;
}

export default function DocumentStatus({
  documentId,
  initialStatus = null,
  onStatusChange,
}: Props) {
  const [status, setStatus] = useState<string | null>(initialStatus);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setStatus(initialStatus);
    setErrorMessage(null);
  }, [documentId, initialStatus]);

  useEffect(() => {
    const es = new EventSource(`${API_URL}/documents/${documentId}/stream`);

    es.onmessage = (event) => {
      const payload = JSON.parse(event.data as string) as SSEPayload;
      setStatus(payload.status);
      if (payload.error_message) setErrorMessage(payload.error_message);
      onStatusChange?.(payload.status);
      if (payload.status === "INDEXED" || payload.status === "FAILED") {
        es.close();
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => es.close();
  }, [documentId]); // onStatusChange intentionally excluded — caller passes a stable setter

  const currentIndex = status ? STEPS.indexOf(status as Step) : -1;
  const visibleIndex = currentIndex >= 0 ? currentIndex : 0;
  const progress = currentIndex >= 0 ? Math.round(((currentIndex + 1) / STEPS.length) * 100) : 0;
  const activeStep = currentIndex >= 0 ? STEPS[currentIndex] : null;

  return (
    <div className="document-status" aria-live="polite">
      <div className="document-status__topline">
        <div>
          <p className="document-status__label">Ход загрузки и обработки</p>
          <strong>
            {activeStep ? STEP_LABELS[activeStep] : "Подключение к обработке"}
          </strong>
        </div>
        <span>{progress}%</span>
      </div>

      <div
        className="document-status__bar"
        aria-label="Прогресс обработки документа"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={progress}
        role="progressbar"
      >
        <span style={{ width: `${progress}%` }} />
      </div>

      <ol className="document-status__steps">
        {STEPS.map((step, i) => {
          const done = visibleIndex > i;
          const active = status === step;
          return (
            <li
              className={[
                "document-status__step",
                done ? "document-status__step--done" : "",
                active ? "document-status__step--active" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              key={step}
            >
              <span>{i + 1}</span>
              <div>
                <strong>{STEP_LABELS[step]}</strong>
                <small>{STEP_DESCRIPTIONS[step]}</small>
              </div>
            </li>
          );
        })}
      </ol>

      {status === "FAILED" && (
        <div className="document-status__error">
          <strong>Ошибка обработки:</strong>{" "}
          {errorMessage ?? "Неизвестная ошибка"}
        </div>
      )}

      {!status && (
        <p className="muted">
          Подключение к потоку…
        </p>
      )}
    </div>
  );
}
