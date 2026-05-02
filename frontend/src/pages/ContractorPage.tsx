import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { ContractorProfileOut, DocumentOut, DocumentSearchResult } from "../api";
import {
  getContractor,
  listContractorDocuments,
  searchDocumentsForContractor,
} from "../api";
import DocumentResults from "../components/DocumentResults";
import SearchBar from "../components/SearchBar";

export default function ContractorPage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<ContractorProfileOut | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [results, setResults] = useState<DocumentSearchResult[] | null>(null);
  const [query, setQuery] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoadError(null);
    Promise.all([getContractor(id), listContractorDocuments(id)])
      .then(([nextProfile, nextDocuments]) => {
        setProfile(nextProfile);
        setDocuments(nextDocuments);
      })
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : String(err))
      );
  }, [id]);

  async function handleSearch(nextQuery: string) {
    if (!id) return;
    setQuery(nextQuery);
    setSearchError(null);
    try {
      setResults(await searchDocumentsForContractor(id, nextQuery));
    } catch (err) {
      setResults(null);
      setSearchError(err instanceof Error ? err.message : String(err));
    }
  }

  if (loadError) {
    return <p className="error">Ошибка загрузки контрагента: {loadError}</p>;
  }

  if (!profile) {
    return <p className="muted">Загружаю контрагента...</p>;
  }

  const contractor = profile.contractor;

  return (
    <div>
      <header className="page-header">
        <p className="eyebrow">Контрагент</p>
        <h1>{contractor.display_name}</h1>
        <p className="muted">
          ИНН: {contractor.inn ?? "—"} · КПП: {contractor.kpp ?? "—"}
        </p>
      </header>

      <section className="panel">
        <div className="section-heading">
          <h2>Документы</h2>
          <span className="meta">первые 20 · всего {profile.document_count}</span>
        </div>
        {documents.length === 0 ? (
          <p className="muted">Документы пока не привязаны.</p>
        ) : (
          <div className="document-list">
            {documents.map((doc) => (
              <Link className="document-row" to={`/documents/${doc.id}`} key={doc.id}>
                <span>{doc.title}</span>
                <span className="meta">{doc.created_at.slice(0, 10)}</span>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Поиск внутри контрагента</h2>
        <SearchBar
          onSearch={handleSearch}
          placeholder="Например: штрафы, срок оплаты, расторжение"
        />
        {searchError && <p className="error">Ошибка поиска: {searchError}</p>}
        {results && <DocumentResults results={results} query={query} />}
      </section>
    </div>
  );
}
