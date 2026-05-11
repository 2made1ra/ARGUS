import { useState } from "react";
import type {
  ChatMessage,
  FoundItem,
  RouterDecision,
} from "../api";
import { assistantChat, emptyBriefState } from "../api";
import AssistantChat from "../components/AssistantChat";
import BriefDraftPanel from "../components/BriefDraftPanel";
import FoundItemsPanel from "../components/FoundItemsPanel";

export default function AssistantPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [brief, setBrief] = useState(emptyBriefState);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [foundItems, setFoundItems] = useState<FoundItem[]>([]);
  const [router, setRouter] = useState<RouterDecision | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(message: string): Promise<void> {
    setLoading(true);
    setError(null);
    setInput("");
    setMessages((current) => [...current, { role: "user", content: message }]);

    try {
      const response = await assistantChat({
        session_id: sessionId,
        message,
        brief,
      });
      setSessionId(response.session_id);
      setBrief(response.brief);
      setFoundItems(response.found_items);
      setRouter(response.router);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: response.message },
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

      <section className="assistant-layout">
        <AssistantChat
          messages={messages}
          input={input}
          loading={loading}
          error={error}
          latestRouter={router}
          onInputChange={setInput}
          onSend={handleSend}
        />
        <aside className="assistant-side">
          <BriefDraftPanel brief={brief} />
          <FoundItemsPanel items={foundItems} loading={loading} />
        </aside>
      </section>
    </main>
  );
}
