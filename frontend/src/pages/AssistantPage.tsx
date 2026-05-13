import { useState } from "react";
import type {
  AssistantInterfaceMode,
  FoundItem,
  RouterDecision,
  SupplierVerificationResult,
  RenderedEventBrief,
} from "../api";
import { assistantChat, emptyBriefState } from "../api";
import AssistantChat from "../components/AssistantChat";
import type { AssistantTimelineMessage } from "../components/AssistantChat";
import BriefDraftPanel from "../components/BriefDraftPanel";
import FoundItemsPanel from "../components/FoundItemsPanel";
import RenderedBriefPanel from "../components/RenderedBriefPanel";
import VerificationResultsPanel from "../components/VerificationResultsPanel";
import { buildAssistantChatRequest } from "../utils/assistantRequest";
import { appendAssistantTimelineMessage } from "../utils/assistantTimeline";
import { assistantUiStateFromResponse } from "../utils/assistantUiState";

export default function AssistantPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [brief, setBrief] = useState(emptyBriefState);
  const [messages, setMessages] = useState<AssistantTimelineMessage[]>([]);
  const [foundItems, setFoundItems] = useState<FoundItem[]>([]);
  const [verificationResults, setVerificationResults] = useState<
    SupplierVerificationResult[]
  >([]);
  const [renderedBrief, setRenderedBrief] = useState<RenderedEventBrief | null>(
    null,
  );
  const [router, setRouter] = useState<RouterDecision | null>(null);
  const [interfaceMode, setInterfaceMode] =
    useState<AssistantInterfaceMode>("chat_search");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedItemIds = brief.selected_item_ids;

  async function handleSend(message: string): Promise<void> {
    setLoading(true);
    setError(null);
    setInput("");
    setMessages((current) => [...current, { role: "user", content: message }]);

    try {
      const response = await assistantChat(buildAssistantChatRequest({
        sessionId,
        message,
        brief,
        messages,
        visibleFoundItems: foundItems,
      }));
      const nextUiState = assistantUiStateFromResponse(foundItems, response);
      setSessionId(response.session_id);
      setBrief(nextUiState.brief);
      setFoundItems(nextUiState.foundItems);
      setVerificationResults(nextUiState.verificationResults);
      setRenderedBrief(nextUiState.renderedBrief);
      setRouter(response.router);
      setInterfaceMode(nextUiState.interfaceMode);
      setMessages((current) =>
        appendAssistantTimelineMessage(current, nextUiState.assistantMessage),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleSelectedItemIdsChange(nextSelectedItemIds: string[]): void {
    setBrief((current) => ({
      ...current,
      selected_item_ids: nextSelectedItemIds,
    }));
  }

  return (
    <main className="workspace assistant-workspace">
      <header className="workspace-header assistant-header">
        <div>
          <p className="eyebrow">ARGUS MVP</p>
          <h1>Ассистент мероприятия</h1>
        </div>
        <p className="workspace-header__note">
          Один рабочий экран: диалог, черновик брифа и проверяемые позиции из
          каталога.
        </p>
      </header>

      <section
        className={`assistant-layout ${
          interfaceMode === "chat_search" ? "assistant-layout--chat-search" : ""
        }`}
      >
        <AssistantChat
          messages={messages}
          input={input}
          loading={loading}
          error={error}
          latestRouter={router}
          selectedItemIds={selectedItemIds}
          onInputChange={setInput}
          onSend={handleSend}
          onSelectedItemIdsChange={handleSelectedItemIdsChange}
        />
        {interfaceMode === "brief_workspace" && (
          <aside className="assistant-side">
            <BriefDraftPanel brief={brief} />
            <FoundItemsPanel
              items={foundItems}
              loading={loading}
              selectedItemIds={selectedItemIds}
              onSelectedItemIdsChange={handleSelectedItemIdsChange}
            />
            {verificationResults.length > 0 && (
              <VerificationResultsPanel results={verificationResults} />
            )}
            {renderedBrief && <RenderedBriefPanel brief={renderedBrief} />}
          </aside>
        )}
      </section>
    </main>
  );
}
