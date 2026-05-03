import { Link } from "react-router-dom";
import { useState } from "react";
import type { GlobalRagAnswer, SourceRef } from "../api";
import { answerGlobalSearch } from "../api";
import AssistantContent from "./AssistantContent";
import SourceList from "./SourceList";
import {
  compactDocumentTitle,
  formatPageRange,
  matchLabel,
} from "../utils/searchPresentation";

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
  const sourcesByContractor = groupSourcesByContractor(answer);

  return (
    <section className="search-results-section">
      <div className="section-heading">
        <h2>Подходящие подрядчики</h2>
        <span className="meta">{answer.contractors.length} найдено</span>
      </div>
      <div className="result-list">
        {answer.contractors.map((contractor) => {
          const keySources =
            sourcesByContractor.get(contractor.contractor_id)?.slice(0, 2) ?? [];

          return (
            <article className="contractor-card" key={contractor.contractor_id}>
              <div className="contractor-card__top">
                <div>
                  <h3 className="compact-title">{contractor.name}</h3>
                  <p className="contractor-card__stats">
                    {contractor.document_count} договоров ·{" "}
                    {contractor.matched_chunks_count} найденных фрагментов
                  </p>
                </div>
                <span className="match-badge">{matchLabel(contractor.score)}</span>
              </div>

              <div className="contractor-card__reason">
                <span>Почему подходит</span>
                <p>{contractor.top_snippet}</p>
              </div>

              {keySources.length > 0 && (
                <div className="contractor-card__sources">
                  <span>Ключевые источники</span>
                  <div>
                    {keySources.map(({ source, index }) => (
                      <Link
                        className="contractor-source"
                        key={`${source.document_id}-${source.chunk_index}-${index}`}
                        to={`/documents/${source.document_id}`}
                      >
                        <span className="source-chip__index">S{index + 1}</span>
                        <span className="contractor-source__body">
                          <span className="compact-title">
                            {compactDocumentTitle(source.document_title)}
                          </span>
                          <span className="meta">
                            {formatPageRange(source.page_start, source.page_end)}
                          </span>
                          <span className="contractor-source__snippet">
                            {source.snippet}
                          </span>
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              <div className="contractor-card__actions">
                <Link
                  className="contractor-card__cta"
                  to={`/contractors/${contractor.contractor_id}`}
                >
                  Открыть подрядчика
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function groupSourcesByContractor(
  answer: GlobalRagAnswer,
): Map<string, Array<{ source: SourceRef; index: number }>> {
  const grouped = new Map<string, Array<{ source: SourceRef; index: number }>>();

  answer.sources.forEach((source, index) => {
    if (source.contractor_id === null) return;

    const group = grouped.get(source.contractor_id) ?? [];
    group.push({ source, index });
    grouped.set(source.contractor_id, group);
  });

  return grouped;
}
