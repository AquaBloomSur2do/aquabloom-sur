import { useEffect, useState } from 'react';
import type { SatelliteScene } from '../types/satellite';
import { apiClient } from '../services/apiClient';

interface SatelliteQueryPanelProps {
  lakeId: string;
}

export function SatelliteQueryPanel({ lakeId }: SatelliteQueryPanelProps) {
  const [scenes, setScenes] = useState<SatelliteScene[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchScenes = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<SatelliteScene[]>(`/api/v1/satellite/scenes?lake_id=${lakeId}`);
      setScenes(data);
    } catch {
      setError('Error al consultar las escenas satelitales.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await apiClient.get<SatelliteScene[]>(`/api/v1/satellite/scenes?lake_id=${lakeId}`);
        if (isMounted) {
          setScenes(data);
        }
      } catch {
        if (isMounted) {
          setError('Error al consultar las escenas satelitales.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };
    void loadData();
    return () => {
      isMounted = false;
    };
  }, [lakeId]);

  if (isLoading) {
    return <div role="status">Cargando consulta satelital...</div>;
  }

  if (error) {
    return (
      <div role="alert">
        <p>{error}</p>
        <button onClick={() => { void fetchScenes(); }}>Reintentar</button>
      </div>
    );
  }

  if (scenes.length === 0) {
    return <div role="status">No se encontraron escenas para este lago.</div>;
  }

  return (
    <div>
      <h3>Resultados Satelitales</h3>
      <ul>
        {scenes.map((scene) => (
          <li key={scene.id}>
            Escena {scene.id} - Fecha: {scene.capture_date}
          </li>
        ))}
      </ul>
    </div>
  );
}
