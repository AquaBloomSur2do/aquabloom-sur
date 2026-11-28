import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ListPageState } from '../components/ListPageState';
import { apiClient } from '../services/apiClient';

interface LakeSummary {
  id: string;
  name: string;
  region: string;
}

interface ActiveLakeResponse {
  items: LakeSummary[];
}

interface StationSummary {
  id: string;
  lake_id: string;
  code: string;
  name: string;
  status: string;
}

interface LakeStation {
  lake: LakeSummary;
  station: StationSummary;
}

const isForbiddenError = (error: unknown): boolean =>
  Boolean(error && typeof error === 'object' && 'status' in error && error.status === 403);

function renderStationStatus(status: string) {
  const normalized = status.trim().toLowerCase();
  if (normalized === 'active') {
    return (
      <span className="badge validated">
        <span aria-hidden="true">✓</span> Activa
      </span>
    );
  }
  return (
    <span className="badge draft">
      <span aria-hidden="true">○</span> Inactiva
    </span>
  );
}

export function StationsList() {
  const [stations, setStations] = useState<LakeStation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);

  const fetchStations = useCallback(async (isRetry = false) => {
    if (isRetry) {
      setIsLoading(true);
      setError(null);
    }

    try {
      const lakesResponse = await apiClient.get<ActiveLakeResponse>(
        'lakes?status=active&limit=100',
      );
      const stationGroups = await Promise.all(
        lakesResponse.items.map(async (lake) => {
          const lakeStations = await apiClient.get<StationSummary[]>(
            `lakes/${lake.id}/stations?status_filter=active`,
          );
          return lakeStations.map((station) => ({ lake, station }));
        }),
      );

      setStations(stationGroups.flat());
      setError(null);
      setIsForbidden(false);
    } catch (fetchError) {
      setIsForbidden(isForbiddenError(fetchError));
      setError(
        fetchError instanceof Error
          ? fetchError.message
          : 'No se pudieron cargar las estaciones.',
      );
      setStations([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchStations();
  }, [fetchStations]);

  return (
    <ListPageState
      eyebrow="Catálogo"
      title="Estaciones activas"
      isLoading={isLoading}
      loadingMessage="Cargando estaciones..."
      error={error}
      isEmpty={stations.length === 0}
      emptyMessage="No hay estaciones activas registradas."
      onRetry={() => void fetchStations(true)}
      isForbidden={isForbidden}
      forbiddenMessage="No tienes permisos para consultar las estaciones."
    >
      <section className="card" aria-label="Listado de estaciones activas">
        <div className="card-head">
          <div>
            <h2>Red de Estaciones Monitoreadas</h2>
            <p className="card-note">
              Estaciones activas asociadas a los lagos habilitados en tu organización.
            </p>
          </div>
          <span className="badge restricted">
            <span aria-hidden="true">📍</span> {stations.length}{' '}
            {stations.length === 1 ? 'estación activa' : 'estaciones activas'}
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Estación</th>
                <th>Código</th>
                <th>Lago</th>
                <th>Región</th>
                <th>Estado</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {stations.map(({ lake, station }) => (
                <tr key={station.id}>
                  <td className="cell-title">{station.name}</td>
                  <td>
                    <span className="code-pill">{station.code}</span>
                  </td>
                  <td>{lake.name}</td>
                  <td>{lake.region}</td>
                  <td>{renderStationStatus(station.status)}</td>
                  <td>
                    <Link
                      className="btn btn-secondary btn-sm"
                      to={`/lakes/${lake.id}`}
                    >
                      Ver lago
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </ListPageState>
  );
}


