import { useCallback, useEffect, useState, type KeyboardEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import { useAuth } from '../contexts/useAuth';
import type { LakeSummary } from '../types/lake';

const normalizeLakesResponse = (payload: unknown): LakeSummary[] => {
  if (Array.isArray(payload)) {
    return payload as LakeSummary[];
  }

  if (payload && typeof payload === 'object') {
    const candidate = payload as { items?: unknown; data?: unknown };

    if (Array.isArray(candidate.items)) {
      return candidate.items as LakeSummary[];
    }

    if (Array.isArray(candidate.data)) {
      return candidate.data as LakeSummary[];
    }
  }

  return [];
};

const getStationCount = (lake: LakeSummary): number => {
  if (typeof lake.station_count === 'number') {
    return lake.station_count;
  }

  if ('stations' in lake && Array.isArray(lake.stations)) {
    return lake.stations.length;
  }

  return 0;
};

export function LakesList() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = String(
    user?.app_metadata?.role ?? user?.user_metadata?.role ?? '',
  ).toLowerCase();
  const canCreateLake = ['administrador', 'investigador'].includes(role);
  const [lakes, setLakes] = useState<LakeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLakes = useCallback(async (isManual = false) => {
    if (isManual) {
      setLoading(true);
      setError(null);
    }

    try {
      const data = await apiClient.get<unknown>('lakes');
      setLakes(normalizeLakesResponse(data));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la lista de lagos.');
      setLakes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchLakes();
  }, [fetchLakes]);

  const handleRowNavigation = (id: string) => {
    navigate(`/lakes/${id}`);
  };

  const handleRowKeyDown = (event: KeyboardEvent<HTMLDivElement>, id: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleRowNavigation(id);
    }
  };

  const getStatusClass = (status: string | undefined) => {
    const normalizedStatus = status?.toLowerCase() ?? 'default';
    if (normalizedStatus === 'active' || normalizedStatus === 'activo') return 'public';
    if (normalizedStatus === 'inactive' || normalizedStatus === 'inactivo') return 'reported';
    return normalizedStatus;
  };

  const getStatusStyle = (status: string | undefined) => {
    const normalizedStatus = status?.toLowerCase();
    if (normalizedStatus === 'active' || normalizedStatus === 'activo') {
      return { background: '#dcfce7', color: '#166534' };
    }
    if (normalizedStatus === 'inactive' || normalizedStatus === 'inactivo') {
      return { background: '#fef3c7', color: '#92400e' };
    }
    return { background: '#e0e7ff', color: '#3730a3' };
  };

  const renderStatusIcon = (status: string | undefined) => {
    const isActive = ['active', 'activo'].includes(status?.toLowerCase() ?? '');
    return (
      <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" style={{ flex: '0 0 auto' }}>
        {isActive ? (
          <path d="m3 8 3.2 3.2L13 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          <circle cx="8" cy="8" r="5.25" stroke="currentColor" strokeWidth="1.5" />
        )}
      </svg>
    );
  };

  return (
    <div className="lakes-list-page">
      <div className="lakes-header">
        <div>
          <p className="eyebrow">Catálogo</p>
          <h1>Listado de Lagos</h1>
        </div>
        {canCreateLake && (
          <Link to="/lakes/new" className="btn btn-primary">
            + Registrar Lago
          </Link>
        )}
      </div>

      {loading && (
        <div className="state-panel state-panel--loading" role="status" aria-live="polite">
          Cargando lagos activos...
        </div>
      )}

      {!loading && error && (
        <div className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button type="button" className="btn btn-primary" onClick={() => void fetchLakes(true)}>
            Reintentar
          </button>
        </div>
      )}

      {!loading && !error && lakes.length === 0 && (
        <div className="state-panel state-panel--empty">
          No hay lagos activos registrados en este momento.
        </div>
      )}

      {!loading && !error && lakes.length > 0 && (
        <div className="lake-list" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="lake-list-head" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(7rem, 0.6fr) minmax(7rem, 0.6fr) minmax(7rem, 0.6fr) auto', gap: '0.75rem', padding: '0.75rem 1rem', color: '#475569', fontSize: '0.8rem', fontWeight: 700 }}>
            <span>Nombre</span>
            <span>Región</span>
            <span>Estado</span>
            <span>Cantidad de estaciones</span>
            <span>Acción</span>
          </div>
          {lakes.map((lake) => (
            <div
                  key={lake.id}
                  className="lake-row card"
                  onClick={() => handleRowNavigation(lake.id)}
                  onKeyDown={(event) => handleRowKeyDown(event, lake.id)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Ver detalle del lago ${lake.name}`}
                  style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(7rem, 0.6fr) minmax(7rem, 0.6fr) minmax(7rem, 0.6fr) auto', alignItems: 'center', gap: '0.75rem', padding: '1rem', border: '1px solid #e5e7eb', borderRadius: '0.75rem', background: '#fff' }}
                >
                  <span className="lake-name" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0, fontWeight: 650 }}>
                    <span className="lake-symbol" aria-hidden="true" style={{ display: 'grid', placeItems: 'center', width: '2rem', height: '2rem', flex: '0 0 auto', borderRadius: '50%', color: '#0f766e', background: '#ccfbf1' }}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M1.5 9.5c2-2 3.5 2 6.5 0s4.5 2 6.5 0M1.5 12.5c2-2 3.5 2 6.5 0s4.5 2 6.5 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                      </svg>
                    </span>
                    <span>{lake.name}</span>
                  </span>
                  <span className="metric-mini">{lake.region}</span>
                  <span className={`badge ${getStatusClass(lake.status)}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', width: 'fit-content', padding: '0.3rem 0.55rem', borderRadius: '999px', ...getStatusStyle(lake.status), fontSize: '0.75rem', fontWeight: 650 }}>
                    {renderStatusIcon(lake.status)}
                    {lake.status ?? 'Sin estado'}
                  </span>
                  <span className="metric-mini">{getStationCount(lake)}</span>
                  <span>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRowNavigation(lake.id);
                      }}
                    >
                      Ver detalle
                    </button>
                  </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
