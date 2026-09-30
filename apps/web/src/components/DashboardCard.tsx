import React from 'react';
import { Link } from 'react-router-dom';

interface DashboardCardProps {
  title: string;
  count: number | null;
  isLoading: boolean;
  error: string | Error | null;
  linkTo: string;
  linkLabel: string;
}

export const DashboardCard: React.FC<DashboardCardProps> = ({
  title,
  count,
  isLoading,
  error,
  linkTo,
  linkLabel,
}) => {
  return (
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        padding: '24px',
        backgroundColor: '#ffffff',
        boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <h3
        style={{
          margin: 0,
          fontSize: '1.25rem',
          fontWeight: 600,
          color: '#374151',
        }}
      >
        {title}
      </h3>

      <div style={{ flexGrow: 1 }}>
        {isLoading ? (
          <span style={{ color: '#6b7280' }}>Cargando datos... ⏳</span>
        ) : error ? (
          <span style={{ color: '#ef4444' }}>⚠️ Error al cargar</span>
        ) : (
          <span
            style={{ fontSize: '2.5rem', fontWeight: 700, color: '#111827' }}
          >
            {count !== null ? count : 0}
          </span>
        )}
      </div>

      <Link
        to={linkTo}
        style={{
          color: '#2563eb',
          textDecoration: 'none',
          fontWeight: 500,
          marginTop: 'auto',
        }}
      >
        {linkLabel} ➔
      </Link>
    </div>
  );
};
