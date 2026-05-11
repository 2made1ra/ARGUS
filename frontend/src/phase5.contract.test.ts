import {
  assistantChat,
  emptyBriefState,
  getCatalogItem,
  listCatalogItems,
  searchCatalogItems,
} from "./api";
import type {
  AssistantChatResponse,
  BriefState,
  FoundItem,
  PriceItemDetailOut,
  PriceItemListOut,
  RouterDecision,
} from "./api";
import AssistantChat from "./components/AssistantChat";
import BriefDraftPanel from "./components/BriefDraftPanel";
import FoundItemsPanel from "./components/FoundItemsPanel";
import AssistantPage from "./pages/AssistantPage";
import CatalogItemPage from "./pages/CatalogItemPage";

const brief: BriefState = {
  ...emptyBriefState,
  event_type: "музыкальный вечер",
  audience_size: 100,
};

const routerDecision: RouterDecision = {
  intent: "mixed",
  confidence: 0.9,
  known_facts: { event_type: "музыкальный вечер" },
  missing_fields: ["city"],
  should_search_now: true,
  search_query: "музыкальное оборудование",
  brief_update: brief,
};

const foundItem: FoundItem = {
  id: "00000000-0000-0000-0000-000000000000",
  score: 0.7,
  name: "Аренда акустической системы",
  category: "Оборудование",
  unit: "день",
  unit_price: "15000.00",
  supplier: "ООО Пример",
  supplier_city: "г. Москва",
  source_text_snippet: "Аренда акустической системы",
  source_text_full_available: true,
  match_reason: {
    code: "semantic",
    label: "Семантическое совпадение",
  },
};

async function phase5ApiContract(): Promise<void> {
  const chatResponse: AssistantChatResponse = await assistantChat({
    session_id: null,
    message: "Нужно музыкальное оборудование",
    brief,
  });
  const listResponse: PriceItemListOut = await listCatalogItems();
  const detailResponse: PriceItemDetailOut = await getCatalogItem(foundItem.id);
  const searchResponse = await searchCatalogItems({
    query: "акустическая система",
    limit: 10,
    filters: { supplier_city: "г. Москва" },
  });

  void chatResponse;
  void listResponse;
  void detailResponse;
  void searchResponse;
}

const phase5Components = [
  AssistantChat,
  BriefDraftPanel,
  FoundItemsPanel,
  AssistantPage,
  CatalogItemPage,
] as const;

void routerDecision;
void foundItem;
void phase5ApiContract;
void phase5Components;
