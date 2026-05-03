import { Link } from "react-router-dom";
import type { SourceRef } from "../api";
import {
  compactDocumentTitle,
  formatPageRange,
  type IndexedSourceRef,
  sourceAnchorId,
  sourceDocumentTarget,
} from "../utils/searchPresentation";

interface Props {
  sources: SourceRef[] | IndexedSourceRef[];
  anchorPrefix?: string;
}

export default function SourceList({ sources, anchorPrefix = "source" }: Props) {
  if (sources.length === 0) return null;

  const sourceItems = sources.map((source, index) =>
    isIndexedSourceRef(source) ? source : { source, index },
  );

  return (
    <div className="source-list">
      {sourceItems.map(({ source, index }) => (
        <Link
          className="source-chip"
          id={sourceAnchorId(anchorPrefix, index)}
          key={`${source.document_id}-${source.chunk_index}-${index}`}
          to={sourceDocumentTarget(source)}
        >
          <span className="source-chip__index">S{index + 1}</span>
          <span className="source-chip__body">
            <span className="source-chip__title">
              {source.contractor_name ?? "Контрагент не указан"}
            </span>
            <span className="source-chip__meta">
              {compactDocumentTitle(source.document_title)} ·{" "}
              {formatPageRange(source.page_start, source.page_end)}
            </span>
            <span className="source-chip__snippet">{source.snippet}</span>
          </span>
        </Link>
      ))}
    </div>
  );
}

function isIndexedSourceRef(
  source: SourceRef | IndexedSourceRef,
): source is IndexedSourceRef {
  return "source" in source;
}
