import type { WithinDocumentResult } from "../api";
import {
  formatPageRange,
  matchLabel,
} from "../utils/searchPresentation";
import SnippetHighlight from "./SnippetHighlight";

interface Props {
  results: WithinDocumentResult[];
  query: string;
}

export default function ChunkResults({ results, query }: Props) {
  if (results.length === 0) {
    return <p className="muted">Фрагменты не найдены.</p>;
  }

  return (
    <div className="result-list">
      {results.map((result) => (
        <article className="result-card" key={result.chunk_index}>
          <div className="result-card__header">
            <h3>{formatPageRange(result.page_start, result.page_end)}</h3>
            <span className="match-badge">{matchLabel(result.score)}</span>
          </div>
          <p className="meta">
            {result.section_type ?? "section_type не определён"} · chunk{" "}
            {result.chunk_index}
          </p>
          <p className="snippet">
            <SnippetHighlight text={result.snippet} query={query} />
          </p>
        </article>
      ))}
    </div>
  );
}
