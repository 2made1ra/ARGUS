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
  apiFetch<DocumentOut[]>("/documents/");

export const getContractor = (id: string) =>
  apiFetch<unknown>(`/contractors/${id}`);

export const searchContractors = (q: string) =>
  apiFetch<unknown[]>(`/search?q=${encodeURIComponent(q)}`);

export const searchDocumentsForContractor = (id: string, q: string) =>
  apiFetch<unknown[]>(
    `/contractors/${id}/search?q=${encodeURIComponent(q)}`
  );

export const searchWithinDocument = (id: string, q: string) =>
  apiFetch<unknown[]>(`/documents/${id}/search?q=${encodeURIComponent(q)}`);
