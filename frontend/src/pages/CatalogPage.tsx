import type { FormEvent, KeyboardEvent } from "react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";
import type { CatalogImportJobOut, PriceItemOut } from "../api";
import {
  getCatalogImportJob,
  getCatalogImportJobStreamUrl,
  listCatalogItems,
  startCatalogImportJob,
} from "../api";
import { catalogImportStatusIsActive } from "../utils/catalogImportProgress";
import { isCurrentCatalogImportStream } from "../utils/catalogImportStream";
import {
  catalogPageCount,
  catalogPageOffset,
  catalogPageRangeLabel,
} from "../utils/catalogPagination";
import { nextModalFocusIndex } from "../utils/modalFocus";

const CATALOG_IMPORT_STORAGE_KEY = "argus.catalogImport.activeJobId";
const CATALOG_PAGE_SIZE = 50;

function readStoredImportJobId(): string | null {
  try {
    return window.localStorage.getItem(CATALOG_IMPORT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeImportJobId(id: string): void {
  try {
    window.localStorage.setItem(CATALOG_IMPORT_STORAGE_KEY, id);
  } catch {
    // localStorage can be unavailable in private contexts; streaming still works.
  }
}

function clearStoredImportJobId(): void {
  try {
    window.localStorage.removeItem(CATALOG_IMPORT_STORAGE_KEY);
  } catch {
    // localStorage can be unavailable in private contexts; nothing else to clear.
  }
}

const MODAL_FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "a[href]",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function getFocusableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(MODAL_FOCUSABLE_SELECTOR))
    .filter((element) => !element.hasAttribute("disabled") && element.tabIndex >= 0);
}

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PriceItemOut[]>([]);
  const [total, setTotal] = useState(0);
  const [indexedTotal, setIndexedTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isStartingUpload, setIsStartingUpload] = useState(false);
  const [activeJob, setActiveJob] = useState<CatalogImportJobOut | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const activeJobIdRef = useRef<string | null>(null);
  const uploadAbortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  const refreshedJobIdsRef = useRef<Set<string>>(new Set());
  const importTriggerRef = useRef<HTMLButtonElement | null>(null);
  const importDialogRef = useRef<HTMLElement | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const importCloseButtonRef = useRef<HTMLButtonElement | null>(null);

  const refreshCatalogPage = useCallback(async (pageNumber: number): Promise<void> => {
    const response = await listCatalogItems(
      CATALOG_PAGE_SIZE,
      catalogPageOffset(pageNumber, CATALOG_PAGE_SIZE),
    );
    setItems(response.items);
    setTotal(response.total);
    setIndexedTotal(response.indexed_total);
  }, []);

  const closeImportStream = useCallback((expectedStream?: EventSource): void => {
    if (
      expectedStream !== undefined &&
      eventSourceRef.current !== expectedStream
    ) {
      return;
    }
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }, []);

  const applyImportJobSnapshot = useCallback(
    (job: CatalogImportJobOut, sourceStream?: EventSource): void => {
      if (!isMountedRef.current) return;
      activeJobIdRef.current = job.id;
      setActiveJob(job);
      setJobError(job.error_message);

      if (catalogImportStatusIsActive(job.status)) {
        storeImportJobId(job.id);
        return;
      }

      clearStoredImportJobId();
      closeImportStream(sourceStream);

      if (
        job.status === "COMPLETED" &&
        !refreshedJobIdsRef.current.has(job.id)
      ) {
        refreshedJobIdsRef.current.add(job.id);
        void refreshCatalogPage(page).catch((err: unknown) => {
          setError(err instanceof Error ? err.message : String(err));
        });
      }
    },
    [closeImportStream, page, refreshCatalogPage],
  );

  const startImportStream = useCallback(
    (jobId: string): void => {
      closeImportStream();

      const eventSource = new EventSource(getCatalogImportJobStreamUrl(jobId));
      eventSourceRef.current = eventSource;
      activeJobIdRef.current = jobId;

      eventSource.onmessage = (event: MessageEvent<string>) => {
        if (
          !isCurrentCatalogImportStream({
            currentStream: eventSourceRef.current,
            expectedStream: eventSource,
            activeJobId: activeJobIdRef.current,
            expectedJobId: jobId,
          })
        ) {
          return;
        }
        try {
          const job = JSON.parse(event.data) as CatalogImportJobOut;
          applyImportJobSnapshot(job, eventSource);
        } catch (err: unknown) {
          setJobError(
            `Не удалось прочитать событие импорта: ${
              err instanceof Error ? err.message : String(err)
            }`,
          );
        }
      };

      eventSource.onerror = () => {
        void getCatalogImportJob(jobId)
          .then((job) => {
            if (
              !isCurrentCatalogImportStream({
                currentStream: eventSourceRef.current,
                expectedStream: eventSource,
                activeJobId: activeJobIdRef.current,
                expectedJobId: jobId,
              })
            ) {
              return;
            }
            applyImportJobSnapshot(job, eventSource);
            if (catalogImportStatusIsActive(job.status)) {
              setJobError(
                "Поток прогресса временно недоступен, переподключаюсь.",
              );
            }
          })
          .catch((err: unknown) => {
            if (
              !isCurrentCatalogImportStream({
                currentStream: eventSourceRef.current,
                expectedStream: eventSource,
                activeJobId: activeJobIdRef.current,
                expectedJobId: jobId,
              })
            ) {
              return;
            }
            setJobError(
              `Не удалось получить статус импорта: ${
                err instanceof Error ? err.message : String(err)
              }`,
            );
          });
      };
    },
    [applyImportJobSnapshot, closeImportStream],
  );

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      uploadAbortControllerRef.current?.abort();
      uploadAbortControllerRef.current = null;
      closeImportStream();
    };
  }, [closeImportStream]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    refreshCatalogPage(page)
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, refreshCatalogPage]);

  useEffect(() => {
    const storedJobId = readStoredImportJobId();
    if (storedJobId === null) return;

    let cancelled = false;
    void getCatalogImportJob(storedJobId)
      .then((job) => {
        if (cancelled) return;
        setImportModalOpen(true);
        applyImportJobSnapshot(job);
        if (catalogImportStatusIsActive(job.status)) {
          startImportStream(job.id);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        clearStoredImportJobId();
        setJobError(
          `Не удалось восстановить импорт каталога: ${
            err instanceof Error ? err.message : String(err)
          }`,
        );
      });

    return () => {
      cancelled = true;
    };
  }, [applyImportJobSnapshot, startImportStream]);

  const activePollingJobId =
    activeJob !== null && catalogImportStatusIsActive(activeJob.status)
      ? activeJob.id
      : null;

  useEffect(() => {
    if (activePollingJobId === null) return undefined;

    const pollJob = (): void => {
      void getCatalogImportJob(activePollingJobId)
        .then((job) => {
          if (activeJobIdRef.current !== activePollingJobId) return;
          applyImportJobSnapshot(job);
        })
        .catch((err: unknown) => {
          if (activeJobIdRef.current !== activePollingJobId) return;
          setJobError(
            `Не удалось получить статус импорта: ${
              err instanceof Error ? err.message : String(err)
            }`,
          );
        });
    };

    pollJob();
    const timer = window.setInterval(pollJob, 2_000);
    return () => window.clearInterval(timer);
  }, [activePollingJobId, applyImportJobSnapshot]);

  const importLocked =
    isStartingUpload ||
    (activeJob !== null && catalogImportStatusIsActive(activeJob.status));
  const canCloseImportModal = !importLocked;

  useEffect(() => {
    if (!importModalOpen) return;
    window.requestAnimationFrame(() => {
      if (importLocked) {
        importDialogRef.current?.focus();
        return;
      }

      const target =
        activeJob !== null && !catalogImportStatusIsActive(activeJob.status)
          ? (importCloseButtonRef.current ?? importDialogRef.current)
          : (importFileInputRef.current ??
            importCloseButtonRef.current ??
            importDialogRef.current);
      target?.focus();
    });
  }, [activeJob, importLocked, importModalOpen]);

  const handleOpenImportModal = (): void => {
    if (!importLocked) {
      uploadAbortControllerRef.current?.abort();
      uploadAbortControllerRef.current = null;
      activeJobIdRef.current = null;
      setSelectedFile(null);
      setActiveJob(null);
      setJobError(null);
    }
    setImportModalOpen(true);
  };

  const handleCloseImportModal = (): void => {
    if (!canCloseImportModal) return;
    uploadAbortControllerRef.current?.abort();
    uploadAbortControllerRef.current = null;
    setImportModalOpen(false);
    setSelectedFile(null);
    if (activeJob === null || !catalogImportStatusIsActive(activeJob.status)) {
      activeJobIdRef.current = null;
      setActiveJob(null);
    }
    window.requestAnimationFrame(() => importTriggerRef.current?.focus());
  };

  const handleImportDialogKeyDown = (
    event: KeyboardEvent<HTMLElement>,
  ): void => {
    if (event.key === "Escape") {
      event.preventDefault();
      if (canCloseImportModal) {
        handleCloseImportModal();
      }
      return;
    }

    if (event.key !== "Tab") return;

    const dialog = importDialogRef.current;
    if (dialog === null) return;

    const focusableElements = getFocusableElements(dialog);
    if (focusableElements.length === 0) {
      event.preventDefault();
      dialog.focus();
      return;
    }

    const currentIndex = focusableElements.indexOf(
      document.activeElement as HTMLElement,
    );
    const nextIndex = nextModalFocusIndex(
      currentIndex,
      focusableElements.length,
      event.shiftKey,
    );
    if (nextIndex < 0) return;

    event.preventDefault();
    focusableElements[nextIndex]?.focus();
  };

  const handleImportSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    if (!selectedFile) {
      setJobError("Выберите CSV-файл для импорта.");
      return;
    }

    setIsStartingUpload(true);
    uploadAbortControllerRef.current?.abort();
    const uploadAbortController = new AbortController();
    uploadAbortControllerRef.current = uploadAbortController;
    activeJobIdRef.current = null;
    setActiveJob(null);
    setJobError(null);

    try {
      const job = await startCatalogImportJob(
        selectedFile,
        undefined,
        uploadAbortController.signal,
      );
      if (
        !isMountedRef.current ||
        uploadAbortControllerRef.current !== uploadAbortController ||
        uploadAbortController.signal.aborted
      ) {
        return;
      }
      storeImportJobId(job.id);
      applyImportJobSnapshot(job);
      if (catalogImportStatusIsActive(job.status)) {
        startImportStream(job.id);
      }
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        uploadAbortControllerRef.current !== uploadAbortController ||
        uploadAbortController.signal.aborted
      ) {
        return;
      }
      setJobError(
        `Не удалось запустить импорт каталога: ${
          err instanceof Error ? err.message : String(err)
        }`,
      );
    } finally {
      if (
        isMountedRef.current &&
        uploadAbortControllerRef.current === uploadAbortController
      ) {
        uploadAbortControllerRef.current = null;
        setIsStartingUpload(false);
      }
    }
  };

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ru-RU");
    if (!normalizedQuery) return items;

    return items.filter((item) =>
      [
        item.name,
        item.category,
        item.supplier,
        item.supplier_city,
        item.supplier_inn,
        item.unit,
        item.unit_price,
      ]
        .filter((value): value is string => value !== null)
        .some((value) =>
          value.toLocaleLowerCase("ru-RU").includes(normalizedQuery),
        ),
    );
  }, [items, query]);

  const pageCount = catalogPageCount(total, CATALOG_PAGE_SIZE);
  const pageRangeLabel = catalogPageRangeLabel({
    page,
    pageSize: CATALOG_PAGE_SIZE,
    total,
    loaded: items.length,
  });
  const canGoPrevious = page > 1 && !loading;
  const canGoNext = page < pageCount && !loading;

  const showImportStatus = isStartingUpload || activeJob !== null;
  const terminalJob =
    activeJob !== null && !catalogImportStatusIsActive(activeJob.status)
      ? activeJob
      : null;
  const importCompleted = terminalJob?.status === "COMPLETED";
  const importFailed = terminalJob?.status === "FAILED";
  const showWaiting = showImportStatus && terminalJob === null;

  return (
    <main className="workspace catalog-workspace">
      <header className="workspace-header catalog-header">
        <div className="catalog-header__intro">
          <p className="eyebrow">Каталог</p>
          <h1>Позиции price_items</h1>
          <p className="workspace-header__note">
            Административная таблица импортированных строк каталога. Детальная
            карточка показывает полный source_text и CSV provenance.
          </p>
        </div>
        <div className="catalog-controls">
          <div className="catalog-summary" aria-label="Сводка каталога">
            <span>
              <strong>{total}</strong>
              всего
            </span>
            <span>
              <strong>{indexedTotal}</strong>
              indexed
            </span>
          </div>
          <button
            ref={importTriggerRef}
            className="primary-action catalog-upload-trigger"
            type="button"
            onClick={handleOpenImportModal}
          >
            Загрузить базу
          </button>
          <label className="catalog-filter">
            <span>Фильтр на странице</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Название, поставщик, ИНН или город"
            />
          </label>
        </div>
      </header>

      {error && <p className="error">Ошибка каталога: {error}</p>}
      {loading && <p className="muted">Загружаю каталог...</p>}

      {!loading && items.length === 0 && (
        <section className="empty-state">
          <p className="eyebrow">Пусто</p>
          <h2>Позиции каталога пока не импортированы</h2>
          <p className="muted">
            Нажмите «Загрузить базу», чтобы импортировать prices.csv в
            price_items и индекс price_items_search_v1.
          </p>
        </section>
      )}

      {!loading && items.length > 0 && filteredItems.length === 0 && (
        <section className="empty-state empty-state--compact">
          <p className="eyebrow">Фильтр</p>
          <h2>Совпадений нет</h2>
        </section>
      )}

      {filteredItems.length > 0 && (
        <>
          <nav className="catalog-pagination" aria-label="Пагинация каталога">
            <span>{pageRangeLabel}</span>
            <div>
              <button
                className="secondary-action"
                type="button"
                disabled={!canGoPrevious}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Назад
              </button>
              <strong>
                {page}/{pageCount}
              </strong>
              <button
                className="secondary-action"
                type="button"
                disabled={!canGoNext}
                onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
              >
                Вперед
              </button>
            </div>
          </nav>

          <section className="catalog-table-wrap">
            <table className="catalog-table">
              <thead>
                <tr>
                  <th>Позиция</th>
                  <th>Цена</th>
                  <th>Поставщик</th>
                  <th>Категория</th>
                  <th>Индекс</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link className="catalog-item-link" to={`/catalog/items/${item.id}`}>
                        {item.name}
                      </Link>
                      <span className="catalog-table__meta">
                        {item.unit} · {item.supplier_city ?? "город не указан"}
                      </span>
                    </td>
                    <td>
                      <strong>{item.unit_price}</strong>
                      <span className="catalog-table__meta">{item.has_vat ?? "НДС —"}</span>
                    </td>
                    <td>
                      {item.supplier ?? "Не указан"}
                      <span className="catalog-table__meta">
                        ИНН {item.supplier_inn ?? "—"}
                      </span>
                    </td>
                    <td>{item.category ?? "—"}</td>
                    <td>
                      <span className="status-pill">{item.catalog_index_status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      {importModalOpen && (
        <div
          className="catalog-import-modal"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              handleCloseImportModal();
            }
          }}
        >
          <section
            ref={importDialogRef}
            className="catalog-import-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="catalog-import-title"
            tabIndex={-1}
            onKeyDown={handleImportDialogKeyDown}
          >
            <header className="catalog-import-dialog__header">
              <div>
                <p className="eyebrow">Импорт каталога</p>
                <h2 id="catalog-import-title">Загрузить базу</h2>
              </div>
              <button
                ref={importCloseButtonRef}
                className="catalog-import-dialog__close"
                type="button"
                onClick={handleCloseImportModal}
                disabled={!canCloseImportModal}
                aria-label="Закрыть окно импорта"
              >
                Закрыть
              </button>
            </header>

            {!showImportStatus && (
              <form className="catalog-import-dialog__form" onSubmit={handleImportSubmit}>
                <label className="catalog-import-picker">
                  <span>CSV-файл</span>
                  <input
                    ref={importFileInputRef}
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) => {
                      uploadAbortControllerRef.current?.abort();
                      uploadAbortControllerRef.current = null;
                      activeJobIdRef.current = null;
                      setSelectedFile(event.target.files?.[0] ?? null);
                      setJobError(null);
                      setActiveJob(null);
                    }}
                  />
                </label>
                <button
                  className="primary-action"
                  type="submit"
                  disabled={selectedFile === null}
                >
                  Загрузить
                </button>
              </form>
            )}

            {selectedFile && !showImportStatus && (
              <p className="catalog-import-selected">
                {selectedFile.name} · {Math.ceil(selectedFile.size / 1024)} КБ
              </p>
            )}

            {showWaiting && (
              <div className="catalog-import-waiting" aria-live="polite">
                <div className="catalog-import-waiting__spinner" aria-hidden="true" />
                <div>
                  <p className="catalog-import-progress__label">Загрузка базы</p>
                  <strong>{activeJob?.filename ?? selectedFile?.name ?? "prices.csv"}</strong>
                  <span>Пожалуйста, дождитесь завершения импорта.</span>
                </div>
              </div>
            )}

            {importCompleted && (
              <section className="catalog-import-terminal catalog-import-terminal--completed">
                <h3>База загружена</h3>
                <p>Каталог успешно импортирован и готов к работе.</p>
                <button
                  className="primary-action"
                  type="button"
                  onClick={handleCloseImportModal}
                >
                  ОК
                </button>
              </section>
            )}

            {importFailed && (
              <section className="catalog-import-terminal catalog-import-terminal--failed">
                <h3>Импорт остановлен</h3>
                <p>{terminalJob?.error_message ?? "Не удалось загрузить базу."}</p>
              </section>
            )}

            {jobError && <p className="catalog-import-error">{jobError}</p>}
          </section>
        </div>
      )}
    </main>
  );
}
