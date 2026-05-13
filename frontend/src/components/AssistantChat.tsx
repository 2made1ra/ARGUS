import type {
  ChatMessage,
  FoundItem,
  RenderedEventBrief,
  RouterDecision,
  SupplierVerificationResult,
} from "../api";
import AssistantContent from "./AssistantContent";
import FoundItemsPanel from "./FoundItemsPanel";
import RenderedBriefPanel from "./RenderedBriefPanel";
import VerificationResultsPanel from "./VerificationResultsPanel";

export interface AssistantTimelineMessage extends ChatMessage {
  foundItems?: FoundItem[];
  foundItemsEmptyState?: "pending" | "no-results";
  verificationResults?: SupplierVerificationResult[];
  renderedBrief?: RenderedEventBrief | null;
}

interface Props {
  messages: AssistantTimelineMessage[];
  input: string;
  loading: boolean;
  error: string | null;
  latestRouter: RouterDecision | null;
  selectedItemIds: string[];
  onInputChange: (value: string) => void;
  onSend: (message: string) => Promise<void>;
  onSelectedItemIdsChange: (itemIds: string[]) => void;
}

const intentLabels: Record<RouterDecision["intent"], string> = {
  brief_discovery: "Бриф",
  supplier_search: "Поиск",
  mixed: "Бриф + поиск",
  clarification: "Уточнение",
  selection: "Выбор",
  comparison: "Сравнение",
  verification: "Проверка",
  render_brief: "Финал",
};

export default function AssistantChat({
  messages,
  input,
  loading,
  error,
  latestRouter,
  selectedItemIds,
  onInputChange,
  onSend,
  onSelectedItemIdsChange,
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
            <div className="assistant-timeline-item" key={`${message.role}-${index}`}>
              <article
                className={`assistant-message assistant-message--${message.role}`}
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

              {message.role === "assistant" &&
                message.foundItems !== undefined && (
                  <FoundItemsPanel
                    items={message.foundItems}
                    emptyState={message.foundItemsEmptyState}
                    title="Каталог в чате"
                    variant="inline"
                    selectedItemIds={selectedItemIds}
                    onSelectedItemIdsChange={onSelectedItemIdsChange}
                  />
                )}
              {message.role === "assistant" &&
                message.verificationResults !== undefined &&
                message.verificationResults.length > 0 && (
                  <VerificationResultsPanel
                    results={message.verificationResults}
                    variant="inline"
                  />
                )}
              {message.role === "assistant" && message.renderedBrief && (
                <RenderedBriefPanel brief={message.renderedBrief} variant="inline" />
              )}
            </div>
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
