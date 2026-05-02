import { Link } from "react-router-dom";
import { useState } from "react";
import type { ChatMessage, GlobalRagAnswer } from "../api";
import { answerGlobalSearch } from "../api";
import RagChat from "../components/RagChat";
import SourceList from "../components/SourceList";

export default function SearchPage() {
  const [latestAnswer, setLatestAnswer] = useState<GlobalRagAnswer | null>(null);

  async function handleAsk(message: string, history: ChatMessage[]) {
    const answer = await answerGlobalSearch(message, history);
    setLatestAnswer(answer);
    return answer;
  }

  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">AI Search</p>
          <h1>Поиск по всей базе договоров</h1>
        </div>
        <p className="workspace-header__note">
          Ответы формируются локальной LLM и привязаны к найденным фрагментам.
        </p>
      </header>

      <section className="search-grid">
        <RagChat
          title="Умный поиск"
          placeholder="Например: мне нужны поставщики фруктов"
          emptyHint="Сформулируйте запрос обычным языком. ARGUS найдет релевантные договоры, сгруппирует их по подрядчикам и даст ответ с источниками."
          onAsk={handleAsk}
        />
        <GlobalResultMirror answer={latestAnswer} />
      </section>
    </main>
  );
}

function GlobalResultMirror({
  answer,
}: {
  answer: GlobalRagAnswer | null;
}) {
  if (!answer) {
    return (
      <aside className="insight-panel">
        <p className="eyebrow">Results</p>
        <h2>Подрядчики появятся здесь</h2>
        <p className="muted">
          После ответа ARGUS покажет карточки подрядчиков и источники, чтобы
          можно было перейти глубже.
        </p>
      </aside>
    );
  }

  return (
    <aside className="insight-panel">
      <p className="eyebrow">Results</p>
      <h2>Подходящие подрядчики</h2>
      <div className="result-list">
        {answer.contractors.map((contractor) => (
          <Link
            className="result-card result-card--link"
            key={contractor.contractor_id}
            to={`/contractors/${contractor.contractor_id}`}
          >
            <div className="result-card__header">
              <h3>{contractor.name}</h3>
              <span className="score">{contractor.score.toFixed(3)}</span>
            </div>
            <p className="snippet">{contractor.top_snippet}</p>
            <p className="meta">
              {contractor.document_count} договоров ·{" "}
              {contractor.matched_chunks_count} совпадений
            </p>
          </Link>
        ))}
      </div>
      <SourceList sources={answer.sources} />
    </aside>
  );
}
