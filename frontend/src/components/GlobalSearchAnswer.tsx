import { Link } from "react-router-dom";
import { useState } from "react";
import type { GlobalRagAnswer } from "../api";
import { answerGlobalSearch } from "../api";
import AssistantContent from "./AssistantContent";
import SourceList from "./SourceList";
import { matchLabel } from "../utils/searchPresentation";

export default function GlobalSearchAnswer() {
  const [input, setInput] = useState("");
  const [latestAnswer, setLatestAnswer] = useState<GlobalRagAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setLoading(true);
    setError(null);
    setLatestAnswer(null);
    try {
      const answer = await answerGlobalSearch(question, []);
      setLatestAnswer(answer);
      setInput(question);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="global-search">
      <form className="global-search-form" onSubmit={handleSubmit}>
        <label htmlFor="global-search-query">Что нужно найти</label>
        <textarea
          id="global-search-query"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Например: нужно организовать спортивное мероприятие"
          rows={3}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? "Ищу..." : "Найти"}
        </button>
      </form>

      {!loading && !latestAnswer && !error && (
        <p className="global-search-empty">
          Опишите задачу обычным языком. ARGUS найдет релевантные договоры,
          сгруппирует их по подрядчикам и покажет проверяемые источники.
        </p>
      )}

      {loading && (
        <p className="global-search-empty">Подбираю подрядчиков и источники...</p>
      )}

      {error && <p className="error">Ошибка глобального поиска: {error}</p>}

      {latestAnswer && (
        <>
          <section className="global-answer" aria-live="polite">
            <div className="section-heading">
              <h2>Короткий вывод ARGUS</h2>
              <span className="meta">RAG · LM Studio</span>
            </div>
            <div className="global-answer__body">
              <AssistantContent content={latestAnswer.answer} />
            </div>
          </section>

          <ContractorResults answer={latestAnswer} />

          {latestAnswer.sources.length > 0 && (
            <section className="search-results-section">
              <div className="section-heading">
                <h2>Источники</h2>
                <span className="meta">
                  {latestAnswer.sources.length} фрагментов
                </span>
              </div>
              <SourceList sources={latestAnswer.sources} />
            </section>
          )}
        </>
      )}
    </section>
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
              <h3 className="compact-title">{contractor.name}</h3>
              <span className="match-badge">{matchLabel(contractor.score)}</span>
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
