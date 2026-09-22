import { useCallback, useEffect, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
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

  if (Array.isArray(lake.stations)) {
    return lake.stations.length;
  }

  return 0;
};

export function LakesList() {
  const navigate = useNavigate();
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

  const handleRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, id: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleRowNavigation(id);
    }
  };

  return (
    <div className="lakes-list-page">
      <div className="lakes-header">
        <div>
          <p className="eyebrow">Catálogo</p>
          <h1>Listado de Lagos</h1>
        </div>
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
        <div className="lakes-table-wrapper">
          <table className="lakes-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Región</th>
                <th>Estado</th>
                <th>Cantidad de estaciones</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {lakes.map((lake) => (
                <tr
                  key={lake.id}
                  className="lake-row"
                  onClick={() => handleRowNavigation(lake.id)}
                  onKeyDown={(event) => handleRowKeyDown(event, lake.id)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Ver detalle del lago ${lake.name}`}
                >
                  <td>{lake.name}</td>
                  <td>{lake.region}</td>
                  <td>
                    <span className={`status-badge status-badge--${lake.status?.toLowerCase?.() ?? 'default'}`}>
                      {lake.status ?? 'Sin estado'}
                    </span>
                  </td>
                  <td>{getStationCount(lake)}</td>
                  <td>
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
