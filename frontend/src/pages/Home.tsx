import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ContractorSearchResult } from "../api";
import { searchContractors } from "../api";
import ContractorSearchResults from "../components/ContractorSearchResults";
import SearchBar from "../components/SearchBar";
import UploadForm from "../components/UploadForm";

type Tab = "upload" | "search";

export default function Home() {
  const [searchParams] = useSearchParams();
  const initialTab: Tab = searchParams.get("tab") === "search" ? "search" : "upload";
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [results, setResults] = useState<ContractorSearchResult[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(nextQuery: string) {
    setQuery(nextQuery);
    setError(null);
    try {
      setResults(await searchContractors(nextQuery));
    } catch (err) {
      setResults(null);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: "1.5rem" }}>ARGUS</h1>

      <div className="tabs">
        <button
          className={`tab-btn${activeTab === "upload" ? " tab-btn--active" : ""}`}
          onClick={() => setActiveTab("upload")}
        >
          Загрузить документ
        </button>
        <button
          className={`tab-btn${activeTab === "search" ? " tab-btn--active" : ""}`}
          onClick={() => setActiveTab("search")}
        >
          Поиск
        </button>
      </div>

      {activeTab === "upload" && (
        <div style={{ marginTop: "1.25rem" }}>
          <UploadForm />
        </div>
      )}

      {activeTab === "search" && (
        <section className="panel" style={{ marginTop: "1.25rem" }}>
          <h2>Глобальный поиск</h2>
          <SearchBar
            onSearch={handleSearch}
            placeholder="Тема, контрагент или фрагмент договора"
          />
          {error && <p className="error">Ошибка поиска: {error}</p>}
          {results && (
            <ContractorSearchResults results={results} query={query} />
          )}
        </section>
      )}
    </div>
  );
}
