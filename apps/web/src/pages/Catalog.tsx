import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../services/apiClient';

// Contrato de interfaz alineado con el backend
interface LakeSummary {
  id: string;
  name: string;
  region: string;
  status: string;
}

interface PaginatedLakes {
  items: LakeSummary[];
  page: number;
  page_size: number;
  total: number;
}

export default function Catalog() {
  const [lakes, setLakes] = useState<LakeSummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCatalog = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Llamada al endpoint paginado que construimos previamente
      const data = await apiClient.get<PaginatedLakes>('/lakes');
      setLakes(data.items || []);
    } catch {
      setError('No se pudo cargar el catálogo de lagos. Verifica tu conexión al servidor.');
    } finally {
      setIsLoading(false);
    }
  }, []);

    useEffect(() => {
        const loadData = async () => {
            await fetchCatalog();
        };
        void loadData();
    },  [fetchCatalog]);

  // ESTADO 1: Carga (Evita la tabla vacía renderizando un Skeleton)
  if (isLoading) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-800">Catálogo de Lagos</h1>
        <div className="animate-pulse flex flex-col gap-4">
          <div className="h-12 w-full bg-gray-200 rounded"></div>
          <div className="h-12 w-full bg-gray-200 rounded"></div>
          <div className="h-12 w-full bg-gray-200 rounded"></div>
          <div className="h-12 w-full bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  // ESTADO 2: Error Recuperable (Fallo de red o API con botón de reintento)
  if (error) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <h2 className="text-xl font-bold text-red-700 mb-2">Error de Conexión</h2>
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={fetchCatalog}
            className="px-6 py-2 bg-red-600 text-white font-medium rounded hover:bg-red-700 transition-colors"
          >
            Reintentar Conexión
          </button>
        </div>
      </div>
    );
  }

  // ESTADO 3: Catálogo sin Resultados (Tabla oculta, mensaje claro)
  if (lakes.length === 0) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-800">Catálogo de Lagos</h1>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-10 text-center">
          <h2 className="text-xl font-bold text-gray-600 mb-1">Catálogo Vacío</h2>
          <p className="text-gray-500">No se encontraron registros en la base de datos.</p>
        </div>
      </div>
    );
  }

  // ESTADO 4: Éxito (Renderizado estándar de la tabla)
  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Catálogo de Lagos</h1>
      <div className="overflow-x-auto bg-white rounded-lg shadow border border-gray-200">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-gray-100 text-gray-700 border-b border-gray-200">
              <th className="p-4 font-semibold">Nombre</th>
              <th className="p-4 font-semibold">Región</th>
              <th className="p-4 font-semibold">Estado</th>
              <th className="p-4 font-semibold">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {lakes.map((lake) => (
              <tr key={lake.id} className="hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-0">
                <td className="p-4 font-medium text-gray-900">{lake.name}</td>
                <td className="p-4 text-gray-600">{lake.region}</td>
                <td className="p-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold status-badge--${lake.status.toLowerCase()}`}>
                    {lake.status}
                  </span>
                </td>
                <td className="p-4">
                  <Link to={`/lakes/${lake.id}`} className="text-blue-600 font-medium hover:text-blue-800 hover:underline">
                    Ver Detalles
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

