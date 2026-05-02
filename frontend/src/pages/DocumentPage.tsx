import { Fragment, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import DocumentStatus from "../components/DocumentStatus";
import { getDocument, getDocumentFacts } from "../api";
import type { DocumentOut, DocumentFactsOut } from "../api";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentOut | null>(null);
  const [facts, setFacts] = useState<DocumentFactsOut | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getDocument(id)
      .then(setDoc)
      .catch((err: unknown) => setLoadError(String(err)));
  }, [id]);

  // Load facts once the document reaches INDEXED
  useEffect(() => {
    if (liveStatus !== "INDEXED" || !id) return;
    getDocumentFacts(id).then(setFacts).catch(() => {});
  }, [liveStatus, id]);

  const status = liveStatus ?? doc?.status ?? null;

  if (loadError) {
    return <p style={{ color: "#b91c1c" }}>Ошибка загрузки: {loadError}</p>;
  }

  if (!doc) {
    return <p style={{ color: "#6b7280" }}>Загружаю…</p>;
  }

  return (
    <div>
      <h1 style={{ marginBottom: "0.25rem" }}>{doc.title}</h1>
      <p style={{ color: "#6b7280", fontSize: "0.85rem", marginBottom: "1rem" }}>
        ID: {doc.id}
      </p>

      <DocumentStatus documentId={doc.id} onStatusChange={setLiveStatus} />

      {status === "INDEXED" && facts && (
        <div style={{ marginTop: "2rem" }}>
          <section style={{ marginBottom: "1.5rem" }}>
            <h2 style={{ marginBottom: "0.75rem" }}>Поля</h2>
            {Object.keys(facts.fields).length === 0 ? (
              <p style={{ color: "#6b7280" }}>—</p>
            ) : (
              <dl
                style={{
                  display: "grid",
                  gridTemplateColumns: "max-content 1fr",
                  gap: "0.3rem 1rem",
                }}
              >
                {Object.entries(facts.fields).map(([k, v]) => (
                  <Fragment key={k}>
                    <dt style={{ fontWeight: 600, color: "#374151" }}>{k}</dt>
                    <dd style={{ margin: 0 }}>{String(v)}</dd>
                  </Fragment>
                ))}
              </dl>
            )}
          </section>

          {facts.summary && (
            <section style={{ marginBottom: "1.5rem" }}>
              <h2 style={{ marginBottom: "0.75rem" }}>Summary</h2>
              <p style={{ lineHeight: 1.7 }}>{facts.summary}</p>
            </section>
          )}

          {facts.key_points.length > 0 && (
            <section>
              <h2 style={{ marginBottom: "0.75rem" }}>Key points</h2>
              <ul style={{ paddingLeft: "1.5rem", lineHeight: 1.8 }}>
                {facts.key_points.map((pt, i) => (
                  <li key={i}>{pt}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
