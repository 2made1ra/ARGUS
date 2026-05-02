import { Link } from "react-router-dom";
import type { SourceRef } from "../api";

interface Props {
  sources: SourceRef[];
}

function pageLabel(source: SourceRef): string {
  if (source.page_start === null && source.page_end === null) return "стр. ?";
  if (source.page_start === source.page_end || source.page_end === null) {
    return `стр. ${source.page_start ?? "?"}`;
  }
  if (source.page_start === null) return `стр. ?-${source.page_end}`;
  return `стр. ${source.page_start}-${source.page_end}`;
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
          <span>
            {source.contractor_name ?? "Контрагент не указан"} ·{" "}
            {source.document_title ?? "Документ"} · {pageLabel(source)}
          </span>
        </Link>
      ))}
    </div>
  );
}
