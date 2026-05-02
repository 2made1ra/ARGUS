export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface DocumentOut {
  id: string;
  title: string;
  status: string;
  doc_type: string | null;
  document_kind: string | null;
  contractor_entity_id: string | null;
  content_type: string;
  partial_extraction: boolean;
  error_message: string | null;
  created_at: string;
}

export interface DocumentFactsOut {
  fields: Record<string, unknown>;
  summary: string | null;
  key_points: string[];
  partial_extraction: boolean;
}

export interface ContractorOut {
  id: string;
  display_name: string;
  normalized_key: string;
  inn: string | null;
  kpp: string | null;
  created_at: string;
}

export interface ContractorProfileOut {
  contractor: ContractorOut;
  document_count: number;
  raw_mapping_count: number;
}

export interface ContractorSearchResult {
  contractor_id: string;
  name: string;
  score: number;
  matched_chunks_count: number;
  top_snippet: string;
}

export interface ChunkSnippet {
  page: number | null;
  snippet: string;
  score: number;
}

export interface DocumentSearchResult {
  document_id: string;
  title: string;
  date: string | null;
  matched_chunks: ChunkSnippet[];
}

export interface WithinDocumentResult {
  chunk_index: number;
  page_start: number | null;
  page_end: number | null;
  section_type: string | null;
  snippet: string;
  score: number;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const getDocument = (id: string) =>
  apiFetch<DocumentOut>(`/documents/${id}`);

export const getDocumentFacts = (id: string) =>
  apiFetch<DocumentFactsOut>(`/documents/${id}/facts`);

export const listDocuments = () =>
  apiFetch<DocumentOut[]>("/documents/?limit=20");

export const getContractor = (id: string) =>
  apiFetch<ContractorProfileOut>(`/contractors/${id}`);

export const listContractorDocuments = (id: string) =>
  apiFetch<DocumentOut[]>(`/contractors/${id}/documents?limit=20`);

export const searchContractors = (q: string) =>
  apiFetch<ContractorSearchResult[]>(
    `/search?q=${encodeURIComponent(q)}&limit=20`
  );

export const searchDocumentsForContractor = (id: string, q: string) =>
  apiFetch<DocumentSearchResult[]>(
    `/contractors/${id}/search?q=${encodeURIComponent(q)}&limit=20`
  );

export const searchWithinDocument = (id: string, q: string) =>
  apiFetch<WithinDocumentResult[]>(
    `/documents/${id}/search?q=${encodeURIComponent(q)}&limit=20`
  );

export async function patchDocumentFacts(
  id: string,
  body: {
    fields: Record<string, string | null>;
    summary: string | null;
    key_points: string[];
  }
): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${id}/facts`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}
