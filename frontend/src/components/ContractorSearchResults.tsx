import { useNavigate } from "react-router-dom";
import type { ContractorSearchResult } from "../api";
import { matchLabel } from "../utils/searchPresentation";
import SnippetHighlight from "./SnippetHighlight";

interface Props {
  results: ContractorSearchResult[];
  query: string;
}

export default function ContractorSearchResults({ results, query }: Props) {
  const navigate = useNavigate();

  if (results.length === 0) {
    return <p className="muted">База данных пуста — загрузите документы, чтобы начать поиск.</p>;
  }

  return (
    <div className="result-list">
      {results.map((result) => (
        <button
          className="result-card result-card--button"
          key={result.contractor_id}
          type="button"
          onClick={() => navigate(`/contractors/${result.contractor_id}`)}
        >
          <div className="result-card__header">
            <h3 className="compact-title">{result.name}</h3>
            <span className="match-badge">{matchLabel(result.score)}</span>
          </div>
          <p className="snippet">
            <SnippetHighlight text={result.top_snippet} query={query} />
          </p>
          <p className="meta">
            Совпадений в чанках: {result.matched_chunks_count}
          </p>
        </button>
      ))}
    </div>
  );
}
