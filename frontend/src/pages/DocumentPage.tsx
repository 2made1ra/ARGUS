import { Fragment, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { API_URL, answerDocument, getDocument, getDocumentFacts, searchWithinDocument } from "../api";
import type {
  ChatMessage,
  DocumentFactsOut,
  DocumentOut,
  WithinDocumentResult,
} from "../api";
import ChunkResults from "../components/ChunkResults";
import DocumentStatus from "../components/DocumentStatus";
import FieldValidationForm from "../components/FieldValidationForm";
import RagChat from "../components/RagChat";
import SearchBar from "../components/SearchBar";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentOut | null>(null);
  const [facts, setFacts] = useState<DocumentFactsOut | null>(null);
  const [chunkResults, setChunkResults] = useState<WithinDocumentResult[] | null>(null);
  const [query, setQuery] = useState("");
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoadError(null);
    getDocument(id)
      .then((nextDoc) => {
        setDoc(nextDoc);
        if (nextDoc.status === "INDEXED") {
          getDocumentFacts(id).then(setFacts).catch(() => {});
        }
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : String(err))
      );
  }, [id]);

  useEffect(() => {
    if (liveStatus !== "INDEXED" || !id) return;
    getDocumentFacts(id).then(setFacts).catch(() => {});
  }, [liveStatus, id]);

  function handleStatusChange(status: string) {
    setLiveStatus(status);
    if (status === "INDEXED") setIsValidating(true);
  }

  async function handleSearch(nextQuery: string) {
    if (!id) return;
    setQuery(nextQuery);
    setSearchError(null);
    try {
      setChunkResults(await searchWithinDocument(id, nextQuery));
    } catch (err) {
      setChunkResults(null);
      setSearchError(err instanceof Error ? err.message : String(err));
    }
  }

  if (loadError) return <p className="error">Ошибка загрузки: {loadError}</p>;
  if (!doc) return <p className="muted">Загружаю документ...</p>;

  const status = liveStatus ?? doc.status;
  const previewUrl = `${API_URL}/documents/${doc.id}/preview`;

  return (
    <main className="workspace workspace--wide">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Document</p>
          <h1>{doc.title}</h1>
        </div>
        <p className="workspace-header__note">
          {status} · {doc.document_kind ?? "kind не определен"}
        </p>
      </header>

      <DocumentStatus documentId={doc.id} onStatusChange={handleStatusChange} />

      {status === "INDEXED" && facts && isValidating && (
        <FieldValidationForm facts={facts} documentId={doc.id} />
      )}

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

        <div className="document-side">
          <RagChat
            title="Чат по договору"
            placeholder="Например: дай summary договора или найди риски"
            emptyHint="Вопросы здесь ограничены выбранным документом."
            onAsk={(message: string, history: ChatMessage[]) =>
              answerDocument(doc.id, message, history)
            }
          />

          {status === "INDEXED" && facts && !isValidating && (
            <DocumentFacts facts={facts} />
          )}
        </div>
      </section>

      {status === "INDEXED" && !isValidating && (
        <section className="panel panel--flat document-search">
          <h2>Точный поиск внутри документа</h2>
          <SearchBar
            onSearch={handleSearch}
            placeholder="Найти фрагмент в тексте документа"
          />
          {searchError && <p className="error">Ошибка поиска: {searchError}</p>}
          {chunkResults && <ChunkResults results={chunkResults} query={query} />}
        </section>
      )}
    </main>
  );
}

function DocumentFacts({ facts }: { facts: DocumentFactsOut }) {
  return (
    <section className="facts-panel">
      <h2>Факты документа</h2>
      {facts.summary && <p className="facts-summary">{facts.summary}</p>}
      <dl className="facts-grid">
        {Object.entries(facts.fields)
          .filter(([, value]) => value !== null && value !== "")
          .slice(0, 8)
          .map(([key, value]) => (
            <Fragment key={key}>
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </Fragment>
          ))}
      </dl>
      {facts.key_points.length > 0 && (
        <ul className="key-points">
          {facts.key_points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
