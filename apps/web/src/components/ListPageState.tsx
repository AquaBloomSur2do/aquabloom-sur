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
        <div className="state-panel state-panel--loading" role="status">
          {loadingMessage}
        </div>
      ) : error ? (
        <div className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button type="button" className="btn btn-primary" onClick={onRetry}>
            Reintentar
          </button>
        </div>
      ) : isEmpty ? (
        <div className="state-panel state-panel--empty">{emptyMessage}</div>
      ) : (
        children
      )}
    </div>
  );
}