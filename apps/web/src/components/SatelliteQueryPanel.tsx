import { useEffect, useState } from 'react';
import type { SatelliteScene } from '../types/satellite';
import { apiClient } from '../services/apiClient';

interface SatelliteQueryPanelProps {
  lakeId?: string;
  statusText?: string;
  cloudCoverPercentage?: number;
  metadata?: {
    resolution: string;
    processingLevel: string;
  };
}

function getCloudBadge(percentage: number) {
  if (percentage <= 20) {
    return { className: 'badge validated', icon: '☀️', text: 'Válido' };
  }
  if (percentage <= 60) {
    return { className: 'badge review', icon: '⛅', text: 'Nuboso' };
  }
  return { className: 'badge reported', icon: '☁️', text: 'Descartado' };
}

export function SatelliteQueryPanel({
  lakeId,
  statusText,
  cloudCoverPercentage,
  metadata,
}: SatelliteQueryPanelProps) {
  const [scenes, setScenes] = useState<SatelliteScene[]>([]);
  const [isLoading, setIsLoading] = useState(lakeId !== undefined);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!lakeId) return;

    let active = true;
    const loadScenes = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiClient.get<SatelliteScene[]>(
          `satellite/scenes?lake_id=${lakeId}`
        );
        if (active) setScenes(data);
      } catch {
        if (active) setError('Error al consultar las escenas satelitales.');
      } finally {
        if (active) setIsLoading(false);
      }
    };

    void loadScenes();
    return () => {
      active = false;
    };
  }, [lakeId, retryCount]);

  const hasMockResult = cloudCoverPercentage !== undefined;
  const cloudBadge = hasMockResult
    ? getCloudBadge(cloudCoverPercentage)
    : undefined;
  const statusLabel =
    statusText ??
    (isLoading
      ? 'Cargando consulta satelital...'
      : error
        ? 'Error de consulta'
        : scenes.length > 0
          ? 'Consulta completada'
          : 'Sin resultados');

  return (
    <section className="card">
      <div className="card-head">
        <h2>Panel de Consulta Satelital</h2>
        <span
          role="status"
          className="badge draft no-dot"
          style={{ fontWeight: 'normal' }}
        >
          {statusLabel}
        </span>
      </div>
      <div className="card-body">
        {hasMockResult && cloudBadge ? (
          <div className="grid">
            <div className="meta-block">
              <strong>Cobertura de Nubosidad</strong>
              <div
                style={{
                  marginTop: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                }}
              >
                <span
                  style={{
                    fontSize: '24px',
                    fontWeight: 800,
                    color: 'var(--navy)',
                  }}
                >
                  {cloudCoverPercentage}%
                </span>
                <span className={cloudBadge.className}>
                  {cloudBadge.icon} {cloudBadge.text}
                </span>
              </div>
            </div>
            {metadata && (
              <div className="detail-grid">
                <div className="detail">
                  <span>Resolución Espacial</span>
                  <b>{metadata.resolution}</b>
                </div>
                <div className="detail">
                  <span>Nivel de Procesamiento</span>
                  <b>{metadata.processingLevel}</b>
                </div>
              </div>
            )}
          </div>
        ) : isLoading ? (
          <p className="lake-meta">
            Cargando consulta satelital...
          </p>
        ) : error ? (
          <div role="alert">
            <p className="lake-meta">{error}</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setRetryCount((count) => count + 1)}
            >
              Reintentar
            </button>
          </div>
        ) : scenes.length > 0 ? (
          <div className="grid">
            {scenes.map((scene) => {
              const badge = getCloudBadge(scene.cloud_cover_percentage);
              return (
                <div className="lake-row" key={scene.id}>
                  <div>
                    <div className="lake-name">Escena {scene.id}</div>
                    <div className="lake-meta">
                      Fecha: {scene.acquisition_date}
                    </div>
                  </div>
                  <span className={badge.className}>
                    {badge.icon} {badge.text}
                  </span>
                  <strong className="metric-mini">
                    {scene.cloud_cover_percentage}%
                  </strong>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty show">
            <div className="empty-icon" aria-hidden="true">◎</div>
            <p className="lake-meta">
              {lakeId
                ? 'No se encontraron escenas para este lago.'
                : 'Selecciona una escena para ver sus metadatos y porcentaje de nubosidad.'}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
