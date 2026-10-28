import { useEffect, useState, type FormEvent } from 'react';
import { Pagination } from './Pagination';
import { ApiError, apiClient } from '../services/apiClient';
import type { PaginatedScenes, Scene } from '../types/scene';

interface SceneSelectorProps {
  lakeId: string;
}

interface DateRange {
  startDate: string;
  endDate: string;
}

const PAGE_SIZE = 20;

export function SceneSelector({ lakeId }: SceneSelectorProps) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [dateRange, setDateRange] = useState<DateRange | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!dateRange) return;

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
          setScenes(Array.isArray(response.items) ? response.items : []);
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
      setRangeError('La fecha inicial debe ser anterior o igual a la fecha final.');
      return;
    }

    setRangeError(null);
    setCurrentPage(1);
    setDateRange({ startDate, endDate });
  };

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;

  return (
    <section
      className="mt-6 bg-white p-5 md:p-6 rounded-xl shadow-sm border border-gray-200"
      aria-labelledby="scene-selector-title"
    >
      <div className="mb-4 border-b border-gray-100 pb-3">
        <h2 id="scene-selector-title" className="text-lg font-bold text-gray-800">
          Escenas registradas
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Consulta las escenas disponibles para este lago y selecciona una.
          Este listado no busca escenas en Copernicus.
        </p>
      </div>

      <aside
        className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
        role="note"
        aria-label="Advertencia sobre uso científico"
      >
        Advertencia: Este insumo muestra procedencia pero no se presenta como un
        dato científico validado.
      </aside>

      <form
        className="mb-4 flex flex-col md:flex-row md:items-end gap-3"
        onSubmit={handleSearch}
      >
        <div className="flex-1">
          <label
            htmlFor="scene-start-date"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Desde
          </label>
          <input
            id="scene-start-date"
            type="date"
            required
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          />
        </div>
        <div className="flex-1">
          <label
            htmlFor="scene-end-date"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Hasta
          </label>
          <input
            id="scene-end-date"
            type="date"
            required
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          />
        </div>
        <button type="submit" className="btn btn-primary">
          Buscar escenas
        </button>
      </form>

      {rangeError && (
        <p className="state-panel state-panel--error mb-4" role="alert">
          {rangeError}
        </p>
      )}

      {!dateRange ? (
        <p className="state-panel state-panel--empty">
          Selecciona un rango de fechas para consultar las escenas registradas.
        </p>
      ) : isLoading ? (
        <p className="state-panel state-panel--loading" role="status">
          Cargando escenas...
        </p>
      ) : error ? (
        <div className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setRetryCount((count) => count + 1)}
          >
            Reintentar
          </button>
        </div>
      ) : scenes.length === 0 ? (
        <p className="state-panel state-panel--empty">
          No hay escenas registradas para este lago en el rango seleccionado.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm min-w-[420px]">
              <thead>
                <tr className="text-gray-500 bg-gray-50">
                  <th scope="col" className="p-3 font-semibold">
                    Seleccionar
                  </th>
                  <th scope="col" className="p-3 font-semibold">
                    Identificador de escena
                  </th>
                  <th scope="col" className="p-3 font-semibold">
                    Fecha de adquisición
                  </th>
                </tr>
              </thead>
              <tbody>
                {scenes.map((scene) => (
                  <tr
                    key={scene.id}
                    className="border-t border-gray-100 hover:bg-gray-50"
                  >
                    <td className="p-3">
                      <input
                        type="radio"
                        name="selected-scene"
                        value={scene.id}
                        checked={selectedScene?.id === scene.id}
                        onChange={() => setSelectedScene(scene)}
                        aria-label={`Seleccionar escena ${scene.scene_identifier}`}
                        className="h-4 w-4 accent-blue-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                      />
                    </td>
                    <td className="p-3 font-mono text-xs text-gray-700">
                      {scene.scene_identifier}
                    </td>
                    <td className="p-3 text-gray-700">
                      {scene.acquisition_date}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedScene && (
            <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-4">
              <p className="text-sm font-semibold text-blue-900" role="status">
                Escena seleccionada: {selectedScene.scene_identifier} (
                {selectedScene.acquisition_date})
              </p>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="font-medium text-gray-700">Procedencia</dt>
                  <dd className="text-gray-600">
                    {selectedScene.provider || 'No disponible'}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-700">
                    Identificador externo
                  </dt>
                  <dd className="break-all font-mono text-gray-600">
                    {selectedScene.external_id || 'No disponible'}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-700">
                    Cobertura de nubes
                  </dt>
                  <dd className="text-gray-600">
                    {selectedScene.cloud_cover != null
                      ? `${selectedScene.cloud_cover}%`
                      : 'No disponible'}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-700">
                    Estado de la escena
                  </dt>
                  <dd className="text-gray-600">
                    {selectedScene.status || 'No disponible'}
                  </dd>
                </div>
              </dl>
            </div>
          )}

          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
          />
        </>
      )}
    </section>
  );
}
