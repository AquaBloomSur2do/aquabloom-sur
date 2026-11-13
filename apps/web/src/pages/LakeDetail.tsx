import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError, apiClient } from '../services/apiClient';
import type { LakeDetailResponse } from '../types/lake';
import type { Station } from '../types/station';
import { NotFound } from './NotFound';
import BaseMap from '../components/Map/BaseMap';
import { SceneSelector } from '../components/SceneSelector';
import { SatelliteQueryPanel } from '../components/SatelliteQueryPanel';
import type { Scene } from '../types/scene';
import './LakeDetail.css';

interface LakeDetailProps {
  sandbox?: boolean;
}

const mockLake: LakeDetailResponse = {
  id: 'lake-villarrica',
  name: 'Lago Villarrica',
  region: 'Región de La Araucanía',
  status: 'ACTIVE',
  description:
    'Cuerpo de agua lacustre de origen glaciar. Monitoreo constante por florecimientos algales.',
};

const mockScenes = [
  {
    id: 'S2B_MSIL2A_20240115',
    date: '15 Ene 2024',
    satellite: 'Sentinel-2B',
  },
  {
    id: 'S2A_MSIL2A_20240125',
    date: '25 Ene 2024',
    satellite: 'Sentinel-2A',
  },
];

export function LakeDetail({ sandbox = false }: LakeDetailProps) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [lake, setLake] = useState<LakeDetailResponse | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [selectedMockSceneId, setSelectedMockSceneId] = useState<string | null>(
    null
  );
  const [desde, setDesde] = useState('2024-01-01');
  const [hasta, setHasta] = useState('2024-01-31');
  const [loading, setLoading] = useState(!sandbox);
  const [isError404, setIsError404] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [stationsError, setStationsError] = useState(false);

  useEffect(() => {
    if (sandbox) return;

    let mounted = true;
    const fetchData = async () => {
      if (!id) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const [lakeResult, stationsResult] = await Promise.allSettled([
          apiClient.get<LakeDetailResponse>(`lakes/${id}`),
          apiClient.get<Station[]>(`lakes/${id}/stations`),
        ]);
        if (mounted) {
          if (lakeResult.status === 'fulfilled') {
            setLake(lakeResult.value);
          } else if (
            lakeResult.reason instanceof ApiError &&
            lakeResult.reason.status === 404
          ) {
            setIsError404(true);
          } else {
            setDetailError('No se pudo cargar la información del lago.');
          }

          if (stationsResult.status === 'fulfilled') {
            setStations(
              Array.isArray(stationsResult.value) ? stationsResult.value : []
            );
          } else {
            setStationsError(true);
          }
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void fetchData();
    return () => {
      mounted = false;
    };
  }, [id, sandbox]);

  const handleDeactivate = async () => {
    if (!window.confirm('¿Desactivar este lago?')) return;
    try {
      await apiClient.request(`lakes/${id}`, { method: 'DELETE' });
      toast.success('Lago desactivado.');
      navigate('/lakes');
    } catch {
      toast.error('Error al desactivar.');
    }
  };

  const lakeToDisplay = sandbox ? mockLake : lake;
  const activeStations = stations.filter(
    (station) => station.status?.toLowerCase() === 'active'
  );
  const geomFeature =
    !sandbox && lake?.geom
      ? {
          type: 'Feature' as const,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          geometry: lake.geom as any,
          properties: { id: lake.id, nombre: lake.name },
        }
      : undefined;

  return (
    <div className="s2-ui-container">
      <div className="content view active">
        {sandbox ? (
          <>
            <header className="page-head">
              <div>
                <span className="eyebrow">{mockLake.region}</span>
                <h1>{mockLake.name}</h1>
                <p className="subtitle">{mockLake.description}</p>
              </div>
              <div className="head-actions">
                <span className="badge validated">Monitoreo Activo</span>
                <span className="badge draft no-dot">Área: 173 km²</span>
              </div>
            </header>

            <main className="dashboard-main">
              <div className="grid" style={{ alignContent: 'start' }}>
                <SceneSelector
                  desde={desde}
                  hasta={hasta}
                  onDesdeChange={setDesde}
                  onHastaChange={setHasta}
                  selectedSceneId={selectedMockSceneId}
                  onSelectScene={setSelectedMockSceneId}
                  scenes={mockScenes}
                />
                <SatelliteQueryPanel
                  statusText={
                    selectedMockSceneId ? 'Datos cargados' : 'Esperando selección'
                  }
                  cloudCoverPercentage={selectedMockSceneId ? 15 : undefined}
                  metadata={
                    selectedMockSceneId
                      ? { resolution: '10m', processingLevel: 'L2A (BOA)' }
                      : undefined
                  }
                />
              </div>

              <section className="card">
                <div className="card-head">
                  <h2>Estaciones Asociadas</h2>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                  <div className="activity">
                    <div className="activity-item" style={{ padding: '15px' }}>
                      <div className="activity-dot">ST</div>
                      <div>
                        <div className="activity-text">
                          <strong>ST-01 Centro Lago</strong>
                        </div>
                        <div className="activity-time">
                          Lat: -39.25, Lon: -72.11
                        </div>
                      </div>
                    </div>
                    <div className="activity-item" style={{ padding: '15px' }}>
                      <div className="activity-dot">ST</div>
                      <div>
                        <div className="activity-text">
                          <strong>ST-02 Bahía Pucón</strong>
                        </div>
                        <div className="activity-time">
                          Lat: -39.27, Lon: -71.98
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </main>
          </>
        ) : loading ? (
          <p className="lake-meta" role="status">Cargando detalle...</p>
        ) : isError404 ? (
          <NotFound />
        ) : detailError || !lakeToDisplay ? (
          <div className="card" role="alert">
            <div className="card-body">
              <p>{detailError ?? 'No se pudo cargar la información del lago.'}</p>
              <Link to="/lakes" className="btn btn-primary">
                Volver al catálogo
              </Link>
            </div>
          </div>
        ) : (
          <>
            <header className="page-head">
              <div>
                <span className="eyebrow">{lakeToDisplay.region}</span>
                <h1>{lakeToDisplay.name}</h1>
                <p className="subtitle">
                  {lakeToDisplay.description ?? 'Sin descripción'}
                </p>
                <span
                  className={`badge ${lakeToDisplay.status.toLowerCase() === 'active' ? 'validated' : 'draft'}`}
                >
                  {lakeToDisplay.status}
                </span>
              </div>
              <div className="head-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleDeactivate}
                >
                  Desactivar
                </button>
                <Link to={`/lakes/${id}/edit`} className="btn btn-primary">
                  Editar Lago
                </Link>
              </div>
            </header>

            <main className="dashboard-main">
              <div className="grid">
                <section className="card">
                  <div className="card-head">
                    <h2>Información</h2>
                  </div>
                  <div className="card-body grid">
                    <div className="detail">
                      <span>ID Catálogo</span>
                      <b>{lakeToDisplay.id}</b>
                    </div>
                    <div className="detail">
                      <span>Descripción</span>
                      <b>{lakeToDisplay.description ?? 'Sin descripción'}</b>
                    </div>
                  </div>
                </section>

                <section className="card">
                  <div className="card-head">
                    <h2>Visor Cartográfico</h2>
                  </div>
                  <div className="card-body">
                    <BaseMap geometries={geomFeature} />
                  </div>
                </section>

                <SceneSelector
                  lakeId={lakeToDisplay.id}
                  onSceneSelect={setSelectedScene}
                />
                <SatelliteQueryPanel
                  lakeId={lakeToDisplay.id}
                  statusText={
                    selectedScene ? 'Datos cargados' : 'Esperando selección'
                  }
                  cloudCoverPercentage={
                    selectedScene?.cloud_cover ?? undefined
                  }
                />
              </div>

              <section className="card">
                <div className="card-head">
                  <h2>Estaciones Asociadas</h2>
                  <div className="head-actions">
                    <span className="badge validated">
                      {activeStations.length} activas
                    </span>
                    <Link
                      className="btn btn-primary"
                      to={`/lakes/${id}/stations/new`}
                    >
                      Registrar estación
                    </Link>
                  </div>
                </div>
                <div className="card-body">
                  {stationsError ? (
                    <p className="lake-meta" role="alert">
                      No se pudieron cargar las estaciones de este lago.
                    </p>
                  ) : stations.length > 0 ? (
                    <div className="grid">
                      {stations.map((station) => (
                        <div className="lake-row" key={station.id}>
                          <div>
                            <div className="lake-name">{station.name}</div>
                            <div className="lake-meta">{station.code}</div>
                          </div>
                          <span className="badge draft">{station.status}</span>
                          <Link
                            className="btn btn-secondary"
                            to={`/lakes/${id}/stations/${station.id}/edit`}
                          >
                            Editar
                          </Link>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="lake-meta">No hay estaciones registradas.</p>
                  )}
                </div>
              </section>
            </main>
          </>
        )}
      </div>
    </div>
  );
}
