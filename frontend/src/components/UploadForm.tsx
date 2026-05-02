import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../api";

export default function UploadForm() {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/documents/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`${res.status}: ${body}`);
      }
      const { document_id } = (await res.json()) as { document_id: string };
      navigate(`/documents/${document_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setUploading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx"
          required
          disabled={uploading}
        />
        <button type="submit" disabled={uploading} style={{ padding: "0.4rem 1rem" }}>
          {uploading ? "Загружаю…" : "Загрузить"}
        </button>
      </div>
      {error && (
        <p style={{ color: "#b91c1c", marginTop: "0.5rem", fontSize: "0.9rem" }}>
          Ошибка: {error}
        </p>
      )}
    </form>
  );
}
