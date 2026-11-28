import type { ReactNode } from 'react';
import { PageState } from './PageState';

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
  isForbidden?: boolean;
  forbiddenMessage?: string;
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
  isForbidden = false,
  forbiddenMessage = 'No tienes permisos para consultar este recurso.',
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
        <PageState variant="loading" message={loadingMessage} />
      ) : isForbidden ? (
        <PageState variant="forbidden" message={forbiddenMessage} />
      ) : error ? (
        <PageState variant="error" message={error} onRetry={onRetry} />
      ) : isEmpty ? (
        <PageState variant="empty" message={emptyMessage} />
      ) : (
        children
      )}
    </div>
  );
}
