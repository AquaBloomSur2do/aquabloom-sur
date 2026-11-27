import type { ReactNode } from 'react';

export type PageStateVariant = 'loading' | 'error' | 'empty' | 'forbidden';

interface PageStateProps {
  variant: PageStateVariant;
  title?: string;
  message: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  action?: ReactNode;
}

export function PageState({
  variant,
  title,
  message,
  onRetry,
  retryLabel = 'Reintentar',
  action,
}: PageStateProps) {
  if (variant === 'loading') {
    return (
      <div className="page-state page-state--loading" role="status" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <div>
          {title && <h2>{title}</h2>}
          <p>{message}</p>
        </div>
      </div>
    );
  }

  if (variant === 'forbidden') {
    return (
      <div className="page-state page-state--forbidden" role="alert">
        <span className="page-state__icon" aria-hidden="true">🔒</span>
        <div>
          <h2>{title ?? 'Acceso denegado'}</h2>
          <p>{message}</p>
          {action}
        </div>
      </div>
    );
  }

  if (variant === 'empty') {
    return (
      <div className="page-state page-state--empty">
        <span className="page-state__icon" aria-hidden="true">📭</span>
        <div>
          {title && <h2>{title}</h2>}
          <p>{message}</p>
          {action}
        </div>
      </div>
    );
  }

  return (
    <div className="page-state page-state--error" role="alert">
      <span className="page-state__icon" aria-hidden="true">⚠️</span>
      <div>
        <h2>{title ?? 'Error de conexión'}</h2>
        <p>{message}</p>
        {onRetry && (
          <button type="button" className="btn btn-primary retry-button" onClick={onRetry}>
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}
