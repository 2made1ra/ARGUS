import { useState } from "react";

interface Props {
  onSearch: (query: string) => void | Promise<void>;
  placeholder?: string;
  buttonLabel?: string;
}

export default function SearchBar({
  onSearch,
  placeholder = "Введите запрос",
  buttonLabel = "Найти",
}: Props) {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || searching) return;

    setSearching(true);
    try {
      await onSearch(trimmed);
    } finally {
      setSearching(false);
    }
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        className="search-bar__input"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
      />
      <button className="search-bar__button" type="submit" disabled={searching}>
        {searching ? "Ищу..." : buttonLabel}
      </button>
    </form>
  );
}
