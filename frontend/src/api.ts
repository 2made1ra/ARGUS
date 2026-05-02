const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const getDocument = (id: string) =>
  apiFetch<unknown>(`/documents/${id}`);

export const listDocuments = () =>
  apiFetch<unknown[]>("/documents/");

export const getContractor = (id: string) =>
  apiFetch<unknown>(`/contractors/${id}`);

export const searchContractors = (q: string) =>
  apiFetch<unknown[]>(`/contractors/search?q=${encodeURIComponent(q)}`);

export const searchDocumentsForContractor = (id: string, q: string) =>
  apiFetch<unknown[]>(
    `/contractors/${id}/documents/search?q=${encodeURIComponent(q)}`
  );

export const searchWithinDocument = (id: string, q: string) =>
  apiFetch<unknown[]>(`/documents/${id}/search?q=${encodeURIComponent(q)}`);
