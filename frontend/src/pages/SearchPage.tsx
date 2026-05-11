import GlobalSearchAnswer from "../components/GlobalSearchAnswer";

export default function SearchPage() {
  return (
    <main className="workspace search-workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Document RAG</p>
          <h1>Поиск по документам</h1>
        </div>
        <p className="workspace-header__note">
          Вторичный drill-down поиск по договорам: подрядчики, документы и
          проверяемые фрагменты.
        </p>
      </header>

      <section className="search-flow">
        <GlobalSearchAnswer />
      </section>
    </main>
  );
}
