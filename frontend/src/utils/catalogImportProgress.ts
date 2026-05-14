export type CatalogImportStatus =
  | "QUEUED"
  | "IMPORTING"
  | "INDEXING"
  | "COMPLETED"
  | "FAILED";

export type CatalogImportStage =
  | "upload"
  | "import"
  | "indexing"
  | "completed"
  | "failed";

export interface CatalogImportStageSegment {
  key: Exclude<CatalogImportStage, "completed" | "failed">;
  label: string;
  from: number;
  to: number;
}

export const catalogImportStageSegments: CatalogImportStageSegment[] = [
  { key: "upload", label: "Загрузка файла", from: 0, to: 10 },
  { key: "import", label: "Импорт CSV", from: 10, to: 35 },
  { key: "indexing", label: "Индексация", from: 35, to: 100 },
];

export function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, Math.round(value)));
}

export function progressPercentFromUpload(uploadPercent: number): number {
  return clampPercent(uploadPercent) / 10;
}

export function catalogImportUploadDisplayPercent(input: {
  uploadPercent: number;
  isStartingUpload: boolean;
  elapsedMs: number;
}): number {
  const measuredProgress = progressPercentFromUpload(input.uploadPercent);
  if (!input.isStartingUpload || measuredProgress > 0) {
    return measuredProgress;
  }

  const elapsedSeconds = Math.ceil(Math.max(0, input.elapsedMs) / 1000);
  return Math.min(9, elapsedSeconds);
}

export function timestampToMs(value: string | null): number | null {
  if (value === null || value.trim() === "") return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function catalogImportStatusIsActive(
  status: CatalogImportStatus,
): boolean {
  return status === "QUEUED" || status === "IMPORTING" || status === "INDEXING";
}

export function catalogImportStageLabel(stage: CatalogImportStage): string {
  if (stage === "completed") return "Готово";
  if (stage === "failed") return "Ошибка";
  return (
    catalogImportStageSegments.find((segment) => segment.key === stage)?.label ??
    "Подготовка"
  );
}

export function catalogImportStageFromProgress(
  progressPercent: number,
): CatalogImportStage {
  const progress = clampPercent(progressPercent);
  if (progress >= 35) return "indexing";
  if (progress >= 10) return "import";
  return "upload";
}

export function formatCatalogImportEta(input: {
  progressPercent: number;
  status: CatalogImportStatus;
  startedAtMs: number | null;
  nowMs?: number;
}): string {
  if (input.status === "COMPLETED") return "готово";
  if (input.status === "FAILED") return "остановлено";
  if (input.status === "QUEUED") return "ожидает worker";

  const progress = clampPercent(input.progressPercent);
  if (progress <= 0 || input.startedAtMs === null) return "считаю время";

  const nowMs = input.nowMs ?? Date.now();
  const elapsedMs = Math.max(0, nowMs - input.startedAtMs);
  if (elapsedMs < 5_000) return "считаю время";

  const remainingRatio = (100 - progress) / progress;
  const remainingMs = elapsedMs * remainingRatio;
  if (!Number.isFinite(remainingMs)) return "считаю время";
  if (remainingMs < 60_000) return "меньше минуты";

  const minutes = Math.max(1, Math.round(remainingMs / 60_000));
  return `примерно ${minutes} мин`;
}
