export function createCatalogUploadAbortError(): Error {
  if (typeof DOMException !== "undefined") {
    return new DOMException("CSV upload was cancelled", "AbortError") as Error;
  }
  const error = new Error("CSV upload was cancelled");
  error.name = "AbortError";
  return error;
}
