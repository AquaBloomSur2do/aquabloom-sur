import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polygon } from 'react-leaflet';
import L from 'leaflet';
import { toast } from 'sonner';
import { apiClient } from '../services/apiClient';
import type { LakeDetailResponse } from '../types/lake';
import type { Station } from '../types/station';
import { NotFound } from './NotFound';
import 'leaflet/dist/leaflet.css';

interface GeoJsonGeometry {
  type: 'Polygon' | 'MultiPolygon';
  coordinates: number[][][] | number[][][][];
}

// Icono personalizado rojo/distintivo para las estaciones activas en el mapa
const stationIcon = L.divIcon({
  className: 'custom-station-marker',
  html: `<div style="background-color: #ef4444; width: 14px; height: 14px; border: 2px solid white; border-radius: 50%; box-shadow: 0 0 4px rgba(0,0,0,0.4);"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

// Helper robusto y tipado para convertir coordenadas de polígono GeoJSON [lon, lat] a Leaflet [lat, lon]
const convertPolygonCoords = (geom: unknown): [number, number][][] => {
  if (!geom || typeof geom !== 'object') return [];
  const g = geom as { type?: string; coordinates?: unknown };
  
  if (!g.coordinates || !Array.isArray(g.coordinates)) return [];

  if (g.type === 'Polygon') {
    const coords = g.coordinates as number[][][];
    return coords.map((ring) => 
      ring.map(([lon, lat]) => [lat, lon] as [number, number])
    );
  }
  
  if (g.type === 'MultiPolygon') {
    const coords = g.coordinates as number[][][][];
    const firstPolygon = coords[0];
    if (!firstPolygon) return [];
    return firstPolygon.map((ring) => 
      ring.map(([lon, lat]) => [lat, lon] as [number, number])
    );
  }

  return [];
};

export function LakeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [lake, setLake] = useState<LakeDetailResponse | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [isError404, setIsError404] = useState(false);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      if (!id) return;
      setLoading(true);
      setLake(null);
      setStations([]);
      setIsError404(false);

      try {
        const [lakeData, stationsData] = await Promise.all([
          apiClient.get<LakeDetailResponse>(`lakes/${id}`),
          apiClient.get<Station[]>(`lakes/${id}/stations`)
        ]);

        if (mounted) {
          setLake(lakeData);
          setStations(Array.isArray(stationsData) ? stationsData : []);
        }
      } catch {
        if (mounted) {
          setIsError404(true);
          toast.error('No se pudo cargar la información del lago o sus estaciones.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void fetchData();

    return () => {
      mounted = false;
    };
  }, [id]);

  const handleDeactivate = async () => {
    if (!window.confirm('¿Estás seguro de que deseas desactivar este lago del catálogo?')) return;
    
    try {
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

  const activeStations = stations.filter((s) => s.status?.toLowerCase() === 'active');
  const polygonPositions = convertPolygonCoords(lake.geom as GeoJsonGeometry | null);
  
  const defaultCenter: [number, number] = polygonPositions.length > 0 && polygonPositions[0].length > 0
    ? polygonPositions[0][0]
    : [-39.58, -72.22];

  return (
    <div className="lake-detail-page p-8">
      <header className="detail-header mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">{lake.name}</h1>
          <p className="text-gray-500">{lake.region}</p>
        </div>
        <div className="flex gap-4 items-center">
          <span className={`status-badge status-badge--${lake.status?.toLowerCase() ?? 'default'}`}>
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
            Estaciones Registradas ({stations.length}) — Activas: {activeStations.length}
          </h2>
          
          {stations.length > 0 ? (
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
                  {stations.map((station) => (
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

      <section className="mt-8 bg-white p-6 rounded-lg shadow border border-gray-200">
        <h2 className="text-xl font-bold mb-4 border-b pb-2">Visualización Cartográfica y Estaciones Activas</h2>
        <div className="h-96 rounded overflow-hidden border z-0 relative">
          <MapContainer 
            center={defaultCenter} 
            zoom={11} 
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {polygonPositions.length > 0 && (
              <Polygon 
                positions={polygonPositions} 
                pathOptions={{ color: 'blue', fillColor: 'lightblue', fillOpacity: 0.4 }} 
              />
            )}

            {activeStations.map((station) => {
              if (!station.point || !station.point.coordinates) return null;
              const [lon, lat] = station.point.coordinates;

              return (
                <Marker key={station.id} position={[lat, lon]} icon={stationIcon}>
                  <Popup>
                    <div className="p-1">
                      <p className="font-bold text-sm">{station.name}</p>
                      <p className="text-xs text-gray-600">Código: {station.code}</p>
                      <span className="inline-block mt-1 px-2 py-0.5 text-xs bg-red-100 text-red-800 rounded">
                        Estación Activa
                      </span>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>
      </section>
    </div>
  );
}
