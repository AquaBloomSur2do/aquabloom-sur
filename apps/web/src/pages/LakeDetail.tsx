import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '../services/apiClient';
import type { LakeDetailResponse } from '../types/lake';
import { NotFound } from './NotFound';

export function LakeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [lake, setLake] = useState<LakeDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isError404, setIsError404] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const fetchLake = async () => {
      if (!id) return;
      try {
        const data = await apiClient.get<LakeDetailResponse>(`lakes/${id}`);
        if (isMounted) setLake(data);
      } catch {
        if (isMounted) {
          setIsError404(true);
          toast.error('No se pudo cargar la información del lago.');
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    void fetchLake();

    return () => {
      isMounted = false;
    };
  }, [id]);

  const handleDeactivate = async () => {
    if (!window.confirm('¿Estás seguro de que deseas desactivar este lago del catálogo?')) return;
    
    try {
      // Utilizamos el método request base especificando el método DELETE
      await apiClient.request(`lakes/${id}`, { method: 'DELETE' });
      toast.success('Lago desactivado exitosamente.');
      navigate('/lakes');
    } catch {
      toast.error('Error al desactivar el lago. Verifica tus permisos o conexión.');
    }
  };

  if (loading) {
    return (
      <div className="lake-detail-page p-8">
        <div className="state-panel state-panel--loading">Cargando detalle del lago...</div>
      </div>
    );
  }

  if (isError404 || !lake) {
    return <NotFound />;
  }

  const stationCount = Array.isArray(lake.stations) ? lake.stations.length : (lake.station_count ?? 0);

  return (
    <div className="lake-detail-page p-8">
      <header className="detail-header mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">{lake.name}</h1>
          <p className="text-gray-500">{lake.region}</p>
        </div>
        <div className="flex gap-4 items-center">
          <span className={`status-badge status-badge--${lake.status?.toLowerCase() ?? 'default'} px-3 py-1 rounded-full text-sm font-semibold`}>
            {lake.status ?? 'Sin estado'}
          </span>
          <button 
            onClick={handleDeactivate}
            className="bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 px-4 py-2 rounded text-sm font-semibold transition-colors border border-red-200"
          >
            Desactivar Lago
          </button>
          <Link 
            to={`/lakes/${id}/edit`} 
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-semibold transition-colors"
          >
            Editar Lago
          </Link>
        </div>
      </header>

      <div className="detail-content grid grid-cols-1 lg:grid-cols-2 gap-8">
        <section className="detail-section bg-white p-6 rounded-lg shadow border border-gray-200">
          <h2 className="text-xl font-bold mb-4 border-b pb-2">Ficha Descriptiva</h2>
          <div className="info-grid grid grid-cols-2 gap-4">
            <div className="info-item">
              <label className="text-xs font-bold uppercase text-gray-500">ID del Catálogo</label>
              <p className="text-sm font-mono">{lake.id}</p>
            </div>
            <div className="info-item">
              <label className="text-xs font-bold uppercase text-gray-500">Descripción</label>
              <p className="text-sm">{lake.description ?? 'Sin descripción disponible'}</p>
            </div>
            <div className="info-item col-span-2">
              <label className="text-xs font-bold uppercase text-gray-500 mb-1 block">Geometría (GeoJSON)</label>
              <pre className="bg-gray-50 p-3 rounded border text-xs overflow-auto max-h-32 text-gray-700">
                {lake.geom ? JSON.stringify(lake.geom, null, 2) : 'Datos espaciales no disponibles'}
              </pre>
            </div>
          </div>
        </section>

        <section className="detail-section bg-white p-6 rounded-lg shadow border border-gray-200">
          <h2 className="text-xl font-bold mb-4 border-b pb-2">
            Estaciones Registradas ({stationCount})
          </h2>
          
          {lake.stations && lake.stations.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-gray-100 text-gray-600">
                    <th className="p-3 border-b font-semibold">Código</th>
                    <th className="p-3 border-b font-semibold">Nombre</th>
                    <th className="p-3 border-b font-semibold">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {lake.stations.map((station) => (
                    <tr key={station.id} className="hover:bg-gray-50 transition-colors">
                      <td className="p-3 border-b font-mono text-xs">{station.code}</td>
                      <td className="p-3 border-b">{station.name}</td>
                      <td className="p-3 border-b">
                         <span className={`status-badge status-badge--${station.status?.toLowerCase() ?? 'default'}`}>
                          {station.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="state-panel state-panel--empty p-4 bg-gray-50 rounded text-center text-gray-500">
              No existen estaciones de monitoreo asociadas a este lago.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

