import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import apiClient from '../services/apiClient';
import { Pagination } from '../components/Pagination';

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

  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [searchTerm, setSearchTerm] = useState<string>('');

  const fetchCatalog = useCallback(
    async (pageToFetch: number, search: string) => {
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

        const data = await apiClient.get<PaginatedLakes>(
          `/lakes?${params.toString()}`
        );
        setLakes(data.items || []);
        setTotalItems(data.total || 0);
      } catch {
        setError(
          'No se pudo cargar el catálogo de lagos. Verifica tu conexión al servidor.'
        );
        toast.error('Falló la sincronización con el catálogo.');
      } finally {
        setIsLoading(false);
      }
    },
    [pageSize]
  );

  useEffect(() => {
    const loadData = async () => {
      await fetchCatalog(currentPage, searchTerm);
    };
    void loadData();
  }, [currentPage, searchTerm, fetchCatalog]);

  const totalPages = Math.ceil(totalItems / pageSize) || 1;

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto w-full">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-800">
          Catálogo de Lagos
        </h1>
        <Link
          to="/lakes/new"
          className="w-full md:w-auto px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500"
        >
          + Registrar Lago
        </Link>
      </div>

      <div className="mb-6 flex gap-4 items-center w-full">
        <label htmlFor="catalog-search" className="sr-only">Buscar lago por nombre</label>
        <input
          id="catalog-search"
          type="text"
          placeholder="Buscar lago por nombre..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setCurrentPage(1);
          }}
          className="px-4 py-2 border border-gray-300 rounded-lg w-full max-w-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        />
      </div>

      {isLoading ? (
        <div className="animate-pulse flex flex-col gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 w-full bg-gray-200 rounded-lg"></div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <h2 className="text-xl font-bold text-red-700 mb-2">
            Error de Conexión
          </h2>
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => void fetchCatalog(currentPage, searchTerm)}
            className="px-6 py-2 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            Reintentar Conexión
          </button>
        </div>
      ) : lakes.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-10 text-center">
          <h2 className="text-xl font-bold text-gray-600 mb-1">
            Catálogo Vacío
          </h2>
          <p className="text-gray-500">
            No se encontraron registros para los filtros aplicados.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden w-full">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[600px]">
              <thead>
                <tr className="bg-gray-50 text-gray-700 border-b border-gray-200 text-sm md:text-base">
                  <th className="p-3 md:p-4 font-semibold whitespace-nowrap">
                    Nombre
                  </th>
                  <th className="p-3 md:p-4 font-semibold whitespace-nowrap">
                    Región
                  </th>
                  <th className="p-3 md:p-4 font-semibold whitespace-nowrap">
                    Estado
                  </th>
                  <th className="p-3 md:p-4 font-semibold whitespace-nowrap text-right">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody>
                {lakes.map((lake) => (
                  <tr
                    key={lake.id}
                    className="hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-0 text-sm md:text-base"
                  >
                    <td className="p-3 md:p-4 font-medium text-gray-900 truncate max-w-[150px] md:max-w-none">
                      {lake.name}
                    </td>
                    <td className="p-3 md:p-4 text-gray-600">{lake.region}</td>
                    <td className="p-3 md:p-4">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap status-badge--${lake.status.toLowerCase()}`}
                      >
                        {lake.status}
                      </span>
                    </td>
                    <td className="p-3 md:p-4 text-right">
                      <Link
                        to={`/lakes/${lake.id}`}
                        className="text-blue-600 font-medium hover:text-blue-800 hover:underline whitespace-nowrap inline-block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-sm"
                      >
                        Ver Detalles
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-gray-100 bg-gray-50 flex justify-center">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={(page) => {
                if (page >= 1 && page <= totalPages) setCurrentPage(page);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

