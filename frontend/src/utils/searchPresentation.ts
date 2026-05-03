import type { SourceRef } from "../api";

export function matchLabel(similarity: number): string {
  if (similarity >= 0.75) return "Высокое совпадение";
  if (similarity >= 0.55) return "Среднее совпадение";
  return "Низкое совпадение";
}

export function formatSinglePage(page: number | null): string {
  if (page === null) return "страница не распознана";
  return `стр. ${page}`;
}

export function formatPageRange(
  pageStart: number | null,
  pageEnd: number | null,
): string {
  if (pageStart === null) return "страница не распознана";
  if (pageEnd === null || pageStart === pageEnd) return `стр. ${pageStart}`;
  return `стр. ${pageStart}-${pageEnd}`;
}

export function compactDocumentTitle(
  title: string | null,
  maxLength = 72,
): string {
  const fallbackTitle = title?.trim() || "Документ";
  if (fallbackTitle.length <= maxLength) return fallbackTitle;

  const extensionMatch = fallbackTitle.match(/(\.[a-z0-9]{2,8})$/i);
  const extension = extensionMatch?.[1] ?? "";
  const titleWithoutExtension = extension
    ? fallbackTitle.slice(0, -extension.length)
    : fallbackTitle;
  const marker = "...";
  const availableLength = Math.max(maxLength - extension.length - marker.length, 12);
  const headLength = Math.ceil(availableLength * 0.62);
  const tailLength = Math.max(availableLength - headLength, 4);

  return `${titleWithoutExtension.slice(0, headLength)}${marker}${titleWithoutExtension.slice(
    -tailLength,
  )}${extension}`;
}

export function sourceAnchorId(prefix: string, index: number): string {
  return `${prefix}-${index + 1}`;
}

export function sourceDocumentTarget(source: SourceRef): string {
  const basePath = `/documents/${source.document_id}`;
  if (source.page_start === null) return basePath;
  return `${basePath}#page=${source.page_start}`;
}
