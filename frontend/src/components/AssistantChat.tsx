import type {
  ChatMessage,
  FoundItem,
  RouterDecision,
  SupplierVerificationResult,
} from "../api";
import { ArgusOrb, Icon, composerModes } from "./ArgusChrome";
import AssistantContent from "./AssistantContent";
import FoundItemsPanel from "./FoundItemsPanel";
import VerificationResultsPanel from "./VerificationResultsPanel";
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

export interface AssistantTimelineMessage extends ChatMessage {
  foundItems?: FoundItem[];
  foundItemsEmptyState?: "pending" | "no-results";
  verificationResults?: SupplierVerificationResult[];
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
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [messages.length, loading]);

  const hasChat = messages.length > 0 || loading;

  return (
    <section
      className={hasChat ? "chat-area assistant-chat" : "empty-area assistant-chat"}
      aria-label="Диалог с ARGUS"
    >
      {hasChat ? (
        <>
          <div className="chat-thread" ref={threadRef} aria-live="polite">
            {latestRouter && (
              <div className="assistant-router-badge">
                {intentLabels[latestRouter.intent]} ·{" "}
                {Math.round(latestRouter.confidence * 100)}%
              </div>
            )}
            {messages.map((message, index) => (
              <div className="assistant-timeline-item" key={`${message.role}-${index}`}>
                <ChatBubble message={message} />
                {message.role === "assistant" && message.foundItems !== undefined && (
                  <FoundItemsPanel
                    items={message.foundItems}
                    emptyState={message.foundItemsEmptyState}
                    title="Каталог в чате"
                    variant="inline"
                    selectedItemIds={selectedItemIds}
                    verificationResults={message.verificationResults ?? []}
                    onSelectedItemIdsChange={onSelectedItemIdsChange}
                  />
                )}
                {message.role === "assistant" &&
                  message.verificationResults !== undefined &&
                  message.verificationResults.length > 0 && (
                    <VerificationResultsPanel
                      relatedItems={message.foundItems ?? []}
                      results={message.verificationResults}
                      variant="inline"
                    />
                  )}
              </div>
            ))}
            {loading && <TypingIndicator />}
          </div>
          <InputComposer
            input={input}
            loading={loading}
            onInputChange={onInputChange}
            onSend={onSend}
          />
        </>
      ) : (
        <>
          <ArgusOrb loading={loading} />
          <div className="greeting-name">Привет!</div>
          <div className="greeting-q">Чем могу помочь?</div>
          <InputComposer
            input={input}
            loading={loading}
            onInputChange={onInputChange}
            onSend={onSend}
          />
        </>
      )}
      {error && <p className="error">Ошибка ассистента: {error}</p>}
    </section>
  );
}

function InputComposer({
  input,
  loading,
  onInputChange,
  onSend,
}: {
  input: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onSend: (message: string) => Promise<void>;
}) {
  const [mode, setMode] = useState<(typeof composerModes)[number]["id"]>("catalog");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeMode = composerModes.find((item) => item.id === mode) ?? composerModes[0];

  function resize(): void {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }

  async function submit(): Promise<void> {
    const message = input.trim();
    if (!message || loading) return;
    onInputChange("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    await onSend(message);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  return (
    <div className="composer-wrap">
      <div className="composer-box composer-row">
        <textarea
          ref={textareaRef}
          className="composer-ta"
          placeholder={`${activeMode.desc}...`}
          value={input}
          rows={1}
          disabled={loading}
          onChange={(event) => {
            onInputChange(event.target.value);
            resize();
          }}
          onKeyDown={handleKeyDown}
        />
        <div className="composer-send-wrap">
          <button
            className="send-btn"
            onClick={() => void submit()}
            disabled={!input.trim() || loading}
            type="button"
            aria-label="Отправить"
          >
            <Icon d="M12 19V5M5 12l7-7 7 7" size={15} />
          </button>
        </div>
      </div>

      <div className="mode-bar">
        {composerModes.map((item) => (
          <button
            key={item.id}
            className={`mode-tab${mode === item.id ? " mode-tab-active" : ""}`}
            onClick={() => setMode(item.id)}
            type="button"
          >
            <span className="mode-tab-icon">
              <Icon d={item.icon} size={13} />
            </span>
            <span className="mode-tab-label">{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ChatBubble({ message }: { message: AssistantTimelineMessage }) {
  return (
    <div className={`msg ${message.role === "user" ? "msg-user" : "msg-asst"}`}>
      <div className="msg-role">{message.role === "user" ? "Вы" : "ARGUS"}</div>
      <div className="msg-bubble">
        {message.role === "assistant" ? (
          <AssistantContent content={message.content} />
        ) : (
          <p>{message.content}</p>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="msg msg-asst">
      <div className="msg-role">ARGUS</div>
      <div className="typing">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
