import { useNavigate } from "react-router-dom";
import type { DocumentSearchResult } from "../api";
import SnippetHighlight from "./SnippetHighlight";

interface Props {
  results: DocumentSearchResult[];
  query: string;
}

export default function DocumentResults({ results, query }: Props) {
  const navigate = useNavigate();

  if (results.length === 0) {
    return <p className="muted">Документы не найдены.</p>;
  }

  return (
    <div className="result-list">
      {results.map((result) => (
        <button
          className="result-card result-card--button"
          key={result.document_id}
          type="button"
          onClick={() => navigate(`/documents/${result.document_id}`)}
        >
          <div className="result-card__header">
            <h3>{result.title}</h3>
            {result.date && <span className="meta">{result.date}</span>}
          </div>
          <div className="chunk-stack">
            {result.matched_chunks.map((chunk, index) => (
              <div className="chunk-preview" key={`${chunk.page}-${index}`}>
                <span className="meta">
                  Стр. {chunk.page ?? "?"} · score {chunk.score.toFixed(3)}
                </span>
                <p className="snippet">
                  <SnippetHighlight text={chunk.snippet} query={query} />
                </p>
              </div>
            ))}
          </div>
        </button>
      ))}
    </div>
  );
}
