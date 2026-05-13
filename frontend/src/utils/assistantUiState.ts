import type {
  ActionPlan,
  AssistantChatResponse,
  AssistantInterfaceMode,
  BriefState,
  FoundItem,
  RenderedEventBrief,
  RouterDecision,
  SupplierVerificationResult,
} from "../api";
import {
  buildVisibleCandidates,
  nextVisibleCandidateItems,
} from "./assistantCandidates.ts";
import type { VisibleCandidatePayload } from "./assistantCandidates.ts";

interface OptionalModeRouter extends Omit<RouterDecision, "interface_mode"> {
  interface_mode?: AssistantInterfaceMode | null;
}

interface OptionalModeActionPlan extends Omit<ActionPlan, "interface_mode"> {
  interface_mode?: AssistantInterfaceMode | null;
}

export interface AssistantResponseForUi
  extends Omit<AssistantChatResponse, "action_plan" | "router" | "ui_mode"> {
  ui_mode?: AssistantInterfaceMode | null;
  router?: OptionalModeRouter | null;
  action_plan?: OptionalModeActionPlan | null;
}

export interface AssistantUiMessage {
  role: "assistant";
  content: string;
  foundItems?: FoundItem[];
  foundItemsEmptyState?: "pending" | "no-results";
  verificationResults?: SupplierVerificationResult[];
}

export interface AssistantUiState {
  interfaceMode: AssistantInterfaceMode;
  brief: BriefState;
  foundItems: FoundItem[];
  visibleCandidates: VisibleCandidatePayload[];
  candidateItemIds: string[];
  selectedItemIds: string[];
  verificationResults: SupplierVerificationResult[];
  renderedBrief: RenderedEventBrief | null;
  showDraftBriefPanel: boolean;
  assistantMessage: AssistantUiMessage;
}

export function assistantUiStateFromResponse(
  previousFoundItems: FoundItem[],
  response: AssistantResponseForUi,
): AssistantUiState {
  const interfaceMode = assistantInterfaceModeFromResponse(response);
  const foundItems = nextVisibleCandidateItems(previousFoundItems, response);
  const visibleCandidates = buildVisibleCandidates(foundItems);
  const isChatSearch = interfaceMode === "chat_search";
  const showInlineFoundItems =
    isChatSearch &&
    (response.found_items.length > 0 || responseRefreshesCandidates(response));
  const showInlineVerificationCards =
    isChatSearch &&
    response.verification_results.length > 0 &&
    foundItems.length > 0;
  const assistantMessageFoundItems = showInlineFoundItems
    ? response.found_items
    : showInlineVerificationCards
      ? foundItems
      : undefined;
  const showInlineVerificationResults =
    isChatSearch && responseHandlesVerification(response);

  return {
    interfaceMode,
    brief: response.brief,
    foundItems,
    visibleCandidates,
    candidateItemIds: visibleCandidates.map((candidate) => candidate.item_id),
    selectedItemIds: response.brief.selected_item_ids,
    verificationResults: response.verification_results,
    renderedBrief: response.rendered_brief,
    showDraftBriefPanel: interfaceMode === "brief_workspace",
    assistantMessage: {
      role: "assistant",
      content: response.message,
      foundItems: assistantMessageFoundItems,
      foundItemsEmptyState:
        showInlineFoundItems && response.found_items.length === 0
          ? "no-results"
          : undefined,
      verificationResults: showInlineVerificationResults
        ? response.verification_results
        : undefined,
    },
  };
}

export function assistantInterfaceModeFromResponse(
  response: Pick<AssistantResponseForUi, "action_plan" | "router" | "ui_mode">,
): AssistantInterfaceMode {
  const modeCandidates = [
    response.ui_mode,
    response.action_plan?.interface_mode,
    response.router?.interface_mode,
  ];

  return modeCandidates.find(isAssistantInterfaceMode) ?? "chat_search";
}

function isAssistantInterfaceMode(value: unknown): value is AssistantInterfaceMode {
  return value === "brief_workspace" || value === "chat_search";
}

function responseRefreshesCandidates(
  response: Pick<AssistantResponseForUi, "action_plan" | "router">,
): boolean {
  return (
    response.action_plan?.tool_intents.includes("search_items") === true ||
    response.router?.tool_intents?.includes("search_items") === true ||
    response.router?.should_search_now === true
  );
}

function responseHandlesVerification(
  response: Pick<
    AssistantResponseForUi,
    "action_plan" | "router" | "verification_results"
  >,
): boolean {
  return (
    response.verification_results.length > 0 ||
    response.action_plan?.tool_intents.includes("verify_supplier_status") ===
      true ||
    response.action_plan?.workflow_stage === "supplier_verification" ||
    response.router?.tool_intents?.includes("verify_supplier_status") === true ||
    response.router?.intent === "verification" ||
    response.router?.workflow_stage === "supplier_verification"
  );
}
