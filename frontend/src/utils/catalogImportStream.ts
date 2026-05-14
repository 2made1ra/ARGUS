export function isCurrentCatalogImportStream(input: {
  currentStream: unknown | null;
  expectedStream: unknown;
  activeJobId: string | null;
  expectedJobId: string;
}): boolean {
  return (
    input.currentStream === input.expectedStream &&
    input.activeJobId === input.expectedJobId
  );
}
