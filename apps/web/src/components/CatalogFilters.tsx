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
            <input
                type="text"
                aria-label="Buscar lago por nombre"
                placeholder="Buscar lago por nombre..."
                value={localText}
                onChange={(e) => setLocalText(e.target.value)}
                className="border p-2 rounded w-full"
            />

            <select
                aria-label="Filtrar por región"
                value={region}
                onChange={(e) => updateFilter("region", e.target.value)}
                className="border p-2 rounded"
            >
                <option value="">Todas las regiones</option>
                {REGIONES_CHILE.map(r => (
                    <option key={r} value={r}>{r}</option>
                ))}
            </select>

            <select
                aria-label="Filtrar por estado de la estación"
                value={status}
                onChange={(e) => updateFilter("status", e.target.value)}
                className="border p-2 rounded"
            >
                <option value="">Todos los estados</option>
                {OPCIONES_ESTADO.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
        </div>
    );
};
