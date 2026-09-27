import React from 'react';
import { useSearchParams } from 'react-router-dom';

export const CatalogFilters: React.FC = () => {
    // useSearchParams sincroniza automáticamente nuestro estado con la URL
    const [searchParams, setSearchParams] = useSearchParams();

    // Extraemos los valores actuales de la URL (si recargan la página, se mantienen)
    const text = searchParams.get("text") || "";
    const region = searchParams.get("region") || "";
    const status = searchParams.get("status") || "";

    // Función centralizada para actualizar parámetros sin borrar los que ya existen
    const updateFilter = (key: string, value: string) => {
        const currentParams = new URLSearchParams(searchParams);
        if (value) {
            currentParams.set(key, value);
        } else {
            currentParams.delete(key); // Mantiene la URL limpia si el filtro está vacío
        }
        setSearchParams(currentParams);
    };

    return (
        <div className="flex gap-4 p-4 bg-gray-50 rounded-lg">
            {/* Control de Búsqueda por Texto */}
            <input
                type="text"
                placeholder="Buscar lago por nombre..."
                value={text}
                onChange={(e) => updateFilter("text", e.target.value)}
                className="border p-2 rounded"
            />

            {/* Control de Región */}
            <select
                value={region}
                onChange={(e) => updateFilter("region", e.target.value)}
                className="border p-2 rounded"
            >
                <option value="">Todas las regiones</option>
                <option value="Los Lagos">Los Lagos</option>
                <option value="La Araucanía">La Araucanía</option>
                <option value="Los Ríos">Los Ríos</option>
            </select>

            {/* Control de Estado */}
            <select
                value={status}
                onChange={(e) => updateFilter("status", e.target.value)}
                className="border p-2 rounded"
            >
                <option value="">Todos los estados</option>
                <option value="active">Activo</option>
                <option value="inactive">Inactivo</option>
                <option value="maintenance">Mantenimiento</option>
            </select>
        </div>
    );
};
