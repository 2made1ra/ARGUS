import { useState } from "react";
import type { ContractorSearchResult } from "../api";
import { searchContractors } from "../api";
import ContractorSearchResults from "../components/ContractorSearchResults";
import SearchBar from "../components/SearchBar";
import UploadForm from "../components/UploadForm";

export default function Home() {
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
      <h1 style={{ marginBottom: "1.5rem" }}>ARGUS — тестовый интерфейс</h1>
      <UploadForm />
      <section className="panel">
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
    </div>
  );
}
