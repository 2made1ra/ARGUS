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
import {
  buildVisibleCandidates,
  nextVisibleCandidateItems,
} from "../utils/assistantCandidates";

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
  const [uiMode, setUiMode] = useState<AssistantInterfaceMode>("chat_search");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(message: string): Promise<void> {
    setLoading(true);
    setError(null);
    setInput("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    const visibleCandidates = buildVisibleCandidates(foundItems);

    try {
      const response = await assistantChat({
        session_id: sessionId,
        message,
        brief,
        recent_turns: messages
          .slice(-6)
          .map(({ role, content }) => ({ role, content })),
        visible_candidates: visibleCandidates,
        candidate_item_ids: visibleCandidates.map((candidate) => candidate.item_id),
      });
      const nextFoundItems = nextVisibleCandidateItems(foundItems, response);
      setSessionId(response.session_id);
      setBrief(response.brief);
      setFoundItems(nextFoundItems);
      setVerificationResults(response.verification_results);
      setRenderedBrief(response.rendered_brief);
      setRouter(response.router);
      setUiMode(response.ui_mode);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.message,
          foundItems:
            response.ui_mode === "chat_search" ? response.found_items : undefined,
          verificationResults:
            response.ui_mode === "chat_search"
              ? response.verification_results
              : undefined,
          renderedBrief:
            response.ui_mode === "chat_search" ? response.rendered_brief : null,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
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
          uiMode === "chat_search" ? "assistant-layout--chat-search" : ""
        }`}
      >
        <AssistantChat
          messages={messages}
          input={input}
          loading={loading}
          error={error}
          latestRouter={router}
          onInputChange={setInput}
          onSend={handleSend}
        />
        {uiMode === "brief_workspace" && (
          <aside className="assistant-side">
            <BriefDraftPanel brief={brief} />
            <FoundItemsPanel items={foundItems} loading={loading} />
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
