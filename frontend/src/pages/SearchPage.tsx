import GlobalSearchAnswer from "../components/GlobalSearchAnswer";

export default function SearchPage() {
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
        <GlobalSearchAnswer />
      </section>
    </main>
  );
}
