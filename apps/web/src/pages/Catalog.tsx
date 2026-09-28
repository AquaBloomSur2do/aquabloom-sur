import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import apiClient from '../services/apiClient';
import { Pagination } from '../components/Pagination';

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

  // Estados de paginación y filtros
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [searchTerm, setSearchTerm] = useState<string>('');

  const fetchCatalog = useCallback(async (pageToFetch: number, search: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: pageToFetch.toString(),
        page_size: pageSize.toString(),
      });
      if (search) {
        params.append('search', search);
      }

      const data = await apiClient.get<PaginatedLakes>(`/lakes?${params.toString()}`);
      setLakes(data.items || []);
      setTotalItems(data.total || 0);
    } catch {
      setError('No se pudo cargar el catálogo de lagos. Verifica tu conexión al servidor.');
      toast.error('Falló la sincronización con el catálogo.');
    } finally {
      setIsLoading(false);
    }
  }, [pageSize]);

  // Cargar datos al cambiar de página o término de búsqueda
  useEffect(() => {
    const loadData = async () => {
      await fetchCatalog(currentPage, searchTerm);
    };
    void loadData();
  }, [currentPage, searchTerm, fetchCatalog]);

  const totalPages = Math.ceil(totalItems / pageSize) || 1;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Catálogo de Lagos</h1>

      {/* Barra de Filtros y Búsqueda con reseteo directo de página */}
      <div className="mb-6 flex gap-4 items-center">
        <input
          type="text"
          placeholder="Buscar lago por nombre..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setCurrentPage(1); // CRITERIO DE ACEPTACIÓN: Reseteo automático a página 1 al filtrar
          }}
          className="px-4 py-2 border border-gray-300 rounded-lg w-full max-w-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {isLoading ? (
        <div className="animate-pulse flex flex-col gap-4">
          <div className="h-12 w-full bg-gray-200 rounded"></div>
          <div className="h-12 w-full bg-gray-200 rounded"></div>
          <div className="h-12 w-full bg-gray-200 rounded"></div>
          <div className="h-12 w-full bg-gray-200 rounded"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <h2 className="text-xl font-bold text-red-700 mb-2">Error de Conexión</h2>
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => void fetchCatalog(currentPage, searchTerm)}
            className="px-6 py-2 bg-red-600 text-white font-medium rounded hover:bg-red-700 transition-colors cursor-pointer"
          >
            Reintentar Conexión
          </button>
        </div>
      ) : lakes.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-10 text-center">
          <h2 className="text-xl font-bold text-gray-600 mb-1">Catálogo Vacío</h2>
          <p className="text-gray-500">No se encontraron registros en la base de datos para los filtros aplicados.</p>
        </div>
      ) : (
        <>
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

          {/* Componente Paginador Integrado y Blindado */}
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={(page) => {
              if (page >= 1 && page <= totalPages) {
                setCurrentPage(page);
              }
            }}
          />
        </>
      )}
    </div>
  );
}
