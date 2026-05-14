export interface AssistantCandidateItem {
  id: string;
  result_group: string | null;
  matched_service_category: string | null;
  matched_service_categories: string[];
}

export interface FoundItemDisplayGroup<T extends AssistantCandidateItem> {
  title: string;
  items: T[];
}

export interface VisibleCandidatePayload {
  ordinal: number;
  item_id: string;
  service_category: string | null;
}

export interface CandidateRefreshResponse<T extends AssistantCandidateItem> {
  found_items: T[];
  action_plan?: { tool_intents: string[] } | null;
  router?: {
    should_search_now?: boolean;
    tool_intents?: string[];
  } | null;
}

export function groupFoundItemsForDisplay<T extends AssistantCandidateItem>(
  items: T[],
): Array<FoundItemDisplayGroup<T>> {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const title = foundItemGroupTitle(item);
    const groupItems = groups.get(title) ?? [];
    groupItems.push(item);
    groups.set(title, groupItems);
  }
  return [...groups.entries()].map(([title, groupItems]) => ({
    title,
    items: groupItems,
  }));
}

export function orderFoundItemsForDisplay<T extends AssistantCandidateItem>(
  items: T[],
): T[] {
  return groupFoundItemsForDisplay(items).flatMap((group) => group.items);
}

export function buildVisibleCandidates(
  items: AssistantCandidateItem[],
): VisibleCandidatePayload[] {
  return orderFoundItemsForDisplay(items).map((item, index) => ({
    ordinal: index + 1,
    item_id: item.id,
    service_category: candidateServiceCategory(item),
  }));
}

export function nextVisibleCandidateItems<T extends AssistantCandidateItem>(
  previousItems: T[],
  response: CandidateRefreshResponse<T>,
): T[] {
  if (response.found_items.length > 0) {
    return orderFoundItemsForDisplay(response.found_items);
  }
  if (responseRefreshesCandidates(response)) {
    return [];
  }
  return [...previousItems];
}

function foundItemGroupTitle(item: AssistantCandidateItem): string {
  return candidateServiceCategory(item) ?? "Каталог";
}

function candidateServiceCategory(item: AssistantCandidateItem): string | null {
  return (
    item.result_group ??
    item.matched_service_category ??
    item.matched_service_categories[0] ??
    null
  );
}

function responseRefreshesCandidates<T extends AssistantCandidateItem>(
  response: CandidateRefreshResponse<T>,
): boolean {
  return (
    response.action_plan?.tool_intents.includes("search_items") === true ||
    response.router?.tool_intents?.includes("search_items") === true ||
    response.router?.should_search_now === true
  );
}
