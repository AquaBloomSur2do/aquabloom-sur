import React, { useEffect, useState } from 'react';
import apiClient from '../services/apiClient';

export interface SampleRecord {
  id: string;
  station_id: string;
  sample_datetime_utc: string;
  chlorophyll_a_ug_l: number;
  is_quarantined: boolean;
  quarantine_reason: string | null;
}

export interface SampleListResponse {
  items: SampleRecord[];
  total: number;
  page: number;
  page_size: number;
}

type FilterMode = 'all' | 'valid' | 'quarantined';

export const SamplesDataGrid: React.FC = () => {
  const [samples, setSamples] = useState<SampleRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(20);
  const [filter, setFilter] = useState<FilterMode>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchSamples = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          page: String(page),
          page_size: String(pageSize),
        });

        if (filter === 'valid') {
          params.set('quarantine', 'false');
        } else if (filter === 'quarantined') {
          params.set('quarantine', 'true');
        }

        const data = await apiClient.get<SampleListResponse>(
          `/samples?${params.toString()}`
        );

        if (isMounted) {
          setSamples(Array.isArray(data.items) ? data.items : []);
          setTotal(typeof data.total === 'number' ? data.total : 0);
        }
      } catch (err) {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : 'Error al cargar las muestras desde el servidor.'
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void fetchSamples();

    return () => {
      isMounted = false;
    };
  }, [page, pageSize, filter]);

  const handleFilterChange = (newFilter: FilterMode) => {
    setFilter(newFilter);
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Registro de Muestras Importadas</h2>
          <p className="card-note">
            Separación de registros válidos y muestras retenidas en cuarentena por errores de formato o rango.
          </p>
        </div>

        <div className="tab-switch" role="group" aria-label="Filtro de muestras">
          <button
            type="button"
            onClick={() => handleFilterChange('all')}
            className={`tab-btn ${filter === 'all' ? 'active' : ''}`}
          >
            Todas
          </button>
          <button
            type="button"
            onClick={() => handleFilterChange('valid')}
            className={`tab-btn ${filter === 'valid' ? 'active' : ''}`}
          >
            Válidas
          </button>
          <button
            type="button"
            onClick={() => handleFilterChange('quarantined')}
            className={`tab-btn ${filter === 'quarantined' ? 'active' : ''}`}
          >
            Con Errores (Cuarentena)
          </button>
        </div>
      </div>

      {error ? (
        <div className="card-body">
          <div className="status-banner danger" role="alert">
            {error}
          </div>
        </div>
      ) : isLoading ? (
        <div className="card-body">
          <p className="subtitle">Cargando muestras...</p>
        </div>
      ) : samples.length === 0 ? (
        <div className="card-body">
          <p className="subtitle">
            No se encontraron muestras para el filtro seleccionado.
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Estación (ID)</th>
                <th>Fecha Muestra (UTC)</th>
                <th>Clorofila-a (µg/L)</th>
                <th>Estado</th>
                <th>Detalle / Motivo de Error</th>
              </tr>
            </thead>
            <tbody>
              {samples.map((sample) => (
                <tr
                  key={sample.id}
                  className={sample.is_quarantined ? 'row-quarantine' : ''}
                >
                  <td>
                    <span className="code-pill">{sample.station_id}</span>
                  </td>
                  <td>{new Date(sample.sample_datetime_utc).toUTCString()}</td>
                  <td className="cell-title">
                    {sample.chlorophyll_a_ug_l} µg/L
                  </td>
                  <td>
                    {sample.is_quarantined ? (
                      <span className="badge reported">En Cuarentena</span>
                    ) : (
                      <span className="badge validated">Válido</span>
                    )}
                  </td>
                  <td>
                    {sample.is_quarantined
                      ? sample.quarantine_reason || 'Error de validación o formato'
                      : 'OK'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && (
        <div
          className="card-body"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: '1px solid var(--line)',
          }}
        >
          <span className="card-note">
            Total de registros: <strong>{total}</strong> (Página {page} de{' '}
            {totalPages})
          </span>
          <div className="head-actions">
            <button
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              className="btn btn-secondary btn-sm"
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((prev) => prev + 1)}
              className="btn btn-secondary btn-sm"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </section>
  );
};

export default SamplesDataGrid;

