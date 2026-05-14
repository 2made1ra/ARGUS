export function catalogPageOffset(page: number, pageSize: number): number {
  const safePage = Math.max(1, Math.floor(page));
  const safePageSize = Math.max(1, Math.floor(pageSize));
  return (safePage - 1) * safePageSize;
}

export function catalogPageCount(total: number, pageSize: number): number {
  const safeTotal = Math.max(0, Math.floor(total));
  const safePageSize = Math.max(1, Math.floor(pageSize));
  return Math.max(1, Math.ceil(safeTotal / safePageSize));
}

export function catalogPageRangeLabel(input: {
  page: number;
  pageSize: number;
  total: number;
  loaded: number;
}): string {
  if (input.total <= 0 || input.loaded <= 0) return "0 из 0";

  const start = catalogPageOffset(input.page, input.pageSize) + 1;
  const end = Math.min(input.total, start + Math.max(0, input.loaded) - 1);
  return `${start}-${end} из ${input.total}`;
}
