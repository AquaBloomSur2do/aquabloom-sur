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

        // CORRECCIÓN 2: Barra diagonal inicial añadida para evitar 404
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
    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-800">
            Registro de Muestras Importadas
          </h2>
          <p className="text-sm text-gray-500">
            Separación de registros válidos y muestras retenidas en cuarentena por errores de formato o rango.
          </p>
        </div>

        <div className="inline-flex rounded-md shadow-sm" role="group">
          <button
            type="button"
            onClick={() => handleFilterChange('all')}
            className={`px-4 py-2 text-sm font-medium border rounded-l-lg ${
              filter === 'all'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            Todas
          </button>
          <button
            type="button"
            onClick={() => handleFilterChange('valid')}
            className={`px-4 py-2 text-sm font-medium border-t border-b ${
              filter === 'valid'
                ? 'bg-green-600 text-white border-green-600'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            Válidas
          </button>
          <button
            type="button"
            onClick={() => handleFilterChange('quarantined')}
            className={`px-4 py-2 text-sm font-medium border rounded-r-lg ${
              filter === 'quarantined'
                ? 'bg-red-600 text-white border-red-600'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            Con Errores (Cuarentena)
          </button>
        </div>
      </div>

      {/* CORRECCIÓN 4: Renderizado mutuamente excluyente (Error vs UI) */}
      {error ? (
        <div
          className="p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md"
          role="alert"
        >
          {error}
        </div>
      ) : isLoading ? (
        <div className="py-8 text-center text-gray-500">
          Cargando muestras...
        </div>
      ) : samples.length === 0 ? (
        <div className="py-8 text-center text-gray-500 border border-dashed rounded-md">
          No se encontraron muestras para el filtro seleccionado.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">
                  Estación (ID)
                </th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">
                  Fecha Muestra (UTC)
                </th>
                <th className="px-4 py-3 text-right font-semibold text-gray-700">
                  Clorofila-a (µg/L)
                </th>
                <th className="px-4 py-3 text-center font-semibold text-gray-700">
                  Estado
                </th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">
                  Detalle / Motivo de Error
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {samples.map((sample) => (
                <tr
                  key={sample.id}
                  className={sample.is_quarantined ? 'bg-red-50/40' : ''}
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">
                    {sample.station_id}
                  </td>
                  <td className="px-4 py-3 text-gray-800">
                    {/* CORRECCIÓN 3: Preservar fidelidad científica con UTC */}
                    {new Date(sample.sample_datetime_utc).toUTCString()}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">
                    {sample.chlorophyll_a_ug_l}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {sample.is_quarantined ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        En Cuarentena
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Válido
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
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

      {/* Paginación simple (oculta si hay error para mejorar UX) */}
      {!error && (
        <div className="flex items-center justify-between pt-2 border-t border-gray-200 text-sm text-gray-600">
          <span>
            Total de registros: <strong>{total}</strong> (Página {page} de{' '}
            {totalPages})
          </span>
          <div className="space-x-2">
            <button
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((prev) => prev + 1)}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SamplesDataGrid;

