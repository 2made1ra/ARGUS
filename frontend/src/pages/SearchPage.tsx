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
    <main className="workspace search-workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">AI Search</p>
          <h1>Поиск подрядчиков по базе договоров</h1>
        </div>
        <p className="workspace-header__note">
          Ответы формируются локальной LLM и привязаны к найденным фрагментам.
        </p>
      </header>

      <section className="search-flow">
        <RagChat
          title="Что нужно найти"
          placeholder="Например: нужно организовать спортивное мероприятие"
          emptyHint="Опишите задачу обычным языком. ARGUS найдет релевантные договоры, сгруппирует их по подрядчикам и покажет источники ниже."
          onAsk={handleAsk}
          composerPlacement="top"
          showSources={false}
        />

        {latestAnswer && <ContractorResults answer={latestAnswer} />}

        {latestAnswer && latestAnswer.sources.length > 0 && (
          <section className="search-results-section">
            <div className="section-heading">
              <h2>Источники</h2>
              <span className="meta">{latestAnswer.sources.length} фрагментов</span>
            </div>
            <SourceList sources={latestAnswer.sources} />
          </section>
        )}
      </section>
    </main>
  );
}

function ContractorResults({
  answer,
}: {
  answer: GlobalRagAnswer;
}) {
  return (
    <section className="search-results-section">
      <div className="section-heading">
        <h2>Подходящие подрядчики</h2>
        <span className="meta">{answer.contractors.length} найдено</span>
      </div>
      <div className="result-list">
        {answer.contractors.map((contractor) => (
          <Link
            className="result-card result-card--link"
            key={contractor.contractor_id}
            to={`/contractors/${contractor.contractor_id}`}
          >
            <div className="result-card__header">
              <h3>{contractor.name}</h3>
            </div>
            <p className="snippet">{contractor.top_snippet}</p>
            <p className="meta">
              {contractor.document_count} договоров ·{" "}
              {contractor.matched_chunks_count} совпадений
            </p>
          </Link>
        ))}
      </div>
    </section>
  );
}
