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

export function StationsList() {
  const [stations, setStations] = useState<LakeStation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    } catch (fetchError) {
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
    >
        <div className="lakes-table-wrapper">
          <table className="lakes-table">
            <thead>
              <tr>
                <th>Estación</th>
                <th>Código</th>
                <th>Lago</th>
                <th>Región</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {stations.map(({ lake, station }) => (
                <tr key={station.id}>
                  <td>{station.name}</td>
                  <td>{station.code}</td>
                  <td>{lake.name}</td>
                  <td>{lake.region}</td>
                  <td>
                    <Link className="btn btn-secondary" to={`/lakes/${lake.id}`}>
                      Ver lago
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
    </ListPageState>
  );
}