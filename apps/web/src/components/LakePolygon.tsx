import React, { useEffect, useRef } from 'react';
import { GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { FeatureCollection, Geometry, Feature } from 'geojson';

// 1. Prevención visual: Aseguramos que los estilos nativos de Leaflet estén cargados
import 'leaflet/dist/leaflet.css';

interface LakePolygonProps {
    geojsonData: FeatureCollection<Geometry> | Feature<Geometry> | null;
}

export const LakePolygon: React.FC<LakePolygonProps> = ({ geojsonData }) => {
    const map = useMap(); 
    const geoJsonRef = useRef<L.GeoJSON>(null);

    useEffect(() => {
        if (geojsonData && geoJsonRef.current) {
            const bounds = geoJsonRef.current.getBounds();
            
            // Seguridad: Aseguramos que el polígono tiene un área válida antes de mover la cámara
            if (bounds.isValid()) {
                map.fitBounds(bounds, { 
                    padding: [40, 40], 
                    animate: true 
                });
            }
        }
    }, [geojsonData, map]); 

    if (!geojsonData) return null;

    // 2. Arquitectura (Bugfix React Leaflet): Creamos un hash o string único basado en el polígono.
    // Al pasar esto como 'key', obligamos a React a redibujar el polígono cuando cambias de lago, 
    // resolviendo el bug nativo donde GeoJSON no actualiza sus datos dinámicamente.
    const dynamicKey = JSON.stringify(geojsonData.bbox || geojsonData.type) + Math.random();

    return (
        <GeoJSON 
            key={dynamicKey}
            data={geojsonData} 
            ref={geoJsonRef}
            style={{ color: '#2563eb', weight: 2, fillOpacity: 0.3 }}
        />
    );
};
