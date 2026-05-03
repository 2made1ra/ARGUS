import UploadForm from "../components/UploadForm";

export default function Home() {
  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Upload</p>
          <h1>Загрузка договоров</h1>
        </div>
        <p className="workspace-header__note">
          После загрузки документ проходит SAGE, резолв подрядчика и индексацию
          в Qdrant.
        </p>
      </header>

      <section className="upload-layout">
        <div className="upload-drop">
          <UploadForm />
        </div>
        <aside className="insight-panel">
          <p className="eyebrow">Pipeline</p>
          <h2>QUEUED → INDEXED</h2>
          <div className="pipeline-list">
            <span>Сохранение файла</span>
            <span>Извлечение текста и полей</span>
            <span>Резолв подрядчика</span>
            <span>Индексация чанков</span>
          </div>
        </aside>
      </section>
    </main>
  );
}
