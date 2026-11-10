import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import type { FeatureCollection, Geometry } from 'geojson';
import apiClient from '../services/apiClient';
import { Pagination } from '../components/Pagination';
import { CatalogFilters, type CatalogFilterValues } from '../components/CatalogFilters';
import BaseMap from '../components/Map/BaseMap';

interface LakeSummary {
  id: string;
  name: string;
  region: string;
  status: string;
  geom?: Geometry | null;
}

interface PaginatedLakes {
  items: LakeSummary[];
  page: number;
  page_size: number;
  total: number;
}

function getStatusClass(status: string) {
  const normalizedStatus = status.toLowerCase();
  if (normalizedStatus === 'active' || normalizedStatus === 'activo') return 'public';
  if (normalizedStatus === 'inactive' || normalizedStatus === 'inactivo') return 'reported';
  return normalizedStatus;
}

function getStatusStyle(status: string) {
  const normalizedStatus = status.toLowerCase();
  if (normalizedStatus === 'active' || normalizedStatus === 'activo') {
    return { background: '#dcfce7', color: '#166534' };
  }
  if (normalizedStatus === 'inactive' || normalizedStatus === 'inactivo') {
    return { background: '#fef3c7', color: '#92400e' };
  }
  return { background: '#e0e7ff', color: '#3730a3' };
}

function StatusIcon({ status }: { status: string }) {
  const isActive = ['active', 'activo'].includes(status.toLowerCase());
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      style={{ flex: '0 0 auto' }}
    >
      {isActive ? (
        <path d="m3 8 3.2 3.2L13 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <circle cx="8" cy="8" r="5.25" stroke="currentColor" strokeWidth="1.5" />
      )}
    </svg>
  );
}

export default function Catalog() {
  const [lakes, setLakes] = useState<LakeSummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [filters, setFilters] = useState<CatalogFilterValues>({
    text: '',
    region: '',
    status: '',
  });

  const fetchCatalog = useCallback(
    async (pageToFetch: number, activeFilters: CatalogFilterValues) => {
      setIsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          page: pageToFetch.toString(),
          page_size: pageSize.toString(),
        });
        if (activeFilters.text) {
          params.append('search', activeFilters.text);
        }
        if (activeFilters.region) {
          params.append('region', activeFilters.region);
        }
        if (activeFilters.status) {
          params.append('status', activeFilters.status);
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

  const handleFiltersChange = useCallback((nextFilters: CatalogFilterValues) => {
    setFilters(nextFilters);
    setCurrentPage(1);
  }, []);

  useEffect(() => {
    const loadData = async () => {
      await fetchCatalog(currentPage, filters);
    };
    void loadData();
  }, [currentPage, filters, fetchCatalog]);

  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  const lakesWithGeometry = lakes.filter(
    (lake): lake is LakeSummary & { geom: Geometry } => Boolean(lake.geom)
  );
  const lakeGeometries: FeatureCollection<Geometry> = {
    type: 'FeatureCollection',
    features: lakesWithGeometry.map((lake) => ({
      type: 'Feature',
      id: lake.id,
      properties: { id: lake.id, nombre: lake.name },
      geometry: lake.geom,
    })),
  };

  return (
    <main className="catalog-page" style={{ width: '100%', maxWidth: 1440, margin: '0 auto', padding: '2rem', boxSizing: 'border-box' }}>
      <header className="page-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0, fontSize: 'clamp(1.75rem, 3vw, 2.25rem)' }}>
          Catálogo de Lagos
        </h1>
        <Link
          to="/lakes/new"
          className="btn btn-primary"
          style={{ whiteSpace: 'nowrap' }}
        >
          + Registrar Lago
        </Link>
      </header>

      <div className="grid estimator-layout" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 30rem), 1fr))', alignItems: 'start', gap: '1.5rem' }}>
        <section style={{ minWidth: 0 }}>
          <CatalogFilters onFiltersChange={handleFiltersChange} />

          {isLoading ? (
            <div className="animate-pulse flex flex-col gap-4" style={{ marginTop: '1rem' }}>
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-16 w-full bg-gray-200 rounded-lg"></div>
              ))}
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center" style={{ marginTop: '1rem' }}>
              <h2 className="text-xl font-bold text-red-700 mb-2">
                Error de Conexión
              </h2>
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={() => void fetchCatalog(currentPage, filters)}
                className="px-6 py-2 bg-red-600 text-white font-medium rounded hover:bg-red-700 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                Reintentar Conexión
              </button>
            </div>
          ) : lakes.length === 0 ? (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-10 text-center" style={{ marginTop: '1rem' }}>
              <h2 className="text-xl font-bold text-gray-600 mb-1">
                Catálogo Vacío
              </h2>
              <p className="text-gray-500">
                No se encontraron registros para los filtros aplicados.
              </p>
            </div>
          ) : (
            <div className="card" style={{ marginTop: '1rem', overflow: 'hidden', border: '1px solid #e5e7eb', borderRadius: '0.75rem', background: '#fff' }}>
              <div className="lake-list" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="lake-list-head" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(6rem, 0.7fr) minmax(6rem, 0.7fr) auto', gap: '0.75rem', padding: '0.875rem 1rem', color: '#475569', fontSize: '0.8rem', fontWeight: 700, borderBottom: '1px solid #e5e7eb' }}>
                  <span>Nombre</span>
                  <span>Región</span>
                  <span>Estado</span>
                  <span>Acciones</span>
                </div>
                {lakes.map((lake) => (
                  <article
                    key={lake.id}
                    className="lake-row"
                    style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(6rem, 0.7fr) minmax(6rem, 0.7fr) auto', alignItems: 'center', gap: '0.75rem', padding: '1rem', borderBottom: '1px solid #e5e7eb' }}
                  >
                    <div className="lake-name" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0, fontWeight: 650 }}>
                      <span className="lake-symbol" aria-hidden="true" style={{ display: 'grid', placeItems: 'center', width: '2rem', height: '2rem', flex: '0 0 auto', borderRadius: '50%', color: '#0f766e', background: '#ccfbf1' }}>
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                          <path d="M1.5 9.5c2-2 3.5 2 6.5 0s4.5 2 6.5 0M1.5 12.5c2-2 3.5 2 6.5 0s4.5 2 6.5 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                      </span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{lake.name}</span>
                    </div>
                    <span className="metric-mini">{lake.region}</span>
                    <span className={`badge ${getStatusClass(lake.status)}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', width: 'fit-content', padding: '0.3rem 0.55rem', borderRadius: '999px', ...getStatusStyle(lake.status), fontSize: '0.75rem', fontWeight: 650 }}>
                      <StatusIcon status={lake.status} />
                      {lake.status}
                    </span>
                    <Link
                      to={`/lakes/${lake.id}`}
                      className="text-blue-600 font-medium hover:text-blue-800 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-sm"
                    >
                      Ver Detalles
                    </Link>
                  </article>
                ))}
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
        </section>

        <section className="card" aria-label="Mapa del catálogo" style={{ minWidth: 0, minHeight: 420, height: 'min(70vh, 720px)', overflow: 'hidden', border: '1px solid #e5e7eb', borderRadius: '0.75rem', background: '#fff' }}>
          <BaseMap geometries={lakeGeometries} />
        </section>
      </div>
    </main>
  );
}
