import type {
  FoundItem,
  SupplierVerificationResult,
  SupplierVerificationStatus,
} from "../api";

export interface RelatedVerificationItem {
  item: FoundItem;
  ordinal: number;
}

export interface VerificationDisplayGroup {
  key: string;
  result: SupplierVerificationResult;
  itemIds: string[];
  relatedItems: RelatedVerificationItem[];
  riskFlags: string[];
}

const statusLabels: Record<SupplierVerificationStatus, string> = {
  active: "Юрлицо действует в реестре",
  inactive: "Юрлицо не действует в реестре",
  not_found: "Не найдено в проверочном источнике",
  not_verified: "Нужна ручная проверка",
  error: "Ошибка проверки",
};

export function verificationStatusLabel(
  status: SupplierVerificationStatus,
): string {
  return statusLabels[status];
}

export function verificationResultsByItemId(
  results: SupplierVerificationResult[],
): Map<string, SupplierVerificationResult> {
  const resultByItemId = new Map<string, SupplierVerificationResult>();
  for (const result of results) {
    if (result.item_id === null) continue;
    resultByItemId.set(result.item_id, result);
  }
  return resultByItemId;
}

export function groupVerificationResults(
  results: SupplierVerificationResult[],
  relatedItems: FoundItem[] = [],
): VerificationDisplayGroup[] {
  const itemById = new Map(relatedItems.map((item) => [item.id, item]));
  const ordinalById = new Map(
    relatedItems.map((item, index) => [item.id, index + 1]),
  );
  const groups = new Map<string, VerificationDisplayGroup>();

  results.forEach((result, index) => {
    const key = verificationGroupKey(result, index);
    const current = groups.get(key);
    const itemIds = result.item_id === null ? [] : [result.item_id];

    if (current === undefined) {
      groups.set(key, {
        key,
        result,
        itemIds,
        relatedItems: relatedItemsForIds(itemIds, itemById, ordinalById),
        riskFlags: [...result.risk_flags],
      });
      return;
    }

    const nextItemIds = uniqueStrings([...current.itemIds, ...itemIds]);
    groups.set(key, {
      ...current,
      itemIds: nextItemIds,
      relatedItems: relatedItemsForIds(nextItemIds, itemById, ordinalById),
      riskFlags: uniqueStrings([...current.riskFlags, ...result.risk_flags]),
    });
  });

  return [...groups.values()];
}

export function formatVerificationCheckedAt(value: string | null): string | null {
  if (value === null) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function formatSupplierCount(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} поставщик`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `${count} поставщика`;
  }
  return `${count} поставщиков`;
}

function verificationGroupKey(
  result: SupplierVerificationResult,
  index: number,
): string {
  const inn = normalizedInn(result.supplier_inn);
  if (inn !== null) return `inn:${inn}`;
  if (result.item_id !== null) return `item:${result.item_id}`;
  return `result:${index}`;
}

function normalizedInn(value: string | null): string | null {
  if (value === null) return null;
  const normalized = value.replace(/\D/g, "");
  return normalized === "" ? null : normalized;
}

function relatedItemsForIds(
  itemIds: string[],
  itemById: Map<string, FoundItem>,
  ordinalById: Map<string, number>,
): RelatedVerificationItem[] {
  return itemIds
    .map((itemId) => {
      const item = itemById.get(itemId);
      const ordinal = ordinalById.get(itemId);
      if (item === undefined || ordinal === undefined) return null;
      return { item, ordinal };
    })
    .filter((item): item is RelatedVerificationItem => item !== null)
    .sort((left, right) => left.ordinal - right.ordinal);
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values)];
}
