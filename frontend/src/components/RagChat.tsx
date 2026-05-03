import { useState } from "react";
import type { ChatMessage, RagAnswer } from "../api";
import SourceList from "./SourceList";

interface Props {
  title: string;
  placeholder: string;
  emptyHint: string;
  onAsk: (message: string, history: ChatMessage[]) => Promise<RagAnswer>;
  initialPrompt?: string;
  composerPlacement?: "top" | "bottom";
  showSources?: boolean;
}

export default function RagChat({
  title,
  placeholder,
  emptyHint,
  onAsk,
  initialPrompt = "",
  composerPlacement = "bottom",
  showSources = true,
}: Props) {
  const [input, setInput] = useState(initialPrompt);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<RagAnswer["sources"]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setLoading(true);
    setError(null);
    try {
      const answer = await onAsk(question, messages);
      setMessages((current) => [
        ...current,
        { role: "user", content: question },
        { role: "assistant", content: answer.answer },
      ]);
      setSources(answer.sources);
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const composer = (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <textarea
        value={input}
        onChange={(event) => setInput(event.target.value)}
        placeholder={placeholder}
        rows={3}
      />
      <button type="submit" disabled={loading || !input.trim()}>
        {loading ? "Думаю..." : "Спросить"}
      </button>
    </form>
  );

  return (
    <section className="rag-chat">
      <div className="section-heading">
        <h2>{title}</h2>
        <span className="meta">RAG · LM Studio</span>
      </div>

      {composerPlacement === "top" && composer}

      <div className="chat-thread" aria-live="polite">
        {messages.length === 0 ? (
          <p className="chat-empty">{emptyHint}</p>
        ) : (
          messages.map((message, index) => (
            <article
              className={`chat-bubble chat-bubble--${message.role}`}
              key={`${message.role}-${index}`}
            >
              <p>{message.content}</p>
            </article>
          ))
        )}
      </div>

      {composerPlacement === "bottom" && composer}
      {error && <p className="error">Ошибка RAG: {error}</p>}
      {showSources && <SourceList sources={sources} />}
    </section>
  );
}
