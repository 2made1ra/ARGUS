import { useEffect, useState } from "react";
import { API_URL } from "../api";

const STEPS = ["QUEUED", "PROCESSING", "RESOLVING", "INDEXING", "INDEXED"] as const;
type Step = (typeof STEPS)[number];

interface SSEPayload {
  status: string;
  document_id: string;
  error_message?: string;
}

interface Props {
  documentId: string;
  onStatusChange?: (status: string) => void;
}

export default function DocumentStatus({ documentId, onStatusChange }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  return (
    <div style={{ margin: "1.5rem 0" }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        {STEPS.map((step, i) => {
          const done = currentIndex > i;
          const active = status === step;
          return (
            <div key={step} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span
                style={{
                  padding: "0.25rem 0.75rem",
                  borderRadius: "999px",
                  fontSize: "0.85rem",
                  fontWeight: active ? 700 : 400,
                  background: active ? "#2563eb" : done ? "#93c5fd" : "#e5e7eb",
                  color: active || done ? "#fff" : "#6b7280",
                  transition: "background 0.3s, color 0.3s",
                }}
              >
                {step}
              </span>
              {i < STEPS.length - 1 && (
                <span style={{ color: "#9ca3af", userSelect: "none" }}>→</span>
              )}
            </div>
          );
        })}
      </div>

      {status === "FAILED" && (
        <div
          style={{
            marginTop: "1rem",
            padding: "0.75rem 1rem",
            background: "#fef2f2",
            border: "1px solid #fca5a5",
            borderRadius: "6px",
            color: "#b91c1c",
          }}
        >
          <strong>Ошибка обработки:</strong>{" "}
          {errorMessage ?? "Неизвестная ошибка"}
        </div>
      )}

      {!status && (
        <p style={{ color: "#6b7280", fontSize: "0.9rem", marginTop: "0.5rem" }}>
          Подключение к потоку…
        </p>
      )}
    </div>
  );
}
