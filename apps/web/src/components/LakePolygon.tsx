import React, { useEffect, useRef, useMemo } from 'react';
import { GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { FeatureCollection, Geometry, Feature } from 'geojson';

// Importación de los estilos base de Leaflet
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
            
            if (bounds.isValid()) {
                map.fitBounds(bounds, { 
                    padding: [40, 40], 
                    animate: true 
                });
            }
        }
    }, [geojsonData, map]); 

    // Memoización arquitectónica: Protege el hilo principal y garantiza el redibujado 
    // exacto ante cambios de geometría, evitando falsos positivos de caché.
    const dynamicKey = useMemo(() => {
        return JSON.stringify(geojsonData);
    }, [geojsonData]);

    if (!geojsonData) return null;

    return (
        <GeoJSON 
            key={dynamicKey}
            data={geojsonData} 
            ref={geoJsonRef}
            style={{ color: '#2563eb', weight: 2, fillOpacity: 0.3 }}
        />
    );
};
