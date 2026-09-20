import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import type { LakeDetailResponse } from '../types/lake';

export function LakeDetail() {
  const { id } = useParams<{ id: string }>();
  const [lake, setLake] = useState<LakeDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      setError('No se indicó un lago válido.');
      return;
    }

    let isMounted = true;

    const fetchLake = async () => {
      setLoading(true);
      setError(null);

      try {
        const data = await apiClient.get<LakeDetailResponse>(`lakes/${id}`);
        if (isMounted) {
          setLake(data);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'No se pudo cargar el detalle del lago.');
          setLake(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void fetchLake();

    return () => {
      isMounted = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="lake-detail-page">
        <div className="state-panel state-panel--loading">Cargando detalle del lago...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="lake-detail-page">
        <div className="state-panel state-panel--error">
          <p>{error}</p>
          <Link to="/lakes" className="btn btn-primary">
            Volver a lagos
          </Link>
        </div>
      </div>
    );
  }

  if (!lake) {
    return (
      <div className="lake-detail-page">
        <h1>Lago no encontrado</h1>
        <p>El lago solicitado no existe o no está disponible.</p>
        <Link to="/lakes" className="btn btn-primary">
          Volver al listado
        </Link>
      </div>
    );
  }

  const stationCount = Array.isArray(lake.stations) ? lake.stations.length : lake.station_count ?? 0;

  return (
    <div className="lake-detail-page">
      <div className="detail-header">
        <Link to="/lakes" className="btn btn-secondary">
          ← Volver
        </Link>
        <h1>{lake.name}</h1>
      </div>

      <div className="detail-content">
        <div className="detail-section">
          <h2>Información general</h2>
          <div className="info-grid">
            <div className="info-item">
              <label>Región</label>
              <p>{lake.region}</p>
            </div>
            <div className="info-item">
              <label>Estado</label>
              <p>{lake.status ?? 'Sin estado'}</p>
            </div>
            <div className="info-item">
              <label>Estaciones</label>
              <p>{stationCount}</p>
            </div>
            <div className="info-item">
              <label>Descripción</label>
              <p>{lake.description ?? 'Sin descripción disponible'}</p>
            </div>
          </div>
        </div>

        <div className="detail-section">
          <h2>Identificador</h2>
          <p>ID del lago: <strong>{lake.id}</strong></p>
        </div>
      </div>
    </div>
  );
}
