export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface DocumentOut {
  id: string;
  title: string;
  status: string;
  doc_type: string | null;
  document_kind: string | null;
  contractor_entity_id: string | null;
  content_type: string;
  partial_extraction: boolean;
  error_message: string | null;
  created_at: string;
  preview_available: boolean;
}

export interface DocumentFactsOut {
  fields: Record<string, unknown>;
  summary: string | null;
  key_points: string[];
  partial_extraction: boolean;
}

export interface ContractorOut {
  id: string;
  display_name: string;
  normalized_key: string;
  inn: string | null;
  kpp: string | null;
  created_at: string;
}

export interface ContractorProfileOut {
  contractor: ContractorOut;
  document_count: number;
  raw_mapping_count: number;
}

export interface ContractorCatalogItem {
  id: string;
  display_name: string;
  normalized_key: string;
  inn: string | null;
  kpp: string | null;
  document_count: number;
}

export interface ContractorSearchResult {
  contractor_id: string;
  name: string;
  score: number;
  matched_chunks_count: number;
  top_snippet: string;
}

export interface ChunkSnippet {
  page: number | null;
  snippet: string;
  score: number;
}

export interface DocumentSearchResult {
  document_id: string;
  title: string;
  date: string | null;
  matched_chunks: ChunkSnippet[];
}

export interface WithinDocumentResult {
  chunk_index: number;
  page_start: number | null;
  page_end: number | null;
  section_type: string | null;
  snippet: string;
  score: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SourceRef {
  document_id: string;
  contractor_id: string | null;
  page_start: number | null;
  page_end: number | null;
  chunk_index: number;
  score: number;
  snippet: string;
  document_title: string | null;
  contractor_name: string | null;
}

export interface RagAnswer {
  answer: string;
  sources: SourceRef[];
}

export interface RagContractorResult {
  contractor_id: string;
  name: string;
  score: number;
  matched_chunks_count: number;
  document_count: number;
  top_snippet: string;
}

export interface GlobalRagAnswer extends RagAnswer {
  contractors: RagContractorResult[];
}

export type AssistantInterfaceMode = "brief_workspace" | "chat_search";

export type EventBriefWorkflowState =
  | "intake"
  | "clarifying"
  | "service_planning"
  | "supplier_searching"
  | "supplier_verification"
  | "brief_ready"
  | "brief_rendered"
  | "search_clarifying"
  | "searching"
  | "search_results_shown";

export type ServiceNeedPriority = "required" | "must_have" | "nice_to_have";
export type ServiceNeedSource = "explicit" | "policy_inferred";

export interface ServiceNeed {
  category: string;
  priority: ServiceNeedPriority;
  source: ServiceNeedSource;
  reason: string | null;
  notes: string | null;
}

export interface BriefState {
  event_type: string | null;
  event_goal: string | null;
  concept: string | null;
  format: string | null;
  city: string | null;
  date_or_period: string | null;
  audience_size: number | null;
  venue: string | null;
  venue_status: string | null;
  venue_constraints: string[];
  duration_or_time_window: string | null;
  event_level: string | null;
  budget: string | number | null;
  budget_total: number | null;
  budget_per_guest: number | null;
  budget_notes: string | null;
  catering_format: string | null;
  technical_requirements: string[];
  service_needs: ServiceNeed[];
  required_services: string[];
  must_have_services: string[];
  nice_to_have_services: string[];
  selected_item_ids: string[];
  constraints: string[];
  preferences: string[];
  open_questions: string[];
}

export const emptyBriefState: BriefState = {
  event_type: null,
  event_goal: null,
  concept: null,
  format: null,
  city: null,
  date_or_period: null,
  audience_size: null,
  venue: null,
  venue_status: null,
  venue_constraints: [],
  duration_or_time_window: null,
  event_level: null,
  budget: null,
  budget_total: null,
  budget_per_guest: null,
  budget_notes: null,
  catering_format: null,
  technical_requirements: [],
  service_needs: [],
  required_services: [],
  must_have_services: [],
  nice_to_have_services: [],
  selected_item_ids: [],
  constraints: [],
  preferences: [],
  open_questions: [],
};

export type RouterIntent =
  | "brief_discovery"
  | "supplier_search"
  | "mixed"
  | "clarification"
  | "selection"
  | "comparison"
  | "verification"
  | "render_brief";

export type ToolIntent =
  | "update_brief"
  | "search_items"
  | "get_item_details"
  | "select_item"
  | "compare_items"
  | "verify_supplier_status"
  | "render_event_brief";

export interface CatalogSearchFiltersOut {
  supplier_city_normalized: string | null;
  category: string | null;
  supplier_status_normalized: string | null;
  has_vat: string | null;
  vat_mode: string | null;
  unit_price_min: number | null;
  unit_price_max: number | null;
}

export interface SearchRequest {
  query: string;
  service_category: string | null;
  filters: CatalogSearchFiltersOut;
  priority: number;
  limit: number;
}

export interface RouterDecision {
  intent: RouterIntent;
  confidence: number;
  known_facts: Record<string, unknown>;
  missing_fields: string[];
  should_search_now: boolean;
  search_query: string | null;
  brief_update: BriefState;
  interface_mode: AssistantInterfaceMode;
  workflow_stage: EventBriefWorkflowState;
  reason_codes: string[];
  search_requests: SearchRequest[];
  tool_intents: ToolIntent[];
  clarification_questions: string[];
  user_visible_summary: string | null;
}

export type MatchReasonCode =
  | "semantic"
  | "keyword_name"
  | "keyword_supplier"
  | "keyword_inn"
  | "keyword_source_text"
  | "keyword_external_id";

export interface MatchReason {
  code: MatchReasonCode;
  label: string;
}

export interface FoundItem {
  id: string;
  score: number;
  name: string;
  category: string | null;
  unit: string;
  unit_price: string;
  supplier: string | null;
  supplier_city: string | null;
  source_text_snippet: string | null;
  source_text_full_available: boolean;
  match_reason: MatchReason;
  result_group: string | null;
  matched_service_category: string | null;
  matched_service_categories: string[];
}

export interface VisibleCandidate {
  ordinal: number;
  item_id: string;
  service_category?: string | null;
}

export interface ActionPlan {
  interface_mode: AssistantInterfaceMode;
  workflow_stage: EventBriefWorkflowState;
  tool_intents: ToolIntent[];
  search_requests: SearchRequest[];
  verification_targets: string[];
  item_detail_ids: string[];
  render_requested: boolean;
  missing_fields: string[];
  clarification_questions: string[];
  skipped_actions: string[];
}

export type SupplierVerificationStatus =
  | "active"
  | "inactive"
  | "not_found"
  | "not_verified"
  | "error";

export interface SupplierVerificationResult {
  item_id: string | null;
  supplier_name: string | null;
  supplier_inn: string | null;
  ogrn: string | null;
  legal_name: string | null;
  status: SupplierVerificationStatus;
  source: string;
  checked_at: string | null;
  risk_flags: string[];
  message: string | null;
}

export interface RenderedBriefSection {
  title: string;
  items: string[];
}

export interface RenderedEventBrief {
  title: string;
  sections: RenderedBriefSection[];
  open_questions: string[];
  evidence: Record<string, string[]>;
}

export interface AssistantChatRequest {
  session_id: string | null;
  message: string;
  brief?: BriefState | null;
  recent_turns?: ChatMessage[];
  visible_candidates?: VisibleCandidate[];
  candidate_item_ids?: string[];
}

export interface AssistantChatResponse {
  session_id: string;
  message: string;
  ui_mode: AssistantInterfaceMode;
  router: RouterDecision;
  action_plan: ActionPlan | null;
  brief: BriefState;
  found_items: FoundItem[];
  verification_results: SupplierVerificationResult[];
  rendered_brief: RenderedEventBrief | null;
}

export interface CatalogSearchFilters {
  supplier_city?: string | null;
  category?: string | null;
  supplier_status?: string | null;
  has_vat?: string | null;
  unit_price?: string | number | null;
}

export interface CatalogSearchRequest {
  query: string;
  limit?: number;
  filters?: CatalogSearchFilters | null;
}

export interface CatalogSearchResult {
  items: FoundItem[];
}

export interface PriceItemOut {
  id: string;
  name: string;
  category: string | null;
  unit: string;
  unit_price: string;
  supplier: string | null;
  supplier_inn: string | null;
  supplier_city: string | null;
  has_vat: string | null;
  supplier_status: string | null;
  catalog_index_status: string;
  import_batch_id: string;
  source_file_id: string;
}

export interface PriceItemListOut {
  items: PriceItemOut[];
  total: number;
}

export interface PriceItemDetailItemOut extends PriceItemOut {
  external_id: string | null;
  source_text: string | null;
  section: string | null;
  supplier_phone: string | null;
  supplier_email: string | null;
  embedding_text: string;
  embedding_template_version: string;
  embedding_model: string;
}

export interface PriceItemSourceOut {
  source_kind: string;
  import_batch_id: string;
  source_file_id: string;
  price_import_row_id: string | null;
  row_number: number | null;
  source_text: string | null;
}

export interface PriceItemDetailOut {
  item: PriceItemDetailItemOut;
  sources: PriceItemSourceOut[];
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const getDocument = (id: string) =>
  apiFetch<DocumentOut>(`/documents/${id}`);

export const getDocumentFacts = (id: string) =>
  apiFetch<DocumentFactsOut>(`/documents/${id}/facts`);

export const listDocuments = () =>
  apiFetch<DocumentOut[]>("/documents/?limit=20");

export const getContractor = (id: string) =>
  apiFetch<ContractorProfileOut>(`/contractors/${id}`);

export const listContractors = (q = "") =>
  apiFetch<ContractorCatalogItem[]>(
    `/contractors/?limit=50${q ? `&q=${encodeURIComponent(q)}` : ""}`
  );

export const listContractorDocuments = (id: string) =>
  apiFetch<DocumentOut[]>(`/contractors/${id}/documents?limit=20`);

export const searchContractors = (q: string) =>
  apiFetch<ContractorSearchResult[]>(
    `/search?q=${encodeURIComponent(q)}&limit=20`
  );

export const searchDocumentsForContractor = (id: string, q: string) =>
  apiFetch<DocumentSearchResult[]>(
    `/contractors/${id}/search?q=${encodeURIComponent(q)}&limit=20`
  );

export const searchWithinDocument = (id: string, q: string) =>
  apiFetch<WithinDocumentResult[]>(
    `/documents/${id}/search?q=${encodeURIComponent(q)}&limit=20`
  );

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const answerGlobalSearch = (
  message: string,
  history: ChatMessage[] = [],
) =>
  postJson<GlobalRagAnswer>("/search/answer", {
    message,
    history,
  });

export const answerContractor = (
  id: string,
  message: string,
  history: ChatMessage[] = [],
) =>
  postJson<RagAnswer>(`/contractors/${id}/answer`, {
    message,
    history,
  });

export const answerDocument = (
  id: string,
  message: string,
  history: ChatMessage[] = [],
) =>
  postJson<RagAnswer>(`/documents/${id}/answer`, {
    message,
    history,
  });

export const assistantChat = (body: AssistantChatRequest) =>
  postJson<AssistantChatResponse>("/assistant/chat", body);

export const listCatalogItems = (limit = 50, offset = 0) =>
  apiFetch<PriceItemListOut>(
    `/catalog/items?limit=${limit}&offset=${offset}`,
  );

export const getCatalogItem = (id: string) =>
  apiFetch<PriceItemDetailOut>(`/catalog/items/${id}`);

export const searchCatalogItems = (body: CatalogSearchRequest) =>
  postJson<CatalogSearchResult>("/catalog/search", body);

export async function patchDocumentFacts(
  id: string,
  body: {
    fields: Record<string, string | null>;
    summary: string | null;
    key_points: string[];
  }
): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${id}/facts`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}
