import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError, apiClient } from '../services/apiClient';
import type { LakeDetailResponse } from '../types/lake';
import type { Station } from '../types/station';
import { NotFound } from './NotFound';
import BaseMap from '../components/Map/BaseMap';

export function LakeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [lake, setLake] = useState<LakeDetailResponse | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [isError404, setIsError404] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [stationsError, setStationsError] = useState(false);

  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      if (!id) return;
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
            setStations(Array.isArray(stationsResult.value) ? stationsResult.value : []);
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
  }, [id]);

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

  if (loading)
    return (
      <div className="p-8 text-center text-gray-500">Cargando detalle...</div>
    );
  if (isError404) return <NotFound />;
  if (detailError || !lake) {
    return (
      <div className="state-panel state-panel--error" role="alert">
        <p>{detailError ?? 'No se pudo cargar la información del lago.'}</p>
        <Link to="/lakes" className="btn btn-primary">
          Volver al catálogo
        </Link>
      </div>
    );
  }

  const activeStations = stations.filter(
    (s) => s.status?.toLowerCase() === 'active'
  );

  // RESOLUCIÓN DEL TS2322: Retornamos undefined explícito si no hay geometría
  // y aplicamos "as any" en la asignación para relajar el chequeo estricto
  // entre la interfaz local y @types/geojson
  const geomFeature = lake.geom
      ? {
          type: 'Feature' as const,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          geometry: lake.geom as any,
          properties: { id: lake.id, nombre: lake.name },
        }
      : undefined;

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto w-full">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-end gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl md:text-4xl font-bold text-gray-900 mb-1">
            {lake.name}
          </h1>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-gray-600 font-medium">{lake.region}</span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase status-badge--${lake.status?.toLowerCase()}`}
            >
              {lake.status}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 w-full md:w-auto">
          <button
            onClick={handleDeactivate}
            className="flex-1 md:flex-none text-center bg-white text-red-600 hover:bg-red-50 border border-red-200 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            Desactivar
          </button>
          <Link
            to={`/lakes/${id}/edit`}
            className="flex-1 md:flex-none text-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            Editar Lago
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 md:gap-8">
        <div className="xl:col-span-1 space-y-6 md:space-y-8">
          <section className="bg-white p-5 md:p-6 rounded-xl shadow-sm border border-gray-200">
            <h2 className="text-lg font-bold text-gray-800 mb-4 border-b border-gray-100 pb-2">
              Información
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                  ID Catálogo
                </label>
                <p className="text-sm font-mono text-gray-800 break-all bg-gray-50 p-2 rounded border border-gray-100">
                  {lake.id}
                </p>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
                  Descripción
                </label>
                <p className="text-sm text-gray-700 leading-relaxed">
                  {lake.description ?? 'Sin descripción'}
                </p>
              </div>
            </div>
          </section>

          <section className="bg-white p-5 md:p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-4 border-b border-gray-100 pb-2">
              <h2 className="text-lg font-bold text-gray-800">Estaciones</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold bg-green-100 text-green-800 px-2 py-1 rounded-full">
                  {activeStations.length} activas
                </span>
                <Link className="btn btn-secondary" to={`/lakes/${id}/stations/new`}>
                  Registrar estación
                </Link>
              </div>
            </div>

            {stationsError ? (
              <p className="state-panel state-panel--error" role="alert">
                No se pudieron cargar las estaciones de este lago.
              </p>
            ) : stations.length > 0 ? (
              <div className="overflow-x-auto -mx-5 md:mx-0">
                <table className="w-full text-left text-sm min-w-[300px]">
                  <thead>
                    <tr className="text-gray-500 bg-gray-50">
                      <th className="p-3 font-semibold rounded-tl-lg">
                        Código
                      </th>
                      <th className="p-3 font-semibold">Nombre</th>
                      <th className="p-3 font-semibold rounded-tr-lg text-right">
                        Estado
                      </th>
                      <th className="p-3 font-semibold text-right">Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stations.map((s) => (
                      <tr
                        key={s.id}
                        className="border-t border-gray-100 hover:bg-gray-50"
                      >
                        <td className="p-3 font-mono text-xs text-gray-600">
                          {s.code}
                        </td>
                        <td className="p-3 font-medium text-gray-800">
                          {s.name}
                        </td>
                        <td className="p-3 text-right">
                          <span
                            className={`inline-block w-2.5 h-2.5 rounded-full ${s.status === 'active' ? 'bg-green-500' : 'bg-red-500'}`}
                          ></span>
                        </td>
                        <td className="p-3 text-right">
                          <Link className="btn btn-secondary" to={`/lakes/${id}/stations/${s.id}/edit`}>
                            Editar
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4 bg-gray-50 rounded border border-gray-100 border-dashed">
                No hay estaciones registradas.
              </p>
            )}
          </section>
        </div>

        <section className="xl:col-span-2 bg-white p-2 md:p-4 rounded-xl shadow-sm border border-gray-200 flex flex-col h-[500px] md:h-[600px]">
          <h2 className="text-lg font-bold text-gray-800 mb-3 px-2 pt-2">
            Visor Cartográfico
          </h2>
          <div className="flex-1 rounded-lg overflow-hidden border border-gray-300 relative bg-gray-100 z-0">
            {/* Integración del BaseMap de la Tarea 069 */}
            <BaseMap geometries={geomFeature} />
          </div>
        </section>
      </div>
    </div>
  );
}

