import type { ChatMessage, RouterDecision } from "../api";
import AssistantContent from "./AssistantContent";

interface Props {
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  error: string | null;
  latestRouter: RouterDecision | null;
  onInputChange: (value: string) => void;
  onSend: (message: string) => Promise<void>;
}

const intentLabels: Record<RouterDecision["intent"], string> = {
  brief_discovery: "Бриф",
  supplier_search: "Поиск",
  mixed: "Бриф + поиск",
  clarification: "Уточнение",
};

export default function AssistantChat({
  messages,
  input,
  loading,
  error,
  latestRouter,
  onInputChange,
  onSend,
}: Props) {
  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextMessage = input.trim();
    if (!nextMessage || loading) return;
    await onSend(nextMessage);
  }

  return (
    <section className="assistant-chat panel" aria-label="Диалог с ARGUS">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Assistant</p>
          <h2>Рабочий диалог</h2>
        </div>
        {latestRouter && (
          <span className="assistant-router-badge">
            {intentLabels[latestRouter.intent]} ·{" "}
            {Math.round(latestRouter.confidence * 100)}%
          </span>
        )}
      </div>

      <div className="assistant-thread" aria-live="polite">
        {messages.length === 0 ? (
          <div className="assistant-empty">
            <strong>Опишите событие или потребность.</strong>
            <span>
              Например: "Хочу организовать музыкальный вечер на 100 человек".
            </span>
          </div>
        ) : (
          messages.map((message, index) => (
            <article
              className={`assistant-message assistant-message--${message.role}`}
              key={`${message.role}-${index}`}
            >
              <div className="assistant-message__role">
                {message.role === "user" ? "Вы" : "ARGUS"}
              </div>
              <div className="assistant-message__body">
                {message.role === "assistant" ? (
                  <AssistantContent content={message.content} />
                ) : (
                  <p>{message.content}</p>
                )}
              </div>
            </article>
          ))
        )}
      </div>

      <form className="assistant-composer" onSubmit={handleSubmit}>
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Напишите задачу: формат события, площадка, город, аудитория или нужные услуги"
          rows={4}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? "Отправляю..." : "Отправить"}
        </button>
      </form>

      {error && <p className="error">Ошибка ассистента: {error}</p>}
    </section>
  );
}
