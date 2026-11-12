import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Pagination } from './Pagination';
import { ApiError, apiClient } from '../services/apiClient';
import type { PaginatedScenes, Scene } from '../types/scene';

interface MockScene {
  id: string;
  date: string;
  satellite: string;
}

interface SceneSelectorProps {
  lakeId?: string;
  onSceneSelect?: (scene: Scene | null) => void;
  desde?: string;
  hasta?: string;
  onDesdeChange?: (value: string) => void;
  onHastaChange?: (value: string) => void;
  scenes?: MockScene[];
  selectedSceneId?: string | null;
  onSelectScene?: (id: string) => void;
}

interface DateRange {
  startDate: string;
  endDate: string;
}

interface DisplayScene {
  id: string;
  identifier: string;
  date: string;
  satellite: string;
  registeredScene?: Scene;
}

const PAGE_SIZE = 20;

export function SceneSelector({
  lakeId,
  onSceneSelect,
  desde,
  hasta,
  onDesdeChange,
  onHastaChange,
  scenes: mockScenes = [],
  selectedSceneId = null,
  onSelectScene,
}: SceneSelectorProps) {
  const isSandbox = lakeId === undefined;
  const [startDate, setStartDate] = useState(desde ?? '');
  const [endDate, setEndDate] = useState(hasta ?? '');
  const [dateRange, setDateRange] = useState<DateRange | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [apiScenes, setApiScenes] = useState<Scene[]>([]);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [newSceneId, setNewSceneId] = useState('');
  const [newSceneDate, setNewSceneDate] = useState('');
  const [isSimulatingPost, setIsSimulatingPost] = useState(false);
  const [registrationSuccess, setRegistrationSuccess] = useState<string | null>(
    null
  );
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    return () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    };
  }, []);

  useEffect(() => {
    if (!lakeId || !dateRange) return;

    const controller = new AbortController();
    let active = true;

    const loadScenes = async () => {
      setIsLoading(true);
      setError(null);
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate,
        page: String(currentPage),
        page_size: String(PAGE_SIZE),
      });

      try {
        const response = await apiClient.get<PaginatedScenes>(
          `lakes/${lakeId}/scenes?${params.toString()}`,
          { signal: controller.signal }
        );
        if (active) {
          setApiScenes(Array.isArray(response.items) ? response.items : []);
          setTotal(response.total);
        }
      } catch (requestError) {
        if (
          active &&
          !(requestError instanceof ApiError && requestError.isCancelled)
        ) {
          setError('No se pudieron cargar las escenas registradas.');
        }
      } finally {
        if (active) setIsLoading(false);
      }
    };

    void loadScenes();
    return () => {
      active = false;
      controller.abort();
    };
  }, [currentPage, dateRange, lakeId, retryCount]);

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (startDate > endDate) {
      setRangeError(
        'La fecha inicial debe ser anterior o igual a la fecha final.'
      );
      return;
    }

    setRangeError(null);
    setSelectedScene(null);
    onSceneSelect?.(null);
    setCurrentPage(1);
    setDateRange({ startDate, endDate });
  };

  const handleSimulatedRegister = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSimulatingPost(true);
    setRegistrationSuccess(null);

    const registrationTimer = setTimeout(() => {
      setIsSimulatingPost(false);
      setRegistrationSuccess(
        `Escena ${newSceneId} simulada y "registrada" exitosamente en staging (API pendiente).`
      );
      setNewSceneId('');
      setNewSceneDate('');

      const successTimer = setTimeout(() => {
        setRegistrationSuccess(null);
      }, 4000);
      timersRef.current.push(successTimer);
    }, 1000);
    timersRef.current.push(registrationTimer);
  };

  const scenesToDisplay: DisplayScene[] = isSandbox
    ? mockScenes.map((scene) => ({
        id: scene.id,
        identifier: scene.id,
        date: scene.date,
        satellite: scene.satellite,
      }))
    : apiScenes.map((scene) => ({
        id: scene.id,
        identifier: scene.scene_identifier,
        date: scene.acquisition_date,
        satellite: scene.provider ?? 'No disponible',
        registeredScene: scene,
      }));
  const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 0;
  const hasSearchResults = isSandbox || dateRange !== null;

  return (
    <div className="grid">
      {!isSandbox && (
        <section className="card">
          <div className="card-head">
            <h2>Registrar nueva escena (Demostración Staging)</h2>
          </div>
          <div className="card-body">
            <p className="lake-meta">
              Simulación de registro de insumo Sentinel-2 L2A (el endpoint POST
              en Satellite está en desarrollo).
            </p>
            {registrationSuccess && (
              <p className="card-note" role="status">{registrationSuccess}</p>
            )}
            <form className="grid grid-2" onSubmit={handleSimulatedRegister}>
              <div className="field">
                <label htmlFor="sim-scene-id" className="label">
                  Identificador Sentinel-2 L2A
                </label>
                <input
                  id="sim-scene-id"
                  className="control"
                  type="text"
                  required
                  placeholder="Ej: S2A_MSIL2A_20261028..."
                  value={newSceneId}
                  onChange={(event) => setNewSceneId(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="sim-scene-date" className="label">
                  Fecha de Captura
                </label>
                <input
                  id="sim-scene-date"
                  className="control"
                  type="date"
                  required
                  value={newSceneDate}
                  onChange={(event) => setNewSceneDate(event.target.value)}
                />
              </div>
              <button
                type="submit"
                disabled={isSimulatingPost}
                className="btn btn-primary"
              >
                {isSimulatingPost ? 'Registrando...' : 'Simular Registro'}
              </button>
            </form>
          </div>
        </section>
      )}

      <section className="card" aria-labelledby="scene-selector-title">
        <div className="card-head">
          <h2 id="scene-selector-title">
            {isSandbox ? 'Selección de Escena' : 'Escenas registradas'}
          </h2>
        </div>
        <div className="card-body">
          <form className="grid grid-2" onSubmit={handleSearch}>
            <div className="field">
              <label htmlFor={isSandbox ? 'desde' : 'scene-start-date'} className="label">
                Desde
              </label>
              <input
                id={isSandbox ? 'desde' : 'scene-start-date'}
                type="date"
                className="control"
                required={!isSandbox}
                value={isSandbox ? desde ?? startDate : startDate}
                onChange={(event) => {
                  setStartDate(event.target.value);
                  onDesdeChange?.(event.target.value);
                }}
              />
            </div>
            <div className="field">
              <label htmlFor={isSandbox ? 'hasta' : 'scene-end-date'} className="label">
                Hasta
              </label>
              <input
                id={isSandbox ? 'hasta' : 'scene-end-date'}
                type="date"
                className="control"
                required={!isSandbox}
                value={isSandbox ? hasta ?? endDate : endDate}
                onChange={(event) => {
                  setEndDate(event.target.value);
                  onHastaChange?.(event.target.value);
                }}
              />
            </div>
            {!isSandbox && (
              <button type="submit" className="btn btn-primary">
                Buscar escenas
              </button>
            )}
          </form>

          <aside
            className="security-note"
            role="note"
            aria-label="Advertencia sobre uso científico"
            style={{
              borderColor: '#f5c070',
              background: 'var(--warning-soft)',
              color: '#8c5910',
              margin: '20px 0',
            }}
          >
            <strong style={{ color: 'var(--warning)' }}>
              Advertencia Científica
            </strong>
            {isSandbox ? (
              <>
                La selección de una escena y el índice satelital asociado son
                estimaciones ópticas. <b>No equivalen a toxicidad confirmada</b> y
                deben complementarse con muestras limnológicas.
              </>
            ) : (
              <>
                Advertencia: Este insumo muestra procedencia pero no se presenta
                como un dato científico validado.
              </>
            )}
          </aside>

          {rangeError && (
            <p className="card-note" role="alert">{rangeError}</p>
          )}

          {!hasSearchResults ? (
            <p className="card-note">
              Selecciona un rango de fechas para consultar las escenas registradas.
            </p>
          ) : isLoading ? (
            <p className="card-note" role="status">Cargando escenas...</p>
          ) : error ? (
            <div role="alert">
              <p className="card-note">{error}</p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setRetryCount((count) => count + 1)}
              >
                Reintentar
              </button>
            </div>
          ) : scenesToDisplay.length === 0 ? (
            <p className="card-note">
              {isSandbox
                ? 'No hay escenas disponibles en este rango de fechas.'
                : 'No hay escenas registradas para este lago en el rango seleccionado.'}
            </p>
          ) : (
            <div className="grid">
              {scenesToDisplay.map((scene) => {
                const isSelected = isSandbox
                  ? selectedSceneId === scene.id
                  : selectedScene?.id === scene.id;

                return (
                  <label
                    key={scene.id}
                    className="lake-row"
                    style={{
                      cursor: 'pointer',
                      borderColor: isSelected ? 'var(--teal)' : 'var(--line)',
                      background: isSelected ? 'var(--teal-soft)' : 'transparent',
                    }}
                  >
                    <span className="lake-symbol">
                      <input
                        type="radio"
                        name={isSandbox ? 'scene_selector' : 'selected-scene'}
                        value={scene.id}
                        checked={isSelected}
                        aria-label={`Seleccionar escena ${scene.identifier}`}
                        onChange={() => {
                          if (isSandbox) {
                            onSelectScene?.(scene.id);
                          } else if (scene.registeredScene) {
                            setSelectedScene(scene.registeredScene);
                            onSceneSelect?.(scene.registeredScene);
                          }
                        }}
                      />
                    </span>
                    <span>
                    <span className="lake-name">
                      {isSandbox ? `Escena ${scene.identifier}` : scene.identifier}
                    </span>
                    <span className="lake-meta">
                      {isSandbox ? `Satélite: ${scene.satellite}` : `Registro ${scene.id}`}
                    </span>
                    </span>
                    <span className="metric-mini">
                      <strong>{scene.date}</strong>
                      <span>Fecha de captura</span>
                    </span>
                  </label>
                );
              })}

              {!isSandbox && selectedScene && (
                <div className="detail-grid">
                  <div className="detail">
                    <span>Escena seleccionada</span>
                    <b role="status">
                      Escena seleccionada: {selectedScene.scene_identifier} (
                      {selectedScene.acquisition_date})
                    </b>
                  </div>
                  <div className="detail">
                    <span>Procedencia</span>
                    <b>{selectedScene.provider || 'No disponible'}</b>
                  </div>
                  <div className="detail">
                    <span>Identificador externo</span>
                    <b>{selectedScene.external_id || 'No disponible'}</b>
                  </div>
                  <div className="detail">
                    <span>Cobertura de nubes</span>
                    <b>
                      {selectedScene.cloud_cover != null
                        ? `${selectedScene.cloud_cover}%`
                        : 'No disponible'}
                    </b>
                  </div>
                  <div className="detail">
                    <span>Estado de la escena</span>
                    <b>{selectedScene.status || 'No disponible'}</b>
                  </div>
                </div>
              )}
              {!isSandbox && totalPages > 0 && (
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={setCurrentPage}
                />
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
