import { Link } from "react-router-dom";
import type { SourceRef } from "../api";
import {
  compactDocumentTitle,
  formatPageRange,
} from "../utils/searchPresentation";

interface Props {
  sources: SourceRef[];
}

export default function SourceList({ sources }: Props) {
  if (sources.length === 0) return null;

  return (
    <div className="source-list">
      {sources.map((source, index) => (
        <Link
          className="source-chip"
          key={`${source.document_id}-${source.chunk_index}-${index}`}
          to={`/documents/${source.document_id}`}
        >
          <span className="source-chip__index">S{index + 1}</span>
          <span className="source-chip__body">
            {source.contractor_name ?? "Контрагент не указан"} ·{" "}
            {compactDocumentTitle(source.document_title)} ·{" "}
            {formatPageRange(source.page_start, source.page_end)}
          </span>
        </Link>
      ))}
    </div>
  );
}
