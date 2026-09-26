import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient, ApiError } from '../services/apiClient';
import type { LakeDetailResponse } from '../types/lake';
import { NotFound } from './NotFound';

export function LakeDetail() {
  const { id } = useParams<{ id: string }>();
  const [lake, setLake] = useState<LakeDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetchLake = useCallback(async () => {
    if (!id) {
      setLake(null);
      setNotFound(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const data = await apiClient.get<LakeDetailResponse>(`lakes/${id}`);
      setLake(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        setLake(null);
        return;
      }

      setError(err instanceof Error ? err.message : 'No se pudo cargar la información del lago.');
      setLake(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void fetchLake();
  }, [fetchLake]);

  if (loading) {
    return (
      <div className="lake-detail-page">
        <div className="state-panel state-panel--loading" role="status" aria-live="polite">
          Cargando información del lago...
        </div>
      </div>
    );
  }

  if (notFound) {
    return <NotFound />;
  }

  if (error) {
    return (
      <div className="lake-detail-page">
        <div className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button type="button" className="btn btn-primary" onClick={() => void fetchLake()}>
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (!lake) {
    return <NotFound />;
  }

  const stationCount = typeof lake.station_count === 'number' ? lake.station_count : lake.stations?.length ?? 0;

  return (
    <div className="lake-detail-page">
      <div className="detail-header">
        <Link to="/lakes" className="btn-back">
          ← Volver
        </Link>
        <h1>{lake.name}</h1>
      </div>

      <div className="detail-content">
        <section className="detail-section">
          <h2>Información General</h2>
          <div className="info-grid">
            <div className="info-item">
              <label>Región:</label>
              <p>{lake.region}</p>
            </div>
            <div className="info-item">
              <label>Estado:</label>
              <p>{lake.status ?? 'Sin estado'}</p>
            </div>
            <div className="info-item">
              <label>Descripción:</label>
              <p>{lake.description ?? 'Sin descripción disponible.'}</p>
            </div>
          </div>
        </section>

        <section className="detail-section bg-white p-6 rounded-lg shadow border border-gray-200">
          <h2 className="text-xl font-bold mb-4 border-b pb-2">
            Estaciones Registradas ({stationCount})
          </h2>

          {lake.stations && lake.stations.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-gray-100 text-gray-600">
                    <th className="p-3 border-b font-semibold">Código</th>
                    <th className="p-3 border-b font-semibold">Nombre</th>
                    <th className="p-3 border-b font-semibold">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {lake.stations.map((station) => (
                    <tr key={station.id} className="hover:bg-gray-50 transition-colors">
                      <td className="p-3 border-b font-mono text-xs">{station.code}</td>
                      <td className="p-3 border-b">{station.name}</td>
                      <td className="p-3 border-b">
                        <span className={`status-badge status-badge--${station.status?.toLowerCase?.() ?? 'default'}`}>
                          {station.status ?? 'Sin estado'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="state-panel state-panel--empty p-4 bg-gray-50 rounded text-center text-gray-500">
              No existen estaciones de monitoreo asociadas a este lago.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

