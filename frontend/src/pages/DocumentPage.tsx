import {
  Link,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { useEffect, useState } from "react";
import { API_URL, answerDocument, deleteDocument, getDocument } from "../api";
import type {
  ChatMessage,
  DocumentOut,
} from "../api";
import RagChat from "../components/RagChat";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocumentOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoadError(null);
    getDocument(id)
      .then(setDoc)
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : String(err))
      );
  }, [id]);

  async function handleDelete() {
    if (!doc || deleting) return;
    const confirmed = window.confirm(
      "Удалить договор из базы? Связанные поля, summary и чанки будут удалены."
    );
    if (!confirmed) return;

    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteDocument(doc.id);
      navigate("/catalog");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err));
      setDeleting(false);
    }
  }

  if (loadError) return <p className="error">Ошибка загрузки: {loadError}</p>;
  if (!doc) return <p className="muted">Загружаю документ...</p>;

  const previewUrl = `${API_URL}/documents/${doc.id}/preview${documentPreviewHash(
    location.hash,
  )}`;

  return (
    <main className="workspace workspace--wide document-workspace">
      <header className="workspace-header document-header">
        <div>
          <p className="eyebrow">Document</p>
          <h1>{doc.title}</h1>
        </div>
        <div className="document-actions">
          <p className="workspace-header__note">
            {doc.status} · {doc.document_kind ?? "kind не определен"}
          </p>
          <div className="document-action-row">
            <Link className="secondary-action" to={`/documents/${doc.id}/validate`}>
              Редактировать поля
            </Link>
            <button
              className="danger-action"
              type="button"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Удаляю..." : "Удалить договор"}
            </button>
          </div>
          {deleteError && (
            <p className="error">Ошибка удаления: {deleteError}</p>
          )}
        </div>
      </header>

      <section className="document-split">
        <div className="document-preview">
          <div className="section-heading">
            <h2>Предпросмотр</h2>
            <span className="meta">PDF</span>
          </div>
          {doc.preview_available ? (
            <iframe title={doc.title} src={previewUrl} />
          ) : (
            <div className="empty-state empty-state--compact">
              <h2>Preview пока недоступен</h2>
              <p className="muted">
                PDF появится после обработки или если исходный файл уже был PDF.
              </p>
            </div>
          )}
        </div>

        <RagChat
          title="Чат по договору"
          placeholder="Например: дай summary договора или найди риски"
          emptyHint="Вопросы здесь ограничены выбранным документом."
          onAsk={(message: string, history: ChatMessage[]) =>
            answerDocument(doc.id, message, history)
          }
        />
      </section>
    </main>
  );
}

function documentPreviewHash(hash: string): string {
  const pageMatch = hash.match(/^#page=(\d+)$/);
  if (!pageMatch) return "";
  return `#page=${pageMatch[1]}`;
}
