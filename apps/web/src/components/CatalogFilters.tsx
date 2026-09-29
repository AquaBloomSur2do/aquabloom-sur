import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

const REGIONES_CHILE = ["Los Lagos", "La Araucanía", "Los Ríos"];
const OPCIONES_ESTADO = [
    { value: "active", label: "Activo" },
    { value: "inactive", label: "Inactivo" },
    { value: "maintenance", label: "Mantenimiento" }
];

export const CatalogFilters: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();

    const initialText = searchParams.get("text") || "";
    const [localText, setLocalText] = useState(initialText);

    const region = searchParams.get("region") || "";
    const status = searchParams.get("status") || "";

    const updateFilter = useCallback((key: string, value: string) => {
        const currentParams = new URLSearchParams(searchParams);
        
        if (value) {
            currentParams.set(key, value);
        } else {
            currentParams.delete(key);
        }

        currentParams.delete("page");
        setSearchParams(currentParams, { replace: true });
    }, [searchParams, setSearchParams]); 

    useEffect(() => {
        const debounceTimer = setTimeout(() => {
            if (localText !== (searchParams.get("text") || "")) {
                updateFilter("text", localText);
            }
        }, 500);

        return () => clearTimeout(debounceTimer); 
    }, [localText, searchParams, updateFilter]); 

    return (
        <div className="flex gap-4 p-4 bg-gray-50 rounded-lg">
            <label htmlFor="catalog-filter-search" className="sr-only">Buscar lago por nombre</label>
            <input
                id="catalog-filter-search"
                type="text"
                aria-label="Buscar lago por nombre"
                placeholder="Buscar lago por nombre..."
                value={localText}
                onChange={(e) => setLocalText(e.target.value)}
                className="border p-2 rounded w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            />

            <label htmlFor="catalog-filter-region" className="sr-only">Filtrar por región</label>
            <select
                id="catalog-filter-region"
                aria-label="Filtrar por región"
                value={region}
                onChange={(e) => updateFilter("region", e.target.value)}
                className="border p-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
                <option value="">Todas las regiones</option>
                {REGIONES_CHILE.map(r => (
                    <option key={r} value={r}>{r}</option>
                ))}
            </select>

            <label htmlFor="catalog-filter-status" className="sr-only">Filtrar por estado de la estación</label>
            <select
                id="catalog-filter-status"
                aria-label="Filtrar por estado de la estación"
                value={status}
                onChange={(e) => updateFilter("status", e.target.value)}
                className="border p-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
                <option value="">Todos los estados</option>
                {OPCIONES_ESTADO.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
        </div>
    );
};
