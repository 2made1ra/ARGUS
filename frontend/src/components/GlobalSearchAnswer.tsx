import { Link } from "react-router-dom";
import { useState } from "react";
import type { GlobalRagAnswer } from "../api";
import { answerGlobalSearch } from "../api";
import AssistantContent from "./AssistantContent";
import SourceList from "./SourceList";
import {
  compactDocumentTitle,
  formatPageRange,
  indexedSourcesForCitations,
  type IndexedSourceRef,
  matchLabel,
  sourceAnchorId,
  sourceDocumentTarget,
} from "../utils/searchPresentation";

export default function GlobalSearchAnswer() {
  const [input, setInput] = useState("");
  const [latestAnswer, setLatestAnswer] = useState<GlobalRagAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const answerView = latestAnswer ? buildAnswerView(latestAnswer) : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setLoading(true);
    setError(null);
    setLatestAnswer(null);
    setSourcesOpen(false);
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

  function handleCitationClick(sourceIndex: number) {
    setSourcesOpen(true);
    window.setTimeout(() => {
      const sourceId = sourceAnchorId("global-source", sourceIndex);
      const sourceElement = document.getElementById(sourceId);
      if (sourceElement === null) return;

      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}#${sourceId}`,
      );
      sourceElement.scrollIntoView({ block: "center" });
    }, 0);
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

      {latestAnswer && answerView && (
        <>
          <section className="global-answer" aria-live="polite">
            <div className="section-heading">
              <h2>Короткий вывод ARGUS</h2>
              <span className="meta">RAG · LM Studio</span>
            </div>
            <div className="global-answer__body">
              <AssistantContent
                citationAnchorPrefix="global-source"
                citationCount={latestAnswer.sources.length}
                citationIndexes={answerView.visibleSourceIndexes}
                content={latestAnswer.answer}
                onCitationClick={handleCitationClick}
              />
            </div>
          </section>

          <ContractorResults
            contractors={answerView.visibleContractors}
            sourceItems={answerView.visibleSourceItems}
          />

          {answerView.visibleSourceItems.length > 0 && (
            <SourceDisclosure
              open={sourcesOpen}
              sourceItems={answerView.visibleSourceItems}
              onToggle={setSourcesOpen}
            />
          )}
        </>
      )}
    </section>
  );
}

function ContractorResults({
  contractors,
  sourceItems,
}: {
  contractors: GlobalRagAnswer["contractors"];
  sourceItems: IndexedSourceRef[];
}) {
  const sourcesByContractor = groupSourcesByContractor(sourceItems);

  return (
    <section className="search-results-section">
      <div className="section-heading">
        <h2>Подходящие подрядчики</h2>
        <span className="meta">{contractors.length} найдено</span>
      </div>
      <div className="result-list">
        {contractors.map((contractor) => {
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
                        to={sourceDocumentTarget(source)}
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
  sourceItems: IndexedSourceRef[],
): Map<string, IndexedSourceRef[]> {
  const grouped = new Map<string, IndexedSourceRef[]>();

  sourceItems.forEach((sourceItem) => {
    const { source } = sourceItem;
    if (source.contractor_id === null) return;

    const group = grouped.get(source.contractor_id) ?? [];
    group.push(sourceItem);
    grouped.set(source.contractor_id, group);
  });

  return grouped;
}

function SourceDisclosure({
  open,
  sourceItems,
  onToggle,
}: {
  open: boolean;
  sourceItems: IndexedSourceRef[];
  onToggle: (open: boolean) => void;
}) {
  return (
    <details
      className="search-results-section source-disclosure"
      open={open}
      onToggle={(event) => onToggle(event.currentTarget.open)}
    >
      <summary className="source-disclosure__summary">
        <span className="source-disclosure__title">Источники</span>
        <span className="meta">{sourceItems.length} фрагментов</span>
      </summary>
      <SourceList anchorPrefix="global-source" sources={sourceItems} />
    </details>
  );
}

function buildAnswerView(answer: GlobalRagAnswer) {
  const citedSourceItems = indexedSourcesForCitations(
    answer.answer,
    answer.sources,
  );
  const recommendedContractorIds = new Set(
    citedSourceItems
      .map(({ source }) => source.contractor_id)
      .filter((contractorId): contractorId is string => contractorId !== null),
  );
  const visibleContractors = answer.contractors.filter((contractor) =>
    recommendedContractorIds.has(contractor.contractor_id),
  );
  const visibleContractorIds = new Set(
    visibleContractors.map((contractor) => contractor.contractor_id),
  );
  const visibleSourceItems = citedSourceItems.filter(
    ({ source }) =>
      source.contractor_id !== null &&
      visibleContractorIds.has(source.contractor_id),
  );
  const visibleSourceIndexes = new Set(
    visibleSourceItems.map(({ index }) => index),
  );

  return {
    visibleContractors,
    visibleSourceIndexes,
    visibleSourceItems,
  };
}
