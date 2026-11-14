import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

export interface CatalogFilterValues {
  text: string;
  region: string;
  status: string;
}

interface CatalogFiltersProps {
  onFiltersChange?: (filters: CatalogFilterValues) => void;
}

const REGIONES_CHILE = ['Los Lagos', 'La Araucanía', 'Los Ríos'];
const OPCIONES_ESTADO = [
  { value: 'active', label: 'Activo' },
  { value: 'inactive', label: 'Inactivo' },
  { value: 'maintenance', label: 'Mantenimiento' },
];

export const CatalogFilters: React.FC<CatalogFiltersProps> = ({
  onFiltersChange,
}) => {
  const [searchParams, setSearchParams] = useSearchParams();

  const initialText = searchParams.get('text') || '';
  const [localText, setLocalText] = useState(initialText);
  const lastEmittedText = useRef(initialText);

  const [region, setRegion] = useState(searchParams.get('region') || '');
  const [status, setStatus] = useState(searchParams.get('status') || '');

  const updateFilter = useCallback(
    (key: string, value: string) => {
      const currentParams = new URLSearchParams(searchParams);

      if (value) {
        currentParams.set(key, value);
      } else {
        currentParams.delete(key);
      }

      currentParams.delete('page');
      setSearchParams(currentParams, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      if (onFiltersChange) {
        if (localText !== lastEmittedText.current) {
          lastEmittedText.current = localText;
          onFiltersChange({ text: localText, region, status });
        }
      } else if (localText !== (searchParams.get('text') || '')) {
        updateFilter('text', localText);
      }
    }, 500);

    return () => clearTimeout(debounceTimer);
  }, [localText, onFiltersChange, region, searchParams, status, updateFilter]);

  const handleRegionChange = (value: string) => {
    setRegion(value);
    if (onFiltersChange) {
      onFiltersChange({ text: localText, region: value, status });
    } else {
      updateFilter('region', value);
    }
  };

  const handleStatusChange = (value: string) => {
    setStatus(value);
    if (onFiltersChange) {
      onFiltersChange({ text: localText, region, status: value });
    } else {
      updateFilter('status', value);
    }
  };

  return (
    <div
      className="filter-bar card"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '1rem',
        padding: '1rem',
        borderRadius: '0.75rem',
        background: '#fff',
        border: '1px solid #e5e7eb',
      }}
    >
      <label htmlFor="catalog-filter-search" className="sr-only">
        Buscar lago por nombre
      </label>
      <input
        id="catalog-filter-search"
        type="text"
        aria-label="Buscar lago por nombre"
        placeholder="Buscar lago por nombre..."
        value={localText}
        onChange={(e) => setLocalText(e.target.value)}
        className="border p-2 rounded w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      />

      <label htmlFor="catalog-filter-region" className="sr-only">
        Filtrar por región
      </label>
      <select
        id="catalog-filter-region"
        aria-label="Filtrar por región"
        value={region}
        onChange={(e) => handleRegionChange(e.target.value)}
        className="border p-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        <option value="">Todas las regiones</option>
        {REGIONES_CHILE.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>

      <label htmlFor="catalog-filter-status" className="sr-only">
        Filtrar por estado de la estación
      </label>
      <select
        id="catalog-filter-status"
        aria-label="Filtrar por estado de la estación"
        value={status}
        onChange={(e) => handleStatusChange(e.target.value)}
        className="border p-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        <option value="">Todos los estados</option>
        {OPCIONES_ESTADO.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
};
