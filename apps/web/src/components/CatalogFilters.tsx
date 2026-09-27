import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

// 5. Extracción de datos quemados a constantes limpias
const REGIONES_CHILE = ["Los Lagos", "La Araucanía", "Los Ríos"];
const OPCIONES_ESTADO = [
    { value: "active", label: "Activo" },
    { value: "inactive", label: "Inactivo" },
    { value: "maintenance", label: "Mantenimiento" }
];

export const CatalogFilters: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();

    // Estado local exclusivo para el input de texto (previene spam de red)
    const initialText = searchParams.get("text") || "";
    const [localText, setLocalText] = useState(initialText);

    const region = searchParams.get("region") || "";
    const status = searchParams.get("status") || "";

    const updateFilter = (key: string, value: string) => {
        const currentParams = new URLSearchParams(searchParams);
        
        if (value) {
            currentParams.set(key, value);
        } else {
            currentParams.delete(key);
        }

        // 1. Colisión con Paginación: Siempre limpiar la página al filtrar
        currentParams.delete("page");

        // 2. Destrucción del Historial: replace: true evita saturar el botón "Atrás"
        setSearchParams(currentParams, { replace: true });
    };

    // 3. Debounce para el input de texto (retraso de 500ms)
    useEffect(() => {
        const debounceTimer = setTimeout(() => {
            // Solo actualiza si el texto realmente cambió respecto a la URL
            if (localText !== (searchParams.get("text") || "")) {
                updateFilter("text", localText);
            }
        }, 500);

        return () => clearTimeout(debounceTimer); // Limpia el timer si el usuario sigue escribiendo
    }, [localText]); 

    return (
        <div className="flex gap-4 p-4 bg-gray-50 rounded-lg">
            {/* 4. Accesibilidad (a11y): Incorporación de aria-label en todos los controles */}
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
