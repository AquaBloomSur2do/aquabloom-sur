import type { ReactNode } from 'react';

interface ListPageStateProps {
  eyebrow: string;
  title: string;
  summary?: string;
  isLoading: boolean;
  loadingMessage: string;
  error: string | null;
  isEmpty: boolean;
  emptyMessage: string;
  onRetry: () => void;
  children: ReactNode;
}

export function ListPageState({
  eyebrow,
  title,
  summary,
  isLoading,
  loadingMessage,
  error,
  isEmpty,
  emptyMessage,
  onRetry,
  children,
}: ListPageStateProps) {
  return (
    <div className="lakes-list-page">
      <header className="lakes-header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          {summary && <p className="text-gray-600">{summary}</p>}
        </div>
      </header>

      {isLoading ? (
        <div className="state-panel state-panel--loading state-container" role="status">
          <div className="spinner" aria-hidden="true"></div>
          <p>{loadingMessage}</p>
        </div>
      ) : error ? (
        <div className="state-panel state-panel--error state-container state-error" role="alert">
          <h3 style={{ margin: '0 0 1rem 0' }}>
            <span aria-hidden="true" style={{ marginRight: '8px' }}>⚠️</span>
            Error de conexión
          </h3>
          <p>{error}</p>
          <button type="button" className="btn btn-primary retry-button" onClick={onRetry}>
            Reintentar
          </button>
        </div>
      ) : isEmpty ? (
        <div className="state-panel state-panel--empty state-container state-empty">
          <span aria-hidden="true" style={{ fontSize: '2rem', marginBottom: '1rem' }}>📭</span>
          <p>{emptyMessage}</p>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
