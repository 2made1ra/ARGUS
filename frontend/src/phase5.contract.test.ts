import {
  assistantChat,
  emptyBriefState,
  getCatalogItem,
  listCatalogItems,
  searchCatalogItems,
} from "./api";
import type {
  ActionPlan,
  AssistantChatResponse,
  BriefState,
  FoundItem,
  PriceItemDetailOut,
  PriceItemListOut,
  RenderedEventBrief,
  RouterDecision,
  SupplierVerificationResult,
} from "./api";
import AssistantChat from "./components/AssistantChat";
import BriefDraftPanel from "./components/BriefDraftPanel";
import FoundItemsPanel from "./components/FoundItemsPanel";
import AssistantPage from "./pages/AssistantPage";
import CatalogItemPage from "./pages/CatalogItemPage";

const brief: BriefState = {
  ...emptyBriefState,
  event_type: "музыкальный вечер",
  event_goal: "презентация продукта",
  concept: "городская сцена",
  format: "офлайн",
  audience_size: 100,
  venue_constraints: ["площадка без подвеса"],
  budget_total: 2_000_000,
  budget_per_guest: 2500,
  budget_notes: "ориентир предварительный",
  catering_format: "фуршет",
  technical_requirements: ["монтаж ночью"],
  service_needs: [
    {
      category: "свет",
      priority: "nice_to_have",
      source: "policy_inferred",
      reason: "площадка без подвеса",
      notes: "искать напольные приборы",
    },
  ],
  must_have_services: ["звук"],
  nice_to_have_services: ["свет"],
  selected_item_ids: ["00000000-0000-0000-0000-000000000000"],
  open_questions: ["date_or_period"],
};

const routerDecision: RouterDecision = {
  intent: "mixed",
  confidence: 0.9,
  known_facts: { event_type: "музыкальный вечер" },
  missing_fields: ["city"],
  should_search_now: true,
  search_query: "музыкальное оборудование",
  brief_update: brief,
  interface_mode: "brief_workspace",
  workflow_stage: "supplier_searching",
  reason_codes: ["event_creation_intent_detected"],
  search_requests: [
    {
      query: "свет Екатеринбург",
      service_category: "свет",
      filters: {
        supplier_city_normalized: "екатеринбург",
        category: null,
        supplier_status_normalized: null,
        has_vat: null,
        vat_mode: null,
        unit_price_min: null,
        unit_price_max: null,
      },
      priority: 1,
      limit: 8,
    },
  ],
  tool_intents: ["update_brief", "search_items"],
  clarification_questions: ["На какую дату планируется мероприятие?"],
  user_visible_summary: null,
};

const actionPlan: ActionPlan = {
  interface_mode: "brief_workspace",
  workflow_stage: "supplier_searching",
  tool_intents: ["update_brief", "search_items"],
  search_requests: routerDecision.search_requests,
  verification_targets: ["00000000-0000-0000-0000-000000000000"],
  comparison_targets: [],
  item_detail_ids: [],
  render_requested: false,
  missing_fields: ["date_or_period"],
  clarification_questions: ["На какую дату планируется мероприятие?"],
  skipped_actions: [],
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
  result_group: "свет",
  matched_service_category: "свет",
  matched_service_categories: ["свет"],
};

const verification: SupplierVerificationResult = {
  item_id: foundItem.id,
  supplier_name: "ООО Пример",
  supplier_inn: "7700000000",
  ogrn: null,
  legal_name: null,
  status: "not_verified",
  source: "manual_not_verified",
  checked_at: null,
  risk_flags: ["verification_adapter_not_configured"],
  message: "Автоматическая проверка не настроена",
};

const renderedBrief: RenderedEventBrief = {
  title: "Бриф мероприятия",
  sections: [{ title: "Основная информация", items: ["Тип: музыкальный вечер"] }],
  open_questions: ["Дата мероприятия"],
  evidence: {
    selected_item_ids: [foundItem.id],
    verification_result_ids: [foundItem.id],
  },
};

const chatSearchResponse: AssistantChatResponse = {
  session_id: "00000000-0000-0000-0000-000000000000",
  message: "Нашёл варианты в каталоге.",
  ui_mode: "chat_search",
  router: { ...routerDecision, interface_mode: "chat_search" },
  action_plan: { ...actionPlan, interface_mode: "chat_search" },
  brief,
  found_items: [foundItem],
  item_details: [],
  verification_results: [verification],
  rendered_brief: renderedBrief,
};

async function phase5ApiContract(): Promise<void> {
  const chatResponse: AssistantChatResponse = await assistantChat({
    session_id: null,
    message: "Нужно музыкальное оборудование",
    brief,
    recent_turns: [{ role: "assistant", content: "Позиции ниже." }],
    visible_candidates: [
      {
        ordinal: 1,
        item_id: foundItem.id,
        service_category: "свет",
      },
    ],
    candidate_item_ids: [foundItem.id],
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
void actionPlan;
void foundItem;
void verification;
void renderedBrief;
void chatSearchResponse;
void phase5ApiContract;
void phase5Components;
