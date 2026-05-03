import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDocument, getDocumentFacts } from "../api";
import type { DocumentFactsOut, DocumentOut } from "../api";
import DocumentStatus from "../components/DocumentStatus";
import FieldValidationForm from "../components/FieldValidationForm";

export default function DocumentValidationPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentOut | null>(null);
  const [facts, setFacts] = useState<DocumentFactsOut | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [factsError, setFactsError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoadError(null);
    getDocument(id)
      .then((nextDoc) => {
        setDoc(nextDoc);
        setStatus(nextDoc.status);
        if (nextDoc.status === "INDEXED") {
          loadFacts(id);
        }
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : String(err))
      );
  }, [id]);

  function loadFacts(documentId: string) {
    setFactsError(null);
    getDocumentFacts(documentId)
      .then(setFacts)
      .catch((err: unknown) =>
        setFactsError(err instanceof Error ? err.message : String(err))
      );
  }

  function handleStatusChange(nextStatus: string) {
    setStatus(nextStatus);
    if (nextStatus === "INDEXED" && id) {
      loadFacts(id);
    }
  }

  if (loadError) return <p className="error">Ошибка загрузки: {loadError}</p>;
  if (!doc) return <p className="muted">Загружаю документ...</p>;

  const currentStatus = status ?? doc.status;

  return (
    <main className="workspace workspace--wide validation-workspace">
      <header className="validation-header">
        <div className="validation-header__copy">
          <p className="eyebrow">Проверка полей</p>
          <h1>Подготовка договора</h1>
          <p className="validation-file-label">Загружается файл</p>
          <p className="validation-file-name" title={doc.title}>
            {doc.title}
          </p>
        </div>
        <p className="workspace-header__note">
          Подтвердите извлечённые поля перед сохранением договора в базу.
        </p>
      </header>

      <DocumentStatus
        documentId={doc.id}
        initialStatus={doc.status}
        onStatusChange={handleStatusChange}
      />

      {currentStatus !== "INDEXED" && currentStatus !== "FAILED" && (
        <section className="panel validation-wait">
          <h2>Документ обрабатывается</h2>
          <p className="muted">
            Форма с найденными полями появится здесь после завершения индексации.
          </p>
        </section>
      )}

      {currentStatus === "FAILED" && (
        <section className="empty-state">
          <h2>Обработка завершилась ошибкой</h2>
          <p className="muted">
            Вернитесь к списку договоров или загрузите файл повторно.
          </p>
          <Link className="secondary-action" to="/catalog">
            Перейти в каталог
          </Link>
        </section>
      )}

      {factsError && (
        <p className="error">Ошибка загрузки полей: {factsError}</p>
      )}

      {currentStatus === "INDEXED" && !facts && !factsError && (
        <p className="muted">Загружаю извлечённые поля...</p>
      )}

      {currentStatus === "INDEXED" && facts && (
        <FieldValidationForm facts={facts} documentId={doc.id} />
      )}
    </main>
  );
}
